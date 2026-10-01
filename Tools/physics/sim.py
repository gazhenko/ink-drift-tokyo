"""
Planar port of CarController (tire model, clutch/drivetrain, gearbox) with quasi-static load transfer.
Used to sanity-check drift balance + AI/test controller gains before running in Unity.
  Tools/.venv/bin/python Tools/physics/sim.py [car_id ...]
"""
import math, sys, re
import numpy as np

RAD2RPM = 60 / (2 * math.pi)
G = 9.81

# --- car specs (mirrors CarCatalog defaults; keep in sync by hand for tuning experiments)
BASE = dict(mass=1270, com_h=0.42, com_z=0.02, wheelbase=2.575, front_axle_z=1.30, track_f=1.52, track_r=1.55, r=0.33, wheel_I=1.2,
            arb_f=14000, arb_r=9000, grip_f=1.18, grip_r=1.08, peak_alpha=7.5, peak_sx=0.11, slide_f=0.88, slide_r=0.80, falloff=0.85,
            load_sens=0.10, idle=950, redline=7400, revlimit=7600, trpm=[1000, 2000, 3000, 4000, 5000, 6000, 7000, 7600],
            tnm=[170, 205, 225, 245, 258, 252, 232, 210], eng_I=0.20, eng_fric=28, eng_brake=0.018, boost_gain=0.0, spool=0.45,
            gears=[3.626, 2.188, 1.541, 1.213, 1.0, 0.767], fd=4.30, eff=0.88, clutch=520, front_split=0.0, brake=2500, bias=0.64,
            hb=4200, max_steer=54, cd=0.33, area=2.05, awd=False)
CARS = {
    "hachi": dict(mass=1275, com_h=0.40, com_z=0.04, wheelbase=2.575, front_axle_z=1.30, track_f=1.52, track_r=1.55, r=0.325, arb_f=13000, arb_r=8000,
                  grip_f=1.16, grip_r=1.02, slide_r=0.80, tnm=[190, 228, 252, 268, 290, 300, 288, 262], clutch=560, max_steer=56),
    "kaiju": dict(mass=1505, com_h=0.43, com_z=0.06, wheelbase=2.47, front_axle_z=1.24, track_f=1.594, track_r=1.589, r=0.345, arb_f=17000, arb_r=10000,
                  grip_f=1.20, grip_r=1.10, slide_r=0.78, idle=850, redline=7000, revlimit=7200, trpm=[1000, 2000, 3000, 4000, 5000, 6000, 6800, 7200],
                  tnm=[260, 320, 345, 352, 350, 336, 305, 280], boost_gain=0.95, spool=0.55, gears=[3.727, 2.048, 1.371, 1.0, 0.819, 0.637], fd=3.69,
                  clutch=980, max_steer=52, brake=2900),
    "zenkai": dict(mass=1590, com_h=0.44, com_z=0.08, wheelbase=2.55, front_axle_z=1.30, track_f=1.56, track_r=1.59, r=0.345, arb_f=16000, arb_r=9500,
                   grip_f=1.18, grip_r=1.08, slide_r=0.82, idle=800, redline=6800, revlimit=7000, trpm=[1000, 1800, 2800, 3800, 4800, 5800, 6500, 7000],
                   tnm=[270, 330, 360, 362, 355, 330, 300, 270], boost_gain=0.75, spool=0.40, gears=[3.794, 2.324, 1.624, 1.271, 1.0, 0.794], fd=3.69,
                   clutch=900, max_steer=58, brake=2900),
    "raijin": dict(mass=1475, com_h=0.46, com_z=0.18, wheelbase=2.64, front_axle_z=1.38, track_f=1.53, track_r=1.56, r=0.33, arb_f=12000, arb_r=11000,
                   grip_f=1.16, grip_r=1.10, slide_f=0.86, slide_r=0.84, idle=900, redline=7000, revlimit=7300, trpm=[1000, 2000, 3000, 4000, 5000, 6000, 6800, 7300],
                   tnm=[190, 250, 280, 290, 290, 280, 255, 230], boost_gain=0.70, spool=0.35, gears=[3.538, 2.238, 1.535, 1.162, 0.92, 0.756], fd=3.94,
                   clutch=760, max_steer=48, awd=True, front_split=0.30),
    "tsubame": dict(mass=1065, com_h=0.38, com_z=0.02, wheelbase=2.31, front_axle_z=1.18, track_f=1.495, track_r=1.505, r=0.31, arb_f=11000, arb_r=6500,
                    grip_f=1.14, grip_r=1.02, slide_r=0.78, idle=900, redline=7500, revlimit=7700, tnm=[150, 182, 200, 212, 222, 228, 214, 190],
                    gears=[3.709, 2.190, 1.536, 1.177, 1.0, 0.832], fd=3.90, clutch=420, max_steer=55, brake=2100),
}


