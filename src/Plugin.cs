using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using BepInEx;
using BepInEx.Configuration;
using HarmonyLib;
using UnityEngine;

namespace PB22Trident
{
    // Carries the PB-22 Trident bundle (embedded .nobp, loaded by Blueprinter) and spins the engine fans. Test builds
    // (-p:DefineConstants=FLIGHTLOG) also write a flight log of the player's aircraft for performance tuning.
    [BepInPlugin("nick.nuclearoption.pb22trident", "PB-22 Trident", "0.9.4")]
    [BepInDependency("com.nikkorap.blueprinter", BepInDependency.DependencyFlags.SoftDependency)]
    public class Plugin : BaseUnityPlugin
    {
#if FLIGHTLOG
        internal static ConfigEntry<bool> FlightLog;
        internal static ConfigEntry<float> FlightLogRate;
#endif
        internal static BepInEx.Logging.ManualLogSource Log;
        internal static ConfigEntry<bool> DebugLog, LandingLog;

        private void Awake()
        {
            Log = Logger;
            DebugLog = Config.Bind("Testing", "DebugLog", false, "Write PB-22 fan diagnostics to the BepInEx log.");
            LandingLog = Config.Bind("Testing", "LandingLog", true, "Write one line to the BepInEx log each time an AI PB-22 changes landing phase.");
#if FLIGHTLOG
            FlightLog = Config.Bind("Testing", "FlightLog", false,
                "Write a CSV flight log of the aircraft you fly (any type) to BepInEx/PB22_flightlogs. For performance tuning.");
            FlightLogRate = Config.Bind("Testing", "FlightLogRate", 5f, "Flight log samples per second.");
#endif
            var go = new GameObject("PB22Runtime");
            DontDestroyOnLoad(go);
            go.hideFlags = HideFlags.HideAndDontSave;
            go.AddComponent<PB22Runtime>();
            go.AddComponent<PB22Gauges>();
            TakeoffFix.Apply(Logger);
            LandingFix.Apply(Logger);
            Logger.LogInfo("PB-22 Trident loaded");
        }
    }

    // The stock AI holds its nose on a runway point until 70% of takeoff speed, which pushes the PB-22's nose down hard
    // late in its long ground roll. Keep the elevator neutral on the ground until the AI starts its rotation.
    internal static class TakeoffFix
    {
        public static void Apply(BepInEx.Logging.ManualLogSource log)
        {
            try
            {
                var t = R.T("AIPilotTakeoffState");
                var m = t == null ? null : t.GetMethod("FixedUpdateState", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (m == null) { log.LogWarning("PB-22 takeoff fix: AI takeoff state not found"); return; }
                new Harmony("nick.nuclearoption.pb22trident.takeoff").Patch(m, postfix: new HarmonyMethod(typeof(TakeoffFix), nameof(Post)));
            }
            catch (Exception e) { log.LogWarning("PB-22 takeoff fix not applied: " + e.Message); }
        }

        private static void Post(object __instance, object __0)
        {
            try
            {
                var ac = R.Get(__0, "aircraft") as Component;
                if (ac == null || !ac.name.StartsWith("PB22Trident")) return;
                float alt = R.Fl(ac, "radarAlt");
                if (alt > 4f) return;
                var ci = R.Get(__instance, "controlInputs");
                var f = ci == null ? null : ci.GetType().GetField("pitch");
                if (f == null) return;
                float takeoff = R.Fl(R.Get(__instance, "aircraftParameters"), "takeoffSpeed");
                if (alt <= 1f && R.Fl(ac, "speed") < takeoff * 0.7f) { f.SetValue(ci, 0f); return; }
                // rotation: the stock AI aims 10 deg up at once and keeps pulling while the wheels are down, which drags the
                // nozzles on the runway (they touch at 6.4 deg). Pull gently and hold the nose at 5 deg until the jet climbs away.
                float pitchDeg = Mathf.Asin(Mathf.Clamp(ac.transform.forward.y, -1f, 1f)) * Mathf.Rad2Deg;
                // positive pitch input is nose down, so a pull is negative: cap the pull so it fades out at 5 deg
                float cmd = (float)f.GetValue(ci);
                float pull = Mathf.Clamp((5f - pitchDeg) * 0.15f, -0.5f, 0.35f);
                if (cmd < -pull) f.SetValue(ci, -pull);
            }
            catch { }
        }
    }

