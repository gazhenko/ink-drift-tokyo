// End-to-end check of the relay: node test/relay-test.mjs [ws://127.0.0.1:8787 | wss://inkdrift-relay.gazhenko.dev]
const base = (process.argv[2] || "ws://127.0.0.1:8787").replace(/\/$/, "");
const RELAY = 255, WELCOME = 1, JOINED = 2, LEFT = 3, ERROR = 4;
let failures = 0;

function check(ok, what) {
  console.log(`${ok ? "PASS" : "FAIL"}  ${what}`);
  if (!ok) failures++;
}

function frame(records) {
  const parts = records.map(([to, payload]) => {
    const p = typeof payload === "string" ? new TextEncoder().encode(payload) : payload;
    const r = new Uint8Array(3 + p.length);
    r[0] = to; r[1] = p.length & 0xff; r[2] = p.length >> 8; r.set(p, 3);
    return r;
  });
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

/** A test client: collects records (from, bytes) and relay control messages. */
function connect(path) {
  return new Promise((resolve) => {
    const ws = new WebSocket(base + path);
    ws.binaryType = "arraybuffer";
    const c = { ws, records: [], control: [], closed: false, id: -1, code: null, waiters: [] };
    const wake = () => { for (const w of c.waiters.splice(0)) w(); };
    ws.onmessage = (e) => {
      const d = new Uint8Array(e.data);
      for (let i = 0; i + 3 <= d.length;) {
        const from = d[i], len = d[i + 1] | (d[i + 2] << 8);
        const body = d.slice(i + 3, i + 3 + len);
        i += 3 + len;
        if (from === RELAY) {
          const kind = body[0];
          const msg = { kind };
          if (kind === WELCOME) { msg.id = body[1]; msg.text = new TextDecoder().decode(body.slice(2)); c.id = msg.id; c.code = msg.text; }
          else if (kind === JOINED || kind === LEFT) msg.id = body[1];
          else msg.text = new TextDecoder().decode(body.slice(1));
          c.control.push(msg);
        } else c.records.push({ from, text: new TextDecoder().decode(body) });
      }
      wake();
    };
    ws.onclose = () => { c.closed = true; wake(); };
    ws.onerror = () => { c.error = true; c.closed = true; wake(); resolve(c); };
    ws.onopen = () => resolve(c);
  });
}

function until(c, pred, ms = 3000) {
  return new Promise((resolve) => {
    if (pred()) return resolve(true);
    const t = setTimeout(() => resolve(false), ms);
    const loop = () => { if (pred()) { clearTimeout(t); resolve(true); } else c.waiters.push(loop); };
    c.waiters.push(loop);
  });
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const httpBase = base.replace(/^ws/, "http");
const health = await fetch(httpBase + "/");
check(health.ok && (await health.text()).includes("ok"), "health check answers");

const host = await connect("/v1/host");
check(await until(host, () => host.code), `host gets a room code (${host.code})`);
check(host.id === 0, "host is peer 0");
const pretty = host.code ? host.code.slice(0, 3).toLowerCase() + "-" + host.code.slice(3).toLowerCase() : "";

const a = await connect("/v1/join/" + pretty);
check(await until(a, () => a.id >= 0) && a.id === 1, "guest A joins with a lowercase, dashed code as peer 1");
check(await until(host, () => host.control.some((m) => m.kind === JOINED && m.id === 1)), "host hears that peer 1 joined");
const b = await connect("/v1/join/" + host.code);
check(await until(b, () => b.id >= 0) && b.id === 2, "guest B joins as peer 2");

a.ws.send(frame([[0, "hello from A"]]));
check(await until(host, () => host.records.some((r) => r.from === 1 && r.text === "hello from A")), "guest -> host arrives tagged with the sender");

host.ws.send(frame([[1, "to A"], [2, "to B"], [1, "again A"]]));
check(await until(a, () => a.records.filter((r) => r.from === 0).length >= 2), "host frame with several records reaches A");
check(a.records.map((r) => r.text).join("|") === "to A|again A", "A gets only its records, in order");
check(await until(b, () => b.records.length >= 1) && b.records[0].text === "to B", "B gets its record");

a.ws.send(frame([[2, "sneaky"]]));
await sleep(500);
check(!b.records.some((r) => r.text === "sneaky"), "guests can't send to other guests");

// latency: host -> A -> host
let rtts = [];
for (let i = 0; i < 10; i++) {
  const t0 = performance.now();
  const n = host.records.length;
  host.ws.send(frame([[1, "ping" + i]]));
  await until(a, () => a.records.some((r) => r.text === "ping" + i));
  a.ws.send(frame([[0, "pong" + i]]));
  await until(host, () => host.records.length > n);
  rtts.push(performance.now() - t0);
}
rtts.sort((x, y) => x - y);
console.log(`      round trip host -> guest -> host via the relay: median ${rtts[5].toFixed(1)} ms, best ${rtts[0].toFixed(1)} ms`);

a.ws.close();
check(await until(host, () => host.control.some((m) => m.kind === LEFT && m.id === 1)), "host hears that peer 1 left");
const c = await connect("/v1/join/" + host.code);
check(await until(c, () => c.id >= 0) && c.id === 3, "the next guest gets a fresh id (3), not the one that just left");

const nobody = await connect("/v1/join/ZZZ-ZZZ");
check(await until(nobody, () => nobody.control.some((m) => m.kind === ERROR)), "unknown code gets an error: " + (nobody.control.find((m) => m.kind === ERROR)?.text || "-"));
check(await until(nobody, () => nobody.closed), "...and is closed");
const bad = await connect("/v1/join/HELLO");
check(bad.error || bad.closed, "malformed code is refused");

const extra = [];
for (let i = 0; i < 5; i++) extra.push(await connect("/v1/join/" + host.code));      // B, C + 5 = 7 guests
await Promise.all(extra.map((g) => until(g, () => g.id >= 0)));
const full = await connect("/v1/join/" + host.code);
check(await until(full, () => full.control.some((m) => m.kind === ERROR && /full/.test(m.text))), "an eighth guest is told the game is full");

host.ws.close();
check(await until(b, () => b.control.some((m) => m.kind === ERROR && /host closed/.test(m.text))), "guests hear that the host closed the game");
check(await until(b, () => b.closed || b.ws.readyState >= 2), "...and are disconnected");
for (const g of [c, ...extra]) try { g.ws.close(); } catch { }

console.log(failures ? `${failures} FAILED` : "ALL PASSED");
process.exit(failures ? 1 : 0);