class Car:
    def __init__(self, cid, assist=0):
        s = dict(BASE); s.update(CARS[cid]); self.s = s; self.id = cid; self.assist = assist
        L = s["wheelbase"] + 1.7; W = max(s["track_f"], s["track_r"]) + 0.3
        self.Iz = s["mass"] * (W * W + L * L) / 12 * 0.85
        self.a = s["front_axle_z"] - s["com_z"]            # CoM -> front axle
        self.b = s["wheelbase"] - self.a                   # CoM -> rear axle
        self.x = self.y = self.psi = 0.0
        self.vx = self.vy = self.r = 0.0                   # body frame: x forward, y left; r yaw rate (CCW +)
        self.w = np.zeros(4)                               # FL FR RL RR
        self.eng = s["idle"] / RAD2RPM
        self.gear = 1; self.shift_t = 0.0; self.pending = 1
        self.boost = 0.0; self.limiter = False; self.lim_t = 0.0
        self.ax = self.ay = 0.0
        self.steer = 0.0
        self.Ia_r = s["wheel_I"] * 2 + 0.15; self.Ia_f = s["wheel_I"] * 2 + 0.10

    def torque(self, rpm):
        s = self.s; tr, tn = s["trpm"], s["tnm"]
        if rpm <= tr[0]: return tn[0] * min(1, rpm / tr[0] + 0.3)
        for i in range(1, len(tr)):
            if rpm <= tr[i]:
                u = (rpm - tr[i - 1]) / (tr[i] - tr[i - 1]); return tn[i - 1] + (tn[i] - tn[i - 1]) * u
        return tn[-1]

    def ratio(self, g):
        if g == 0: return 0.0
        if g < 0: return -3.4 * self.s["fd"]
        return self.s["gears"][min(g - 1, len(self.s["gears"]) - 1)] * self.s["fd"]

    @property
    def speed(self): return math.hypot(self.vx, self.vy)

    @property
    def beta_deg(self):
        # drift angle: + when velocity is to the RIGHT of heading (Unity convention). Body y is LEFT here.
        return math.degrees(math.atan2(-self.vy, self.vx)) if math.hypot(self.vx, self.vy) > 1.5 else 0.0

    def tire(self, front, Fz, vlong, vlat, omega):
        s = self.s
        den = max(abs(vlong), 3.0)
        slip_long = omega * s["r"] - vlong
        sxn = (slip_long / den) / s["peak_sx"]
        syn = (vlat / den) / math.tan(math.radians(s["peak_alpha"]))
        sN = math.hypot(sxn, syn)
        fz0 = s["mass"] * G / 4
        mu = (s["grip_f"] if front else s["grip_r"]) * (1 - s["load_sens"] * (Fz / fz0 - 1))
        slide = s["slide_f"] if front else s["slide_r"]
        f = sN * (2 - sN) if sN < 1 else slide + (1 - slide) * math.exp(-(sN - 1) * s["falloff"])
        F = mu * Fz * f
        if sN < 1e-6: return 0.0, 0.0
        fx = F * sxn / sN; fy = -F * syn / sN
        fx -= math.copysign(1, vlong) * Fz * 0.012 * min(1, abs(vlong))
        return fx, fy

    def step(self, dt, steer_in, thr, brk, hb, clutch_in=0.0, auto=True):
        s = self.s
        # steering (same rules as C#)
        speed = abs(self.vx)
        v = max(speed, 1.0)
        lock_speed = min(s["max_steer"], (s["wheelbase"] * 1.1 * G / (v * v) * 180 / math.pi + s["peak_alpha"]) * 1.6)
        beta = self.beta_deg if self.vx > 1 else 0.0
        lock = max(lock_speed, min(s["max_steer"], abs(beta) + 14))
        target = steer_in * lock
        if self.assist > 0 and self.vx > 3:
            gain = 0.5 if self.assist == 1 else 0.85
            target += beta * gain * (1 - abs(steer_in) * 0.6)
        target = max(-s["max_steer"], min(s["max_steer"], target))
        self.steer += max(-s["max_steer"] * 7 * dt, min(s["max_steer"] * 7 * dt, target - self.steer))
        delta = math.radians(self.steer)   # + = right turn (clockwise) -> in body frame (y left) that's negative angle

        # gearbox (auto)
        if self.shift_t > 0:
            self.shift_t -= dt
            if self.shift_t <= 0: self.gear = self.pending
        elif auto:
            rpm = self.eng * RAD2RPM
            if self.gear >= 1 and rpm > s["redline"] * 0.985 and self.gear < len(s["gears"]) and thr > 0.2:
                self.pending = self.gear + 1; self.shift_t = 0.11
            elif self.gear > 1:
                below = rpm * self.ratio(self.gear - 1) / self.ratio(self.gear)
                if below < s["redline"] * 0.80 and rpm < s["redline"] * 0.52: self.pending = self.gear - 1; self.shift_t = 0.11

        # loads (quasi-static transfer)
        m = s["mass"]; h = s["com_h"]; L = s["wheelbase"]
        Fzf = m * G * self.b / L - m * self.ax * h / L
        Fzr = m * G * self.a / L + m * self.ax * h / L
        roll_f = s["arb_f"] / (s["arb_f"] + s["arb_r"]) * 0.5 + 0.25
        dLat = m * self.ay * h
        dF = dLat * roll_f / s["track_f"]; dR = dLat * (1 - roll_f) / s["track_r"]
        # ay>0 means accel to the LEFT -> right wheels (FR, RR) loaded
        dF = max(-Fzf / 2, min(Fzf / 2, dF)); dR = max(-Fzr / 2, min(Fzr / 2, dR))
        Fz = np.array([Fzf / 2 - dF, Fzf / 2 + dF, Fzr / 2 - dR, Fzr / 2 + dR]).clip(0, None)

        # wheel positions (body frame: x fwd, y left): FL, FR, RL, RR
        pos = [(self.a, s["track_f"] / 2), (self.a, -s["track_f"] / 2), (-self.b, s["track_r"] / 2), (-self.b, -s["track_r"] / 2)]
        ang = [-delta, -delta, 0.0, 0.0]
        vl = []; vt = []
        for i in range(4):
            px, py = pos[i]
            cvx = self.vx - self.r * py; cvy = self.vy + self.r * px
            c, sn = math.cos(ang[i]), math.sin(ang[i])
            vlong = cvx * c + cvy * sn
            vlat_left = -cvx * sn + cvy * c
            vl.append(vlong); vt.append(-vlat_left)   # tire model wants lateral velocity to the RIGHT positive

        # drivetrain substeps
        N = 8; h_ = dt / N
        ratio = 0.0 if self.shift_t > 0 else self.ratio(self.gear)
        throttle = thr if self.gear >= 0 else brk
        if self.shift_t > 0: throttle = 0.55 if self.pending < self.gear else 0.0
        if self.limiter: throttle = 0.0
        rpm = self.eng * RAD2RPM
        tb = throttle * min(1, max(0, (rpm - 2000) / 2600)) if s["boost_gain"] > 0 else 0
        self.boost += max(-dt / 0.12, min(dt / s["spool"], tb - self.boost))
        uclutch = clutch_in
        if hb and self.assist > 0: uclutch = max(uclutch, 0.85)
        fs = s["front_split"] if s["awd"] else 0.0; rs = 1 - fs
        acc_fx = np.zeros(4); acc_fy = np.zeros(4)
        for _ in range(N):
            rpm = self.eng * RAD2RPM
            Te = self.torque(max(rpm, s["idle"])) * (1 + self.boost * s["boost_gain"]) * throttle
            Te -= s["eng_fric"] * min(1, rpm / 2000) + s["eng_brake"] * self.eng * (1 - throttle)
            if rpm < s["idle"]: Te += (s["idle"] - rpm) * 0.35
            dw = self.w[2] * rs + self.w[0] * fs
            matched = abs(dw * ratio) * RAD2RPM
            auto_c = min(1, max(0, max((rpm - s["idle"] * 1.05) / 900, (matched - s["idle"] * 1.1) / 300)))
            cap = s["clutch"] * (1 - uclutch) * auto_c
            Tc = 0.0
            if ratio != 0 and cap > 0:
                Id = self.Ia_r * rs + self.Ia_f * fs
                rel = self.eng - dw * ratio
                Ieff = 1 / (1 / s["eng_I"] + ratio * ratio / max(0.05, Id))
                Tc = max(-cap, min(cap, rel * Ieff / h_))
            self.eng = max(self.eng + (Te - Tc) / s["eng_I"] * h_, s["idle"] * 0.6 / RAD2RPM)
            Td = Tc * ratio * s["eff"]
            f = [self.tire(i < 2, Fz[i], vl[i], vt[i], self.w[i]) for i in range(4)]
            fx = np.array([q[0] for q in f]); fy = np.array([q[1] for q in f])

            def brake_t(i):
                pedal = thr if self.gear < 0 else brk
                t = pedal * s["brake"] * (s["bias"] if i < 2 else 1 - s["bias"])
                if i >= 2 and hb: t += s["hb"]
                return t

            def apply(om, dlt):
                return 0.0 if abs(om) <= dlt else om - math.copysign(dlt, om)
            # rear locked axle
            net = Td * rs - (fx[2] + fx[3]) * s["r"]
            om = self.w[2] + net / self.Ia_r * h_
            om = apply(om, (brake_t(2) + brake_t(3)) / self.Ia_r * h_)
            self.w[2] = self.w[3] = om
            if s["awd"]:
                net = Td * fs - (fx[0] + fx[1]) * s["r"]
                om = self.w[0] + net / self.Ia_f * h_
                om = apply(om, (brake_t(0) + brake_t(1)) / self.Ia_f * h_)
                self.w[0] = self.w[1] = om
            else:
                for i in (0, 1):
                    om = self.w[i] + (-fx[i] * s["r"]) / s["wheel_I"] * h_
                    self.w[i] = apply(om, brake_t(i) / s["wheel_I"] * h_)
            acc_fx += fx; acc_fy += fy
        fx = acc_fx / N; fy = acc_fy / N
        rpm = self.eng * RAD2RPM
        if self.limiter:
            self.lim_t -= dt
            if self.lim_t <= 0 and rpm < s["revlimit"] - 150: self.limiter = False
        elif rpm > s["revlimit"]: self.limiter = True; self.lim_t = 0.055

        # forces to body frame (fy is to the RIGHT of the wheel)
        FX = FY = MZ = 0.0
        for i in range(4):
            c, sn = math.cos(ang[i]), math.sin(ang[i])
            fyl = -fy[i]
            bx = fx[i] * c - fyl * sn
            by = fx[i] * sn + fyl * c
            px, py = pos[i]
            FX += bx; FY += by; MZ += px * by - py * bx
        v2 = self.vx ** 2 + self.vy ** 2
        if v2 > 0.01:
            q = 0.5 * 1.225 * v2 * s["cd"] * s["area"]; v = math.sqrt(v2)
            FX -= q * self.vx / v; FY -= q * self.vy / v
        ax = FX / m; ay = FY / m
        self.ax, self.ay = ax, ay
        # integrate in body frame with rotation terms
        self.vx += (ax + self.r * self.vy) * dt
        self.vy += (ay - self.r * self.vx) * dt
        self.r += MZ / self.Iz * dt
        self.psi += self.r * dt
        c, sn = math.cos(self.psi), math.sin(self.psi)
        self.x += (self.vx * c - self.vy * sn) * dt
        self.y += (self.vx * sn + self.vy * c) * dt

    @property
    def yaw_rate_unity(self): return -self.r   # Unity: + = clockwise (right turn)


