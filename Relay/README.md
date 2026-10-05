# INK DRIFT TOKYO relay

The online relay behind room codes: a Cloudflare Worker with one Durable Object per room. Every game connects out to
it over a WebSocket, so players never have to open router ports. The relay only passes packets between the host and
the guests in a room; the host's game still runs the race.

- `GET /v1/host` (WebSocket): opens a room and answers with its code.
- `GET /v1/join/<code>` (WebSocket): joins that room (codes are case and dash tolerant).
- Frames carry records `[peer u8][length u16 LE][bytes]`. Clients address records to a peer (guests can only reach the
  host, peer 0); the relay tags them with the sender. Peer 255 is the relay itself: welcome (your id and the room
  code), joined, left and error.

```sh
npm install
npx wrangler dev --ip 0.0.0.0     # local server; start the game with -relay ws://<this machine>:8787
npm test                          # end-to-end check against ws://127.0.0.1:8787
node test/relay-test.mjs wss://inkdrift-relay.gazhenko.dev
CLOUDFLARE_ACCOUNT_ID=... npx wrangler deploy
```

Deploying needs a Cloudflare API token with **Workers Scripts: Edit** on the account and **Workers Routes: Edit** on
the `gazhenko.dev` zone. The game's default relay is `RelayLink.DefaultUrl` in
`Game/Assets/InkDrift/Scripts/Runtime/Net/RelayLink.cs`.

Cost: on the free Workers plan, each WebSocket message the relay receives counts as 1/20 of a request against the
100,000 a day, which covers several hours of racing a day. Request logging is off.