    // The stock landing AI reads height from the aircraft origin. The PB-22's main wheels sit 3.9 m behind it (Darkreach 1.7),
    // so in the landing attitude the origin rides half a metre or more above the wheels: the AI sinks hard to "touch down",
    // and the smallest bounce reads as more than 1 m and aborts the landing. While the landing logic runs, give it the
    // height of the main wheels instead; the aircraft's own value is put back straight after.
    internal static class LandingFix
    {
        private const float MainGearAft = 3.9f, OriginHeight = 2.85f, TouchedDown = 4f;  // AIPilotLandingState.LandingMode.Touched_Down
        private static FieldInfo radarAlt;
        private static Component rawAc;  // the aircraft whose height is swapped right now, and its own value
        private static float rawAlt;

        public static void Apply(BepInEx.Logging.ManualLogSource log)
        {
            try
            {
                var t = R.T("AIPilotLandingState");
                var m = t == null ? null : t.GetMethod("RunMode", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                var u = R.T("Unit");
                radarAlt = u == null ? null : u.GetField("radarAlt", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (m == null || radarAlt == null) { log.LogWarning("PB-22 landing fix: AI landing state not found"); return; }
                var h = new Harmony("nick.nuclearoption.pb22trident.landing");
                h.Patch(m, prefix: new HarmonyMethod(typeof(LandingFix), nameof(Pre)), postfix: new HarmonyMethod(typeof(LandingFix), nameof(Post)));
                var sw = t.GetMethod("SwitchMode", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (sw != null) h.Patch(sw, prefix: new HarmonyMethod(typeof(LandingFix), nameof(Switch)));
                var leave = t.GetMethod("LeaveState", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (leave != null) h.Patch(leave, prefix: new HarmonyMethod(typeof(LandingFix), nameof(Leave)));
                log.LogInfo("PB-22 landing fix applied");
            }
            catch (Exception e) { log.LogWarning("PB-22 landing fix not applied: " + e.Message); }
        }

        private static void Pre(object __instance, out float __state)
        {
            __state = float.NaN;
            try
            {
                var ac = R.Get(__instance, "aircraft") as Component;
                if (ac == null || !ac.name.StartsWith("PB22Trident")) return;
                float alt = (float)radarAlt.GetValue(ac);
                if (alt > 20f) return;
                __state = alt; rawAc = ac; rawAlt = alt;
                float wheels = WheelHeight(ac, alt);
                // on the runway the stock AI aborts as soon as it reads more than 1 m. With throttle closed and the nose
                // lowered the PB-22 settles back from a small bounce, so only a real climb (wheels above 2.5 m) aborts
                if (R.Fl(__instance, "landingMode") == TouchedDown) wheels -= 1.5f;
                radarAlt.SetValue(ac, Mathf.Max(wheels, 0f));
            }
            catch { }
        }

        // height of the main wheels: the origin the game measures from sits 3.9 m ahead of them and 2.85 m above the ground
        private static float WheelHeight(Component ac, float alt)
        {
            float pitch = Mathf.Asin(Mathf.Clamp(ac.transform.forward.y, -1f, 1f));
            return alt + OriginHeight * (1f - Mathf.Cos(pitch)) - MainGearAft * Mathf.Sin(pitch);
        }

        private static void Post(object __instance, float __state)
        {
            try
            {
                var ac = R.Get(__instance, "aircraft") as Component;
                if (!float.IsNaN(__state)) radarAlt.SetValue(ac, __state);
                rawAc = null;
                if (ac == null || !ac.name.StartsWith("PB22Trident") || R.Fl(__instance, "landingMode") != TouchedDown) return;
                // after touchdown the stock AI keeps aiming at the glideslope, so the nose stays up and the PB-22, still
                // above 300 km/h, flies off the runway again (0.4.9 video). Lower the nose onto the runway like a pilot would.
                // In this game a positive pitch input is stick forward (nose down), as the fly-by-wire and the yokes use it.
                var ci = R.Get(__instance, "controlInputs");
                var f = ci == null ? null : ci.GetType().GetField("pitch");
                if (f == null) return;
                float pitchDeg = Mathf.Asin(Mathf.Clamp(ac.transform.forward.y, -1f, 1f)) * Mathf.Rad2Deg;
                float push = Mathf.Clamp(pitchDeg * 0.15f, 0f, 0.6f);
                if ((float)f.GetValue(ci) < push) f.SetValue(ci, push);
            }
            catch { }
        }

        // one line per landing phase change, so a test flight shows exactly where and why a landing was given up
        private static void Switch(object __instance, object[] __args)
        {
            try
            {
                if (!Plugin.LandingLog.Value) return;
                var ac = R.Get(__instance, "aircraft") as Component;
                if (ac == null || !ac.name.StartsWith("PB22Trident")) return;
                var from = R.Get(__instance, "landingMode"); var to = __args[0];
                if (from == null || to == null || from.Equals(to)) return;
                var rb = R.Get(ac, "rb");
                float alt = rawAc == ac ? rawAlt : (float)radarAlt.GetValue(ac), pitch = Mathf.Asin(Mathf.Clamp(ac.transform.forward.y, -1f, 1f)) * Mathf.Rad2Deg;
                int traffic = -1;
                var list = Call(R.Get(R.Get(__instance, "runwayUsage"), "Runway"), "GetLandingList") as System.Collections.ICollection;
                if (list != null) traffic = list.Count - 1;
                Plugin.Log.LogInfo("PB-22 AI landing " + ac.name + "#" + ac.GetInstanceID() + ": " + from + " -> " + to
                    + ", wheels " + WheelHeight(ac, alt).ToString("F2") + " m, pitch " + pitch.ToString("F1") + ", speed " + (R.Fl(ac, "speed") * 3.6f).ToString("F0")
                    + " km/h, sink " + (rb == null ? "?" : (-((Vector3)Prop(rb, "velocity")).y).ToString("F1")) + " m/s, touchdown in " + R.Fl(__instance, "touchdownTime").ToString("F1")
                    + " s, ground " + R.Fl(__instance, "timeOnGround").ToString("F1") + " s, other landers " + traffic + ", mass " + (rb == null ? "?" : ((float)Prop(rb, "mass") / 1000f).ToString("F1")) + " t");
            }
            catch { }
        }

        // When a landed aircraft slows to taxi speed before it reaches a runway exit, the game hands it to the taxi logic
        // without taking it off the runway's landing list. Every aircraft behind it on final then sees it as traffic ahead
        // and gives up its landing. Take a PB-22 off the list itself once its landing run is over.
        private static void Leave(object __instance)
        {
            try
            {
                var ac = R.Get(__instance, "aircraft") as Component;
                if (ac == null || !ac.name.StartsWith("PB22Trident") || R.Fl(__instance, "landingMode") != TouchedDown) return;
                var runway = R.Get(R.Get(__instance, "runwayUsage"), "Runway");
                var mi = runway == null ? null : runway.GetType().GetMethod("DeregisterLanding", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (mi != null) mi.Invoke(runway, new object[] { ac });
            }
            catch { }
        }

        private static object Prop(object o, string name)
        {
            return o.GetType().GetProperty(name).GetValue(o, null);
        }

        private static object Call(object o, string name)
        {
            if (o == null) return null;
            var mi = o.GetType().GetMethod(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic, null, Type.EmptyTypes, null);
            return mi == null ? null : mi.Invoke(o, null);
        }
    }

    // Everything game-side is reached by reflection so the plugin needs no game assembly references.
    internal static class R
    {
        private static readonly Dictionary<string, Type> types = new Dictionary<string, Type>();
        private static readonly Dictionary<string, MemberInfo> members = new Dictionary<string, MemberInfo>();
        private const BindingFlags F = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        public static Type T(string name)
        {
            Type t;
            if (types.TryGetValue(name, out t)) return t;
            foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
            {
                t = a.GetType(name);
                if (t != null) break;
            }
            types[name] = t;
            return t;
        }

        public static object Get(object o, string name)
        {
            if (o == null) return null;
            var t = o.GetType();
            string key = t.FullName + "." + name;
            MemberInfo m;
            if (!members.TryGetValue(key, out m))
            {
                for (var tt = t; tt != null && m == null; tt = tt.BaseType)
                {
                    m = tt.GetField(name, F | BindingFlags.DeclaredOnly);
                    if (m == null) m = tt.GetProperty(name, F | BindingFlags.DeclaredOnly);
                }
                members[key] = m;
            }
            try
            {
                var f = m as FieldInfo;
                if (f != null) return f.GetValue(o);
                var p = m as PropertyInfo;
                if (p != null) return p.GetValue(o, null);
            }
            catch { }
            return null;
        }

        public static float Fl(object o, string name)
        {
            var v = Get(o, name);
            if (v is float) return (float)v;
            if (v is int) return (int)v;
            if (v is bool) return (bool)v ? 1f : 0f;
            if (v != null && v.GetType().IsEnum) return Convert.ToInt32(v);
            return float.NaN;
        }

        // At spawn the game moves every jointed part (wings, nacelles, cockpit, tail) out from under the aircraft to its own
        // root, so a search under the aircraft transform only sees the fuselage. Search the aircraft and every part instead.
        public static List<Transform> Roots(Component ac)
        {
            var l = new List<Transform> { ac.transform };
            var parts = Get(ac, "partLookup") as System.Collections.IEnumerable;
            if (parts != null)
                foreach (var p in parts)
                {
                    var c = p as Component;
                    if (c != null && !l.Contains(c.transform)) l.Add(c.transform);
                }
            l.RemoveAll(t => l.Exists(r => r != t && t.IsChildOf(r)));
            return l;
        }

        public static Transform Find(Component ac, string name)
        {
            foreach (var r in Roots(ac))
            {
                var t = Find(r, name);
                if (t != null) return t;
            }
            return null;
        }

        private static Transform Find(Transform t, string name)
        {
            if (t.name == name) return t;
            for (int i = 0; i < t.childCount; i++)
            {
                var r = Find(t.GetChild(i), name);
                if (r != null) return r;
            }
            return null;
        }

        public static Vector3 V3(object o, string name)
        {
            var v = Get(o, name);
            return v is Vector3 ? (Vector3)v : Vector3.zero;
        }
    }

    public class PB22Runtime : MonoBehaviour
    {
        private class Fan { public Transform t; public Component engine; }

        private readonly List<Fan> fans = new List<Fan>();
        private float nextScan;
        private Type aircraftType, turbofanType;

#if FLIGHTLOG
        // flight log
        private Component logged;
        private StreamWriter log;
        private float nextSample, logStart;
        private readonly List<Component> engines = new List<Component>(), nozzles = new List<Component>(), wings = new List<Component>(), flaps = new List<Component>();
        private readonly List<Component> bodies = new List<Component>();
#endif

        private void Update()
        {
            if (aircraftType == null) { aircraftType = R.T("Aircraft"); turbofanType = R.T("Turbofan"); }
            if (aircraftType == null) return;
            if (Time.unscaledTime >= nextScan) { nextScan = Time.unscaledTime + 2f; Scan(); }
            SpinFans();
#if FLIGHTLOG
            if (Plugin.FlightLog.Value) Sample(); else CloseLog();
#endif
        }

#if FLIGHTLOG
        private void OnDestroy() { CloseLog(); }
#endif

        private void Scan()
        {
            fans.RemoveAll(f => f.t == null || f.engine == null);
            var all = FindObjectsOfType(aircraftType);
            foreach (var o in all)
            {
                var ac = (Component)o;
                if (!ac.name.StartsWith("PB22")) continue;
                foreach (var side in new[] { "L", "R" })
                {
                    var t = R.Find(ac, "fan_" + side);
                    if (t == null || fans.Exists(f => f.t == t)) continue;
                    var eng = R.Find(ac, side == "L" ? "engine1" : "engine3");
                    var tf = eng != null && turbofanType != null ? eng.GetComponent(turbofanType) : null;
                    if (tf != null) { fans.Add(new Fan { t = t, engine = tf }); if (Plugin.DebugLog.Value) Plugin.Log.LogInfo("PB-22 fan " + side + " linked to " + eng.name + " on " + ac.name); }
                    else Plugin.Log.LogWarning("PB-22 fan " + side + ": no Turbofan found on " + ac.name);
                }
            }
#if FLIGHTLOG
            if (Plugin.FlightLog.Value)
            {
                Component player = null;
                foreach (var o in all)
                {
                    var ac = (Component)o;
                    var local = R.Get(ac, "LocalSim");
                    if (R.Get(ac, "Player") != null && local is bool && (bool)local) { player = ac; break; }
                }
                if (player != logged) OpenLog(player);
            }
#endif
        }

        // the fan face turns with the engine's spool: a visual rate (not the real 4000 rpm, which would strobe) scaled by RPM
        private bool rpmWarned;
        private void SpinFans()
        {
            // 0.4.8 logs showed Time.deltaTime reading 0 in this Update, so the fans never moved; real frame time
            // (capped so a hitch can't jump the blades) keeps them turning
            float dt = Mathf.Min(Time.unscaledDeltaTime, 0.1f);
            foreach (var f in fans)
            {
                if (f.t == null || f.engine == null) continue;
                float rpm = R.Fl(f.engine, "currentRPM"), max = R.Fl(f.engine, "maxRPM");
                if (float.IsNaN(rpm) || float.IsNaN(max) || max <= 0f)
                {
                    if (!rpmWarned) { rpmWarned = true; Plugin.Log.LogWarning("PB-22 fans: engine RPM unreadable (" + rpm + " / " + max + ")"); }
                    continue;
                }
                float k = Mathf.Clamp01(rpm / max);
                // at most 240 deg/s: the 22 blades sit 16 deg apart, so anything near or above half a blade per frame
                // strobes and the fan looks frozen or turning backwards (the 0.3.0 rate of 1500 deg/s did exactly that).
                // A shut-down engine still windmills slowly.
                f.t.Rotate(0f, 0f, -(40f + 200f * k) * dt, Space.Self);
            }
            // fan check for the BepInEx log: is the fan turning, and is its renderer the one on screen
            if (Plugin.DebugLog.Value && fans.Count > 0 && Time.unscaledTime >= nextFanLog)
            {
                nextFanLog = Time.unscaledTime + 20f;
                // report the fan most likely on screen: a visible one with the engine running
                Fan f = fans[fans.Count - 1];
                foreach (var c in fans)
                {
                    if (c.t == null || c.engine == null) continue;
                    var cr = c.t.GetComponent<Renderer>();
                    if (cr != null && cr.isVisible && R.Fl(c.engine, "currentRPM") > 0f) { f = c; break; }
                    if (cr != null && cr.isVisible) f = c;
                }
                if (f.t != null && f.engine != null)
                {
                    var r = f.t.GetComponent<Renderer>();
                    Plugin.Log.LogInfo("PB-22 fan check: " + f.t.name + " on " + f.t.root.name + " rpm " + R.Fl(f.engine, "currentRPM").ToString("F0") + "/" + R.Fl(f.engine, "maxRPM").ToString("F0")
                        + " angle " + f.t.localEulerAngles.z.ToString("F1") + " dt " + Time.deltaTime.ToString("F3") + " udt " + Time.unscaledDeltaTime.ToString("F3") + " ts " + Time.timeScale.ToString("F2")
                        + " renderer " + (r == null ? "none" : (r.enabled + "/" + r.isVisible + "/" + f.t.gameObject.activeInHierarchy))
                        + " fans " + fans.Count);
                }
            }
        }
        private float nextFanLog;

#if FLIGHTLOG
        private void OpenLog(Component ac)
        {
            CloseLog();
            logged = ac;
            if (ac == null) return;
            engines.Clear(); nozzles.Clear(); wings.Clear(); flaps.Clear(); bodies.Clear();
            foreach (var n in new[] { "Turbofan", "JetNozzle", "SwingWingController", "HighLiftDevice" })
            {
                var t = R.T(n);
                if (t == null) continue;
                var list = n == "Turbofan" ? engines : n == "JetNozzle" ? nozzles : n == "SwingWingController" ? wings : flaps;
                list.AddRange(ac.GetComponentsInChildren(t, true));
            }
            var rbT = R.T("UnityEngine.Rigidbody");
            if (rbT != null) bodies.AddRange(ac.GetComponentsInChildren(rbT, true));
            string dir = Path.Combine(Paths.BepInExRootPath, "PB22_flightlogs");
            Directory.CreateDirectory(dir);
            string file = Path.Combine(dir, ac.name.Replace("(Clone)", "").Trim() + "_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".csv");
            log = new StreamWriter(file, false, Encoding.ASCII);
            log.WriteLine("t,aircraft,alt_m,radarAlt_m,speed_ms,airDensity,aoa_deg,pitch_deg,climb_ms,gForce,throttle,pitchInput,engineThrust_N,nozzleThrust_N,rpmRatio,sweep,flap,gear,fuelLevel,mass_kg,airborne");
            logStart = Time.time;
        }

        private void CloseLog()
        {
            if (log != null) { log.Flush(); log.Close(); log = null; }
            logged = null;
        }

        private void Sample()
        {
            if (log == null || logged == null) return;
            if (Time.time < nextSample) return;
            nextSample = Time.time + 1f / Mathf.Max(0.5f, Plugin.FlightLogRate.Value);
            var tr = logged.transform;
            var rb = R.Get(logged, "rb");
            Vector3 v = rb != null ? R.V3(rb, "velocity") : Vector3.zero;
            float aoa = Mathf.Atan2(-Vector3.Dot(v, tr.up), Vector3.Dot(v, tr.forward)) * Mathf.Rad2Deg;
            float pitch = Mathf.Asin(Mathf.Clamp(tr.forward.y, -1f, 1f)) * Mathf.Rad2Deg;
            var ci = R.Get(logged, "controlInputs");
            float thrust = 0f, nthrust = 0f, rpm = 0f, mass = 0f, sweep = float.NaN, flap = float.NaN;
            foreach (var e in engines) if (e != null) { thrust += R.Fl(e, "currentThrust"); rpm += R.Fl(e, "currentRPM") / Mathf.Max(1f, R.Fl(e, "maxRPM")); }
            if (engines.Count > 0) rpm /= engines.Count;
            foreach (var n in nozzles) if (n != null) nthrust += R.Fl(n, "totalThrust");
            foreach (var w in wings) if (w != null) { sweep = R.Fl(w, "positionPrev"); break; }
            foreach (var f in flaps) if (f != null) { flap = R.Fl(f, "position"); break; }
            foreach (var b in bodies) if (b != null) mass += R.Fl(b, "mass");
            var ic = CultureInfo.InvariantCulture;
            log.WriteLine(string.Join(",", new[] {
                (Time.time - logStart).ToString("F2", ic), logged.name.Replace(",", ""),
                tr.position.y.ToString("F1", ic), R.Fl(logged, "radarAlt").ToString("F1", ic), v.magnitude.ToString("F2", ic),
                R.Fl(logged, "airDensity").ToString("F4", ic), aoa.ToString("F2", ic), pitch.ToString("F2", ic), v.y.ToString("F2", ic),
                R.Fl(logged, "gForce").ToString("F2", ic), R.Fl(ci, "throttle").ToString("F2", ic), R.Fl(ci, "pitch").ToString("F2", ic),
                thrust.ToString("F0", ic), nthrust.ToString("F0", ic), rpm.ToString("F3", ic), sweep.ToString("F3", ic), flap.ToString("F3", ic),
                R.Fl(logged, "gearState").ToString("F0", ic), R.Fl(logged, "fuelLevel").ToString("F3", ic), mass.ToString("F0", ic),
                R.Fl(logged, "airborne").ToString("F0", ic) }));
        }
#endif
    }
}