def expert(car, beta_target=35.0, R=25.0, state={}):
    """Closed-loop drift driver: front wheels track the velocity vector + yaw-rate correction; throttle holds the angle."""
    beta = car.beta_deg; a = abs(beta); sgn = 1 if beta >= 0 else -1
    v = max(car.speed, 1.0)
    r_target = sgn * v / R                      # Unity sign: beta>0 (car rotated left) <-> turning left -> yaw rate negative
    r = car.yaw_rate_unity
    yaw_err = (-r_target) - r
    steer_deg = beta + yaw_err * 9.0
    prev = state.get("a", a); da = (a - prev) * 120; state["a"] = a
    thr = 0.55 + (beta_target - a) * 0.035 - da * 0.006
    return max(-1, min(1, steer_deg / car.s["max_steer"])), max(0, min(1, thr))


def run_tests(cid):
    dt = 1 / 120
    out = []
    # accel
    car = Car(cid); t = 0; t100 = None
    while t < 12:
        car.step(dt, -car.yaw_rate_unity * 0.3, 1, 0, False); t += dt
        if t100 is None and car.vx * 3.6 >= 100: t100 = t
    out.append(f"0-100 {t100 if t100 else -1:.2f}s v@12s {car.vx * 3.6:.0f} km/h gear {car.gear}")
    # skidpad
    car = Car(cid); car.vx = 16.7; car.w[:] = 16.7 / car.s["r"]; maxlat = 0; target = 16.7; t = 0
    while t < 12:
        target += dt * 0.6; err = target - car.vx
        car.step(dt, 0.55, min(1, max(0, 0.3 + err * 0.3)), min(1, max(0, -err * 0.2)), False); t += dt
        if abs(car.beta_deg) < 12: maxlat = max(maxlat, abs(car.r * car.vx) / G)
    out.append(f"skidpad {maxlat:.2f} g")
    for kick in (False, True):
        car = Car(cid); car.vx = 19.5; car.w[:] = 19.5 / car.s["r"]; car.eng = 19.5 / car.s["r"] * car.ratio(2) * RAD2RPM / RAD2RPM; car.gear = 2
        car.eng = car.w[2] * car.ratio(2)
        t = 0; peak = 0
        while t < 0.55:
            if kick: car.step(dt, -0.85, 1, 0, False, 1.0 if t < 0.3 else 0.0)
            else: car.step(dt, -0.9, 0.4, 0, t < 0.35)
            t += dt; peak = max(peak, abs(car.beta_deg))
        after = abs(car.beta_deg)
        hold = spun = 0; s = n = 0; t = 0; st = {}
        while t < 8:
            a = abs(car.beta_deg)
            steer, thr = expert(car, 35.0, 28.0, st)
            car.step(dt, steer, thr, 0, False); t += dt
            if 15 < a < 70 and car.speed * 3.6 > 25: hold += dt
            if a > 100: spun += dt
            if a > 10: s += a; n += 1
        out.append(f"drift({'kick' if kick else 'hb'}) peak {peak:.0f} after {after:.0f} hold {hold:.1f}/8 mean {s / max(n, 1):.0f} spin {'YES' if spun > 0.3 else 'no'} v {car.speed * 3.6:.0f}")
    return out


