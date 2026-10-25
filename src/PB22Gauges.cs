using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace PB22Trident
{
    // Turns the PB-22 cockpit's analog needles and lights its panel lamps for the aircraft you are flying.
    // Read-only: it reads the game's own flight, engine, fuel, power and damage state and only moves needles and
    // switches lamp images. No Harmony, no network, no files. Gauges with no game signal (oil, hydraulics) sit in the
    // green with a slow drift and sag or drop out as the parts behind them are damaged or lost.
    public class PB22Gauges : MonoBehaviour
    {
        private class Needle { public Transform t; public Quaternion rest; public float angle; }

        private Type hudType, aircraftType, fuelTankType, unitPartType, jammerType, imageType;
        private FieldInfo hudInstance;
        private Component aircraft;
        private readonly Dictionary<string, Needle> needles = new Dictionary<string, Needle>();
        private readonly Dictionary<string, Behaviour> lamps = new Dictionary<string, Behaviour>();
        private readonly List<Transform> balls = new List<Transform>();
        private readonly Dictionary<string, Needle> pedals = new Dictionary<string, Needle>();
        private bool reported, failed;
        private Component engL, engR, power;
        private readonly List<Component> tanks = new List<Component>(), jammers = new List<Component>();
        private readonly List<Component> hydParts = new List<Component>(), elecParts = new List<Component>();
        private float fuelCapacity, lastFuel = -1f, fuelFlow, hydF = 1f, oilF = 1f, voltF = 1f, nextUpdate, lastUpdate, nextLampScan, lastFuelTime;
        private readonly float seed = UnityEngine.Random.value * 100f;

        private static readonly string[] HydNames = { "wing", "aileron", "flap", "elevator", "rudder", "tail" };
        private static readonly string[] ElecNames = { "fuselage", "cockpit", "nose" };

        private void Update()
        {
            if (Time.unscaledTime < nextUpdate) return;
            float dt = Mathf.Clamp(Time.unscaledTime - lastUpdate, 0.001f, 0.5f);
            lastUpdate = Time.unscaledTime; nextUpdate = Time.unscaledTime + 1f/30f;
            try
            {
                var ac = PlayerAircraft();
                if (ac == null || !ac.name.StartsWith("PB22")) { aircraft = null; return; }
                if (ac != aircraft) Bind(ac);
                if (Time.unscaledTime >= nextLampScan) { nextLampScan = Time.unscaledTime + 2f; ScanLamps(); }
                Drive(dt);
                if (!reported && lamps.Count > 0)
                {   // one line per aircraft for the BepInEx log, so a test flight shows what was found
                    reported = true;
                    Plugin.Log.LogInfo("PB-22 gauges on " + ac.name + ": " + needles.Count + " needles, " + balls.Count + " attitude balls, " + pedals.Count + " pedals, "
                        + lamps.Count + " lamps, engines " + (engL != null) + "/" + (engR != null) + ", " + tanks.Count + " fuel tanks, "
                        + hydParts.Count + "/" + elecParts.Count + " hyd/elec parts, power " + (power != null));
                }
            }
            catch (Exception e)
            {
                if (!failed) { failed = true; Plugin.Log.LogWarning("PB-22 gauges stopped: " + e); }
                aircraft = null;
            }
        }

        private Component PlayerAircraft()
        {
            if (hudType == null)
            {
                hudType = R.T("CombatHUD"); aircraftType = R.T("Aircraft"); fuelTankType = R.T("FuelTank");
                unitPartType = R.T("UnitPart"); jammerType = R.T("JammingPod"); imageType = R.T("UnityEngine.UI.Image");
                if (hudType != null)
                    for (var t = hudType.BaseType; t != null && hudInstance == null; t = t.BaseType)
                        hudInstance = t.GetField("i", BindingFlags.Static | BindingFlags.Public | BindingFlags.FlattenHierarchy);
            }
            if (hudInstance == null) return null;
            var hud = hudInstance.GetValue(null);
            return hud == null ? null : R.Get(hud, "aircraft") as Component;
        }

        private void Bind(Component ac)
        {
            aircraft = ac; needles.Clear(); lamps.Clear(); balls.Clear(); pedals.Clear(); reported = false; tanks.Clear(); jammers.Clear(); hydParts.Clear(); elecParts.Clear();
            lastFuel = -1f; lastFuelTime = 0f; fuelFlow = 0f; hydF = oilF = voltF = 1f; nextLampScan = 0f;
            foreach (var r in R.Roots(ac)) foreach (var t in r.GetComponentsInChildren<Transform>(true))
            {
                if (t.name.StartsWith("PB22_gauge_")) needles[t.name.Substring(11)] = new Needle { t = t, rest = t.localRotation };
                if (t.name.StartsWith("PB22_adi_")) balls.Add(t);
                if (t.name.StartsWith("PB22_pedal_")) pedals[t.name.Substring(11)] = new Needle { t = t, rest = t.localRotation };
                if (t.name == "engine1") engL = Engine(t);
                if (t.name == "engine3") engR = Engine(t);
            }
            if (fuelTankType != null) foreach (var r in R.Roots(ac)) tanks.AddRange(r.GetComponentsInChildren(fuelTankType, true));
            fuelCapacity = 0f;
            foreach (var tk in tanks) fuelCapacity += Num(Call(tk, "GetCapacity"));
            if (jammerType != null) foreach (var r in R.Roots(ac)) jammers.AddRange(r.GetComponentsInChildren(jammerType, true));
            if (unitPartType != null)
                foreach (var r in R.Roots(ac)) foreach (var p in r.GetComponentsInChildren(unitPartType, true))
                {
                    string n = p.name.ToLowerInvariant();
                    if (Array.Exists(HydNames, s => n.StartsWith(s))) hydParts.Add(p);
                    else if (Array.Exists(ElecNames, s => n.StartsWith(s))) elecParts.Add(p);
                }
            power = Call(ac, "GetPowerSupply") as Component;
        }

        private static Component Engine(Transform t)
        {
            foreach (var c in t.GetComponents<Component>()) if (c != null && c.GetType().Name == "Turbofan") return c;
            return null;
        }

        // the tac screen canvas is spawned by the stock Cockpit; its lamp cells are found by name
        private void ScanLamps()
        {
            if (imageType == null) return;
            foreach (var root in new[] { "Annunciators", "PanelLamps" })
            {
                var go = GameObject.Find(root); if (go == null) continue;
                foreach (Transform cell in go.transform)
                {
                    var lit = cell.Find("lit"); if (lit == null) continue;
                    var img = lit.GetComponent(imageType) as Behaviour; if (img == null) continue;
                    lamps[cell.name] = img;
                }
            }
        }

        private void Drive(float dt)
        {
            var ac = aircraft; float now = Time.unscaledTime;
            // ---- flight: the same values the centre display shows
            float kt = R.Fl(ac, "speed") * 1.94384f, ft = Mathf.Max(R.Fl(ac, "radarAlt"), 0f) * 3.28084f;
            Set("asi_L", -150f + 300f * Mathf.Clamp01(kt / 1200f), dt, 6f); Set("asi_R", -150f + 300f * Mathf.Clamp01(kt / 1200f), dt, 6f);
            foreach (var s in new[] { "_L", "_R" })
            {
                Set("alt" + s, ft % 1000f / 1000f * 360f, dt, 0f); Set("altk" + s, ft % 10000f / 10000f * 360f, dt, 0f);
            }
            Set("hdg", -ac.transform.eulerAngles.y, dt, 0f);
            // attitude balls: held level with the real horizon, turned with the aircraft's heading (a gyro ball seen from the seat)
            var flat = Vector3.ProjectOnPlane(ac.transform.forward, Vector3.up);
            if (flat.sqrMagnitude < 1e-4f) flat = Vector3.ProjectOnPlane(-ac.transform.up * Mathf.Sign(ac.transform.forward.y), Vector3.up);
            var levelRot = Quaternion.LookRotation(flat.normalized, Vector3.up);
            foreach (var b in balls) if (b != null) b.rotation = levelRot;
            // ---- engines: the same RPM % and thrust kN the engine rows show
            float rpmL = Num(Call(engL, "GetRPMRatio")), rpmR = Num(Call(engR, "GetRPMRatio"));
            Set("rpm_L", -135f + 270f * Mathf.Clamp01(rpmL), dt, 4f); Set("rpm_R", -135f + 270f * Mathf.Clamp01(rpmR), dt, 4f);
            Set("thr_L", -135f + 270f * Mathf.Clamp01(Num(Call(engL, "GetThrust")) / 160000f), dt, 4f);
            Set("thr_R", -135f + 270f * Mathf.Clamp01(Num(Call(engR, "GetThrust")) / 160000f), dt, 4f);
            float condL = EngineCondition(engL), condR = EngineCondition(engR);
            bool running = condL > 0f && rpmL > 0.05f || condR > 0f && rpmR > 0.05f;
            // ---- fuel: level, and real burn from how fast the level falls (tonnes per hour)
            float level = Num(Call(ac, "GetFuelLevel"));
            float gdt = Time.unscaledTime - lastFuelTime;
            if (gdt > 0.25f)
            {   // sampled over game time so a pause reads no burn
                if (lastFuel >= 0f && fuelCapacity > 0f)
                {
                    float burn = Mathf.Max(lastFuel - level, 0f) * fuelCapacity / gdt * 3.6f;
                    fuelFlow = Mathf.Lerp(fuelFlow, burn, 1f - Mathf.Exp(-gdt / 2f));
                }
                lastFuel = level; lastFuelTime = Time.unscaledTime;
            }
            Set("fuel", -120f + 240f * Mathf.Clamp01(level), dt, 3f);
            Set("ff", -135f + 270f * Mathf.Clamp01(fuelFlow / 10f), dt, 3f);
            // ---- controls
            var inputs = Call(ac, "GetInputs");
            float thr = R.Fl(inputs, "throttle"), brake = R.Fl(inputs, "brake");
            if (float.IsNaN(thr)) thr = 0f; if (float.IsNaN(brake)) brake = 0f;
            float yaw = R.Fl(inputs, "yaw"); if (float.IsNaN(yaw)) yaw = 0f;
            foreach (var kv in pedals)
            {   // pedals swing on their cross shaft: the right pedal goes forward with right rudder, the left with left
                if (kv.Value.t == null) continue;
                float sgn = kv.Key.EndsWith("R") ? 1f : -1f;
                kv.Value.angle = Mathf.Lerp(kv.Value.angle, -12f * sgn * Mathf.Clamp(yaw, -1f, 1f), 1f - Mathf.Exp(-dt * 10f));
                kv.Value.t.localRotation = kv.Value.rest * Quaternion.AngleAxis(kv.Value.angle, Vector3.right);
            }
            float noz = thr < 0.8f ? 0.35f - 0.2f * thr / 0.8f : 0.15f + 0.85f * (thr - 0.8f) / 0.2f;
            Set("noz", -135f + 270f * Mathf.Clamp01(noz), dt, 2f);
            int gear = (int)R.Fl(ac, "gearState");          // 2 locked down, 3 retracting, 4 extending
            bool gearDown = gear == 2, gearMoving = gear == 3 || gear == 4;
            Set("brk", -135f + 270f * (gearDown ? 0.15f + 0.7f * Mathf.Clamp01(brake) : 0f), dt, 3f);
            // ---- systems with no game signal: green drift, sag with damage, drop when lost
            hydF = Toward(hydF, Health(hydParts), dt);
            oilF = Toward(oilF, Mathf.Min(Factor(condL), Factor(condR)), dt);
            float charge = power != null ? Mathf.Clamp01(Num(Call(power, "GetCharge"))) : 1f;
            float voltTarget = Health(elecParts) * (running ? 1f : 0.3f);
            voltF = Toward(voltF, voltTarget, dt);
            Set("hyd", -135f + 270f * (0.71f + Wiggle(1f, hydF)) * hydF, dt, 3f);
            Set("oil", -135f + 270f * (0.40f + 0.25f * Mathf.Max(rpmL, rpmR) + Wiggle(2f, oilF)) * oilF, dt, 3f);
            float volts = (22f + 7f * charge) * voltF + Wiggle(3f, voltF) * 40f;
            Set("volt", -135f + 270f * Mathf.Clamp01(volts / 40f), dt, 3f);
            // ---- lamps
            bool flash = Mathf.Repeat(now * 3.2f, 1f) < 0.5f;
            bool fireL = false, fireR = false;
            foreach (var tk in tanks)
            {
                if (tk == null || R.Fl(tk, "onFire") != 1f) continue;
                if (ac.transform.InverseTransformPoint(tk.transform.position).x < 0f) fireL = true; else fireR = true;
            }
            bool jamming = false;
            foreach (var j in jammers) if (j != null && ((Behaviour)j).enabled) jamming = true;
            Lamp("lamp_HYD", hydF < 0.999f);
            Lamp("lamp_ELEC", volts < 24.8f);
            Lamp("lamp_FUEL FIRE", (fireL || fireR) && flash);
            Lamp("lamp_IFF", jamming);
            bool gearLamp = gearDown || gearMoving && flash;
            foreach (var n in new[] { "panel_GEAR", "panel_NOSE", "panel_LEFT", "panel_RIGHT" }) Lamp(n, gearLamp);
            Lamp("panel_FLAP", gearDown);                    // stock flaps follow the gear
            Lamp("panel_FIRE L", (fireL || condL <= 0f && engL != null) && flash);
            Lamp("panel_FIRE R", (fireR || condR <= 0f && engR != null) && flash);
        }

        // needle angle in degrees, clockwise seen by the pilot from 12 o'clock; rate = smoothing (0 = direct)
        private void Set(string id, float angle, float dt, float rate)
        {
            Needle n;
            if (!needles.TryGetValue(id, out n) || n.t == null) return;
            n.angle = rate <= 0f ? angle : Mathf.Lerp(n.angle, angle, 1f - Mathf.Exp(-dt * rate));
            n.t.localRotation = n.rest * Quaternion.AngleAxis(-n.angle, Vector3.forward);   // pivot z points into the panel
        }

        private void Lamp(string name, bool on)
        {
            Behaviour b;
            if (lamps.TryGetValue(name, out b) && b != null && b.enabled != on) b.enabled = on;
        }

        // slow drift of a few percent of the dial, larger once the system is hurt
        private float Wiggle(float k, float f)
        {
            float amp = f >= 0.999f ? 0.025f : 0.06f;
            return (Mathf.PerlinNoise(Time.unscaledTime * 0.12f + seed, k * 7.3f) - 0.5f) * 2f * amp;
        }

        private static float Toward(float v, float target, float dt) { return Mathf.MoveTowards(v, target, dt); }

        // part health 0..1 to gauge factor: green above 60 %, sagging below, gone under 20 %
        private static float Factor(float h)
        {
            if (h >= 0.6f) return 1f;
            if (h < 0.2f) return 0f;
            return 0.55f + 0.45f * (h - 0.2f) / 0.4f;
        }

        private float Health(List<Component> parts)
        {
            float worst = 1f;
            foreach (var p in parts)
            {
                if (p == null) { worst = 0f; continue; }
                var det = Call(p, "IsDetached");
                float h = det is bool && (bool)det ? 0f : R.Fl(p, "hitPoints") / 100f;
                if (!float.IsNaN(h)) worst = Mathf.Min(worst, h);
            }
            return Factor(worst);
        }

        private static float EngineCondition(Component e)
        {
            if (e == null) return 0f;
            float c = R.Fl(e, "condition");
            return float.IsNaN(c) ? 1f : c;
        }

        private static readonly Dictionary<string, MethodInfo> methods = new Dictionary<string, MethodInfo>();
        private static object Call(object o, string name)
        {
            if (o == null) return null;
            var t = o.GetType(); string key = t.FullName + "." + name;
            MethodInfo m;
            if (!methods.TryGetValue(key, out m))
            {
                m = t.GetMethod(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic, null, Type.EmptyTypes, null);
                methods[key] = m;
            }
            try { return m == null ? null : m.Invoke(o, null); } catch { return null; }
        }

        private static float Num(object o)
        {
            if (o is float) return (float)o;
            if (o is int) return (int)o;
            return 0f;
        }
    }
}
