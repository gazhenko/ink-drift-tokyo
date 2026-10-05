// INK DRIFT TOKYO online relay: a Cloudflare Worker that lets friends race without opening router ports.
//
// The host opens a WebSocket to /v1/host and gets a room code; friends open /v1/join/<code>. Every game connects
// outward, so no router or firewall has to accept incoming connections. Each room is one Durable Object that
// passes the game's own packets between the host and its guests (the host still runs the race).
//
// Binary frames carry records:  [peer u8][length u16 little-endian][bytes]
//   client -> relay: peer = where the packet goes (guests may only send to the host, peer 0)
//   relay -> client: peer = who sent it, or 255 for a message from the relay itself:
//     [1 = welcome][your id u8][room code utf8]   [2 = joined][id]   [3 = left][id]   [4 = error][utf8 text]

const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";   // no I, O, 0 or 1: easy to read out loud
const CODE_LENGTH = 6;
const MAX_GUESTS = 7;                                   // 8 drivers in a game
const RELAY = 255;
const WELCOME = 1, JOINED = 2, LEFT = 3, ERROR = 4;
const MAX_RECORD = 4096, MAX_FRAME = 65536;

export function normalizeCode(text) {
  const s = String(text || "").toUpperCase().replace(/[\s-]/g, "");
  if (s.length !== CODE_LENGTH) return null;
  for (const c of s) if (!ALPHABET.includes(c)) return null;
  return s;
}

function randomCode() {
  const bytes = crypto.getRandomValues(new Uint8Array(CODE_LENGTH));
  let s = "";
  for (const b of bytes) s += ALPHABET[b & 31];
  return s;
}

function record(peer, payload) {
  const out = new Uint8Array(3 + payload.length);
  out[0] = peer; out[1] = payload.length & 0xff; out[2] = payload.length >> 8;
  out.set(payload, 3);
  return out;
}

function control(kind, id, text) {
  const t = text ? new TextEncoder().encode(text) : new Uint8Array(0);
  const body = new Uint8Array((id === null ? 1 : 2) + t.length);
  body[0] = kind;
  if (id !== null) body[1] = id;
  body.set(t, id === null ? 1 : 2);
  return record(RELAY, body);
}

function trySend(ws, data) {
  try { ws.send(data); return true; } catch { return false; }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/" || url.pathname === "/health")
      return new Response("INK DRIFT TOKYO relay: ok\n", { headers: { "content-type": "text/plain" } });

    const join = url.pathname.match(/^\/v1\/join\/([^/]+)$/);
    if (url.pathname !== "/v1/host" && !join) return new Response("Not found\n", { status: 404 });
    if (request.headers.get("Upgrade") !== "websocket") return new Response("Expected a WebSocket\n", { status: 426 });

    if (join) {
      const code = normalizeCode(decodeURIComponent(join[1]));
      if (!code) return new Response("Bad room code\n", { status: 400 });
      const room = env.ROOMS.get(env.ROOMS.idFromName(code));
      return room.fetch(new Request(`https://room/join?code=${code}`, request));
    }
    // a fresh random code; 30 bits make a clash with a live room very unlikely, but try again if it happens
    for (let i = 0; i < 6; i++) {
      const code = randomCode();
      const room = env.ROOMS.get(env.ROOMS.idFromName(code));
      const res = await room.fetch(new Request(`https://room/host?code=${code}`, request));
      if (res.status !== 409) return res;
    }
    return new Response("No free room, try again\n", { status: 503 });
  },
};

/** One game room: the host's socket plus up to seven guests. Uses the hibernation API, so state lives on the sockets. */
export class Room {
  constructor(state) {
    this.state = state;
  }

  host() { return this.state.getWebSockets("host")[0] || null; }
  guest(id) { return this.state.getWebSockets("g" + id)[0] || null; }

  async fetch(request) {
    const url = new URL(request.url);
    const code = url.searchParams.get("code");
    const host = this.host();
    if (url.pathname === "/host" && host) return new Response("Room in use\n", { status: 409 });

    const [client, server] = Object.values(new WebSocketPair());
    if (url.pathname === "/host") {
      this.state.acceptWebSocket(server, ["host"]);
      server.serializeAttachment({ id: 0, code, nextId: 1 });
      server.send(control(WELCOME, 0, code));
      return new Response(null, { status: 101, webSocket: client });
    }

    const reject = (text) => {
      server.accept();
      server.send(control(ERROR, null, text));
      server.close(4000, "rejected");
      return new Response(null, { status: 101, webSocket: client });
    };
    if (!host) return reject(`No game found with the code ${code.slice(0, 3)}-${code.slice(3)}. Check the code, or ask your friend to host again.`);
    if (this.state.getWebSockets("guest").length >= MAX_GUESTS) return reject("That game is full.");

    // ids count up (wrapping past 254) so a leaving guest's id isn't handed straight to the next one
    const h = host.deserializeAttachment();
    let id = h.nextId;
    while (this.guest(id)) id = id >= 254 ? 1 : id + 1;
    h.nextId = id >= 254 ? 1 : id + 1;
    host.serializeAttachment(h);

    this.state.acceptWebSocket(server, ["guest", "g" + id]);
    server.serializeAttachment({ id, code });
    server.send(control(WELCOME, id, code));
    trySend(host, control(JOINED, id));
    return new Response(null, { status: 101, webSocket: client });
  }

  async webSocketMessage(ws, message) {
    if (typeof message === "string" || message.byteLength > MAX_FRAME) return;
    const from = ws.deserializeAttachment().id;
    const data = new Uint8Array(message);
    const out = new Map();                       // target socket -> records for it (one frame per target)
    for (let i = 0; i + 3 <= data.length;) {
      const to = data[i], len = data[i + 1] | (data[i + 2] << 8);
      i += 3;
      if (len > MAX_RECORD || i + len > data.length) break;
      const target = from === 0 ? (to === 0 ? null : this.guest(to)) : (to === 0 ? this.host() : null);
      if (target) {
        if (!out.has(target)) out.set(target, []);
        out.get(target).push(record(from, data.subarray(i, i + len)));
      }
      i += len;
    }
    for (const [target, records] of out) {
      if (records.length === 1) { trySend(target, records[0]); continue; }
      let size = 0;
      for (const r of records) size += r.length;
      const frame = new Uint8Array(size);
      let o = 0;
      for (const r of records) { frame.set(r, o); o += r.length; }
      trySend(target, frame);
    }
  }

  async webSocketClose(ws) { this.leave(ws); }
  async webSocketError(ws) { this.leave(ws); }

  leave(ws) {
    let id;
    try { id = ws.deserializeAttachment().id; } catch { return; }
    if (id === 0) {
      // the host left: the game is over for everyone
      for (const g of this.state.getWebSockets("guest")) {
        trySend(g, control(ERROR, null, "The host closed the game."));
        try { g.close(4001, "host left"); } catch { }
      }
    } else {
      const host = this.host();
      if (host && host !== ws) trySend(host, control(LEFT, id));
    }
    try { ws.close(1000, "bye"); } catch { }
  }
}