def trace(cid, mode="hb"):
    dt = 1 / 120
    car = Car(cid); car.vx = 19.5; car.w[:] = 19.5 / car.s["r"]; car.gear = 2; car.eng = car.w[2] * car.ratio(2)
    t = 0; ST = {}
    while t < 6:
        if t < 0.55:
            if mode == "kick": args = (-0.85, 1, 0, False, 1.0 if t < 0.3 else 0.0)
            else: args = (-0.9, 0.4, 0, t < 0.35)
        else:
            steer, thr = expert(car, 35.0, 28.0, ST)
            args = (steer, thr, 0, False)
        car.step(dt, *args); t += dt
        if int(t * 120) % 12 == 0:
            print(f"t={t:4.2f} beta={car.beta_deg:6.1f} r={car.yaw_rate_unity:5.2f} v={car.speed*3.6:5.1f} steer={car.steer:6.1f} thr={args[1]:.2f} rpm={car.eng*RAD2RPM:5.0f} g={car.gear} wr={car.w[2]*car.s['r']:5.1f} vx={car.vx:5.1f}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "trace":
        trace(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "hb"); sys.exit()
    ids = sys.argv[1:] or list(CARS)
    for cid in ids:
        print(f"== {cid}")
        for line in run_tests(cid): print("  ", line)
