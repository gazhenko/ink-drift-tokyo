using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace InkDrift.Net
{
    /// <summary>
    /// Connection to the online relay (Relay/ in the repo, a Cloudflare Worker). Every game connects out to it over a
    /// WebSocket, so nobody has to open a router port: the host gets a room code, friends join with it, and the relay
    /// passes the game's packets between them. Frames hold records [peer u8][length u16][bytes]; peer 255 is the relay
    /// itself (welcome / joined / left / error). Runs on background threads; events queue up for the main thread.
    /// </summary>
    public class RelayLink : IDisposable
    {
        public const string DefaultUrl = "wss://inkdrift-relay.gazhenko.dev";
        const string Alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
        const int CodeLength = 6;
        const byte RelayPeer = 255, CtlWelcome = 1, CtlJoined = 2, CtlLeft = 3, CtlError = 4;
        const int MaxQueued = 4000;

        public enum EventKind { Open, Joined, Left, Error, Closed }
        public struct Event { public EventKind kind; public int id; public string text; }

        /// <summary>The relay to use (-relay ws://127.0.0.1:8787 points the game at a local test server).</summary>
        public static string Url => CommandLine.Has("-relay") ? CommandLine.Get("-relay").TrimEnd('/') : DefaultUrl;

        public bool IsOpen => open;
        /// <summary>This game's id in the room (0 = host).</summary>
        public int LocalId { get; private set; } = -1;
        /// <summary>The room code without the dash (set once open).</summary>
        public string RoomCode { get; private set; }
        public readonly ConcurrentQueue<Event> Events = new ConcurrentQueue<Event>();
        /// <summary>Called on the receive thread for every packet: sender's id in the room, bytes.</summary>
        public Action<int, byte[]> OnPacket;
        public long BytesIn, BytesOut, FramesOut;

        readonly ClientWebSocket ws = new ClientWebSocket();
        readonly CancellationTokenSource cts = new CancellationTokenSource();
        readonly ConcurrentQueue<byte[]> outbox = new ConcurrentQueue<byte[]>();
        readonly AutoResetEvent wake = new AutoResetEvent(false);
        volatile bool open, closing, ended;

        public static RelayLink Host() => new RelayLink(Url + "/v1/host");
        public static RelayLink Join(string code) => new RelayLink(Url + "/v1/join/" + code);

        RelayLink(string url)
        {
            var uri = new Uri(url);
            Task.Run(() => Run(uri));
        }

        // ---------------------------------------------------------------- room codes
        /// <summary>A room code typed by a player ("k7q-4mz", "K7Q 4MZ"), normalised to "K7Q4MZ". Addresses don't count.</summary>
        public static bool TryParseCode(string text, out string code)
        {
            code = null;
            if (string.IsNullOrWhiteSpace(text) || text.Contains(".") || text.Contains(":")) return false;
            var s = text.Trim().ToUpperInvariant().Replace("-", "").Replace(" ", "");
            if (s.Length != CodeLength) return false;
            foreach (char c in s) if (Alphabet.IndexOf(c) < 0) return false;
            code = s;
            return true;
        }

        /// <summary>"K7Q4MZ" -> "K7Q-4MZ".</summary>
        public static string Format(string code) => string.IsNullOrEmpty(code) || code.Length != CodeLength ? code : code.Substring(0, 3) + "-" + code.Substring(3);

        // ---------------------------------------------------------------- send
        /// <summary>Queue a packet for a peer in the room (any thread). Dropped until the room is open.</summary>
        public void Send(int to, byte[] data, int len)
        {
            if (!open || closing || len > 4096) return;
            if (outbox.Count > MaxQueued) return;          // the link is stalled: unreliable data is stale anyway
            var rec = new byte[len + 3];
            rec[0] = (byte)to; rec[1] = (byte)(len & 0xFF); rec[2] = (byte)(len >> 8);
            Buffer.BlockCopy(data, 0, rec, 3, len);
            outbox.Enqueue(rec);
            wake.Set();
        }

        void SendLoop()
        {
            var frame = new MemoryStream();
            while (!ended)
            {
                wake.WaitOne(250);
                if (ended) return;
                if (outbox.IsEmpty) { if (closing) break; continue; }
                Thread.Sleep(2);                           // gather the rest of this frame's packets into one message
                frame.SetLength(0);
                while (frame.Length < 32768 && outbox.TryDequeue(out var rec)) frame.Write(rec, 0, rec.Length);
                try
                {
                    ws.SendAsync(new ArraySegment<byte>(frame.GetBuffer(), 0, (int)frame.Length), WebSocketMessageType.Binary, true, cts.Token).GetAwaiter().GetResult();
                    BytesOut += frame.Length; FramesOut++;
                }
                catch (Exception e) { End(closing ? null : Describe(e)); return; }
            }
            if (closing)
            {
                try { ws.CloseOutputAsync(WebSocketCloseStatus.NormalClosure, "bye", CancellationToken.None).Wait(1000); } catch { }
                End(null);
                try { cts.Cancel(); } catch { }
            }
        }

        // ---------------------------------------------------------------- receive
        async Task Run(Uri uri)
        {
            try
            {
                using (var connect = CancellationTokenSource.CreateLinkedTokenSource(cts.Token))
                {
                    connect.CancelAfter(12000);
                    await ws.ConnectAsync(uri, connect.Token).ConfigureAwait(false);
                }
                new Thread(SendLoop) { IsBackground = true, Name = "InkRelaySend" }.Start();
                var buf = new byte[16384];
                var msg = new MemoryStream();
                while (!ended && ws.State == WebSocketState.Open)
                {
                    var r = await ws.ReceiveAsync(new ArraySegment<byte>(buf), cts.Token).ConfigureAwait(false);
                    if (r.MessageType == WebSocketMessageType.Close) break;
                    msg.Write(buf, 0, r.Count);
                    if (!r.EndOfMessage) continue;
                    BytesIn += msg.Length;
                    if (r.MessageType == WebSocketMessageType.Binary) Parse(msg.GetBuffer(), (int)msg.Length);
                    msg.SetLength(0);
                }
                End(null);
            }
            catch (Exception e) { End(closing ? null : Describe(e)); }
        }

        void Parse(byte[] d, int n)
        {
            for (int i = 0; i + 3 <= n;)
            {
                int from = d[i], len = d[i + 1] | (d[i + 2] << 8);
                i += 3;
                if (i + len > n) return;
                if (from == RelayPeer) Control(d, i, len);
                else
                {
                    var copy = new byte[len];
                    Buffer.BlockCopy(d, i, copy, 0, len);
                    OnPacket?.Invoke(from, copy);
                }
                i += len;
            }
        }

        void Control(byte[] d, int i, int len)
        {
            if (len < 1) return;
            switch (d[i])
            {
                case CtlWelcome when len >= 2:
                    LocalId = d[i + 1];
                    RoomCode = Encoding.UTF8.GetString(d, i + 2, len - 2);
                    open = true;
                    Events.Enqueue(new Event { kind = EventKind.Open, id = LocalId, text = RoomCode });
                    break;
                case CtlJoined when len >= 2:
                    Events.Enqueue(new Event { kind = EventKind.Joined, id = d[i + 1] });
                    break;
                case CtlLeft when len >= 2:
                    Events.Enqueue(new Event { kind = EventKind.Left, id = d[i + 1] });
                    break;
                case CtlError:
                    Events.Enqueue(new Event { kind = EventKind.Error, text = Encoding.UTF8.GetString(d, i + 1, len - 1) });
                    break;
            }
        }

        // ---------------------------------------------------------------- shutdown
        void End(string error)
        {
            if (ended) return;
            ended = true; open = false;
            wake.Set();
            Events.Enqueue(new Event { kind = error != null ? EventKind.Error : EventKind.Closed, text = error });
        }

        static string Describe(Exception e)
        {
            while (e.InnerException != null && (e is AggregateException || e is WebSocketException)) e = e.InnerException;
            Debug.Log("[Net] relay: " + e.GetType().Name + ": " + e.Message);
            return e is OperationCanceledException
                ? "The online service didn't answer. Check your internet connection and try again."
                : "Couldn't reach the online service (" + e.Message + "). Check your internet connection and try again.";
        }

        /// <summary>Send what's queued, then close (doesn't block).</summary>
        public void Dispose()
        {
            if (closing) return;
            closing = true;
            wake.Set();
            if (!open) { try { cts.Cancel(); } catch { } }
            // whatever happens to the polite close, everything is torn down shortly after
            Task.Delay(1500).ContinueWith(_ => { ended = true; try { cts.Cancel(); } catch { } try { ws.Dispose(); } catch { } });
        }
    }
}
