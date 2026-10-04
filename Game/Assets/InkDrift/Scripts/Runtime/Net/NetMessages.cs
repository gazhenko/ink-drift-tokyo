using System;
using System.IO;
using System.Text;
using UnityEngine;

namespace InkDrift.Net
{
    public enum Msg : byte
    {
        Hello = 1,        // client -> host (unreliable, repeated until Welcome): token, version, name, car, paint
        Welcome = 2,      // host -> client (reliable): your id
        Reject = 3,       // host -> client: reason
        Lobby = 4,        // host -> all (reliable): track, laps, players
        LobbyUpdate = 5,  // client -> host (reliable): name, car, paint, ready, inLobby
        Ping = 6,         // client -> host (unreliable): client time
        Pong = 7,         // host -> client (unreliable): client time, host time
        StartRace = 8,    // host -> all (reliable): track, laps, grid
        Loaded = 9,       // client -> host (reliable)
        Go = 10,          // host -> all (reliable): host time of the green light
        CarState = 11,    // owner -> host -> others (unreliable)
        Finish = 12,      // client -> host (reliable): race time
        Results = 13,     // host -> all (reliable): standings
        Leave = 14,       // either way (reliable, best effort)
        Discover = 15,    // anyone -> broadcast (unreliable)
        HostInfo = 16,    // host -> discoverer (unreliable): name, players, port, version
        ToLobby = 17,     // host -> all (reliable): race over, back to the lobby
    }

    public class NetWriter
    {
        readonly MemoryStream ms = new MemoryStream(256);
        readonly BinaryWriter w;
        public NetWriter(Msg type) { w = new BinaryWriter(ms); w.Write((byte)type); }
        public NetWriter U8(int v) { w.Write((byte)v); return this; }
        public NetWriter I8(int v) { w.Write((sbyte)Mathf.Clamp(v, -128, 127)); return this; }
        public NetWriter U16(int v) { w.Write((ushort)v); return this; }
        public NetWriter I32(int v) { w.Write(v); return this; }
        public NetWriter U32(uint v) { w.Write(v); return this; }
        public NetWriter F32(float v) { w.Write(v); return this; }
        public NetWriter F64(double v) { w.Write(v); return this; }
        public NetWriter Bool(bool v) { w.Write(v); return this; }
        public NetWriter V3(Vector3 v) { w.Write(v.x); w.Write(v.y); w.Write(v.z); return this; }
        public NetWriter Q(Quaternion q) { w.Write(q.x); w.Write(q.y); w.Write(q.z); w.Write(q.w); return this; }
        public NetWriter Str(string s)
        {
            var b = Encoding.UTF8.GetBytes(s ?? "");
            int n = Math.Min(b.Length, 255);
            w.Write((byte)n); w.Write(b, 0, n);
            return this;
        }
        public byte[] Bytes => ms.ToArray();
    }

    public class NetReader
    {
        readonly BinaryReader r;
        public readonly Msg Type;
        public NetReader(byte[] data) { r = new BinaryReader(new MemoryStream(data)); Type = (Msg)r.ReadByte(); }
        public int U8() => r.ReadByte();
        public int I8() => r.ReadSByte();
        public int U16() => r.ReadUInt16();
        public int I32() => r.ReadInt32();
        public uint U32() => r.ReadUInt32();
        public float F32() => r.ReadSingle();
        public double F64() => r.ReadDouble();
        public bool Bool() => r.ReadBoolean();
        public Vector3 V3() => new Vector3(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
        public Quaternion Q() => new Quaternion(r.ReadSingle(), r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
        public string Str() { int n = r.ReadByte(); return Encoding.UTF8.GetString(r.ReadBytes(n)); }
    }

    /// <summary>One car's state as its owner sees it (sent ~30 times a second).</summary>
    public struct CarSnapshot
    {
        public int id;
        public double time;          // host clock
        public Vector3 pos, vel, angVel;
        public Quaternion rot;
        public float steer, throttle, brake;
        public bool handbrake, finished;
        public int gear;
        public float progress;       // race distance (laps × length + distance past the line)
        public int lap;
        public uint resetCount;      // bumps when the owner reset the car (teleport, don't smooth)

        public void Write(NetWriter w)
        {
            w.U8(id).F64(time).V3(pos).Q(rot).V3(vel).V3(angVel)
             .I8(Mathf.RoundToInt(steer * 127f)).U8(Mathf.RoundToInt(throttle * 255f)).U8(Mathf.RoundToInt(brake * 255f))
             .U8((handbrake ? 1 : 0) | (finished ? 2 : 0)).I8(gear).F32(progress).U8(lap).U32(resetCount);
        }

        public static CarSnapshot Read(NetReader r)
        {
            var s = new CarSnapshot { id = r.U8(), time = r.F64(), pos = r.V3(), rot = r.Q(), vel = r.V3(), angVel = r.V3() };
            s.steer = r.I8() / 127f; s.throttle = r.U8() / 255f; s.brake = r.U8() / 255f;
            int f = r.U8(); s.handbrake = (f & 1) != 0; s.finished = (f & 2) != 0;
            s.gear = r.I8(); s.progress = r.F32(); s.lap = r.U8(); s.resetCount = r.U32();
            return s;
        }
    }

    /// <summary>
    /// Invite codes: a host's IPv4 address and port as 8 Crockford base-32 characters ("INK-XXXX-XXXX"), so a friend
    /// can paste one line instead of an address. The join box also takes a plain address, host name or ip:port.
    /// </summary>
    public static class InviteCodec
    {
        const string Alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

        public static string Encode(System.Net.IPAddress ip, int port)
        {
            var b = ip.GetAddressBytes();
            if (b.Length != 4) return null;
            ulong v = ((ulong)b[0] << 32) | ((ulong)b[1] << 24) | ((ulong)b[2] << 16) | ((ulong)b[3] << 8) | (ulong)(port - 7777 & 0xFF);
            var sb = new StringBuilder();
            for (int i = 0; i < 8; i++) { sb.Insert(0, Alphabet[(int)(v & 31)]); v >>= 5; }
            return "INK-" + sb.ToString(0, 4) + "-" + sb.ToString(4, 4);
        }

        public static bool TryDecode(string code, out System.Net.IPEndPoint ep)
        {
            ep = null;
            if (string.IsNullOrEmpty(code)) return false;
            var s = code.Trim().ToUpperInvariant().Replace("-", "").Replace(" ", "");
            if (s.StartsWith("INK")) s = s.Substring(3);
            if (s.Length != 8) return false;
            ulong v = 0;
            foreach (char c0 in s)
            {
                char c = c0 == 'O' ? '0' : c0 == 'I' || c0 == 'L' ? '1' : c0;
                int k = Alphabet.IndexOf(c);
                if (k < 0) return false;
                v = (v << 5) | (uint)k;
            }
            var ip = new System.Net.IPAddress(new[] { (byte)(v >> 32), (byte)(v >> 24), (byte)(v >> 16), (byte)(v >> 8) });
            ep = new System.Net.IPEndPoint(ip, 7777 + (int)(v & 0xFF));
            return true;
        }
    }
}
