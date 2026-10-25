using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

// PB-22 Trident cockpit: original interior (PB22_cockpit.fbx + atlas) wired to the game's own cockpit systems.
// Yokes and throttles move through stock components only (ControlSurface, Cockpit.throttles); no plugin code.
// SetupAssets() makes the cockpit materials, the bundled ejection seat and the tac screen page once;
// Build() is called from PB22Builder.Cockpit() after the crew are placed. Every value is a literal on purpose.
public static class PB22Cockpit
{
    const string CK = "Assets/Blueprinter/Mods/PB22Trident/Art/Cockpit/";
    const string PH = "Assets/Blueprinter/_donotship/";
    const float RAISE = 0.15f;          // front seats sit higher than 0.4.4 for the -7.5 deg over-nose view
    const float FRONT_SEAT_Y = -0.15f;  // front crew origin height in the aircraft frame (0.4.4 seat y -0.34 + RAISE, then +0.04 on 2026-10-19)
    const float COL_TILT = 8f;          // yoke column leans aft

    // pivots in prefab-root space (match pb22_cockpit_model.py)
    static readonly Vector3 THROTTLE_PIVOT = new Vector3(0f, -0.26f, 10.84f);
    static readonly Vector3 COL_PIVOT_L = new Vector3(-0.34f, -0.77f, 10.98f);
    static readonly Vector3 COL_PIVOT_R = new Vector3(0.34f, -0.77f, 10.98f);
    static readonly Vector3 HUB_L = new Vector3(-0.34f, -0.08f, 10.883027f);
    static readonly Vector3 HUB_R = new Vector3(0.34f, -0.08f, 10.883027f);

    static readonly string[] MINE = { "PB22_cockpit_int", "PB22_warningLights", "PB22_tacScreen", "PB22_screens", "PB22_throttle",
                                      "PB22_yoke_L", "PB22_yoke_R", "PB22_cockpit_int_simple", "PB22_rear_int", "PB22_rear_screens", "PB22_rear_int_simple" };

    static System.Type GameType(string n)
    {
        foreach (var a in System.AppDomain.CurrentDomain.GetAssemblies()) { var t = a.GetType(n); if (t != null) return t; }
        throw new System.Exception("no type " + n);
    }
    static SerializedProperty Prop(SerializedObject so, string path)
    {
        var p = so.FindProperty(path); if (p == null) throw new System.Exception("no property " + path + " on " + so.targetObject);
        return p;
    }
    static void Set(Object c, string path, object v)
    {
        var so = new SerializedObject(c); var p = Prop(so, path);
        if (v is float) p.floatValue = (float)v; else if (v is string) p.stringValue = (string)v; else if (v is bool) p.boolValue = (bool)v; else if (v is int) p.intValue = (int)v;
        else if (v is Vector3) p.vector3Value = (Vector3)v; else p.objectReferenceValue = (Object)v;
        so.ApplyModifiedPropertiesWithoutUndo();
    }
    static void ObjArray(Object c, string path, params Object[] items)
    {
        var so = new SerializedObject(c); var p = Prop(so, path); p.arraySize = items.Length;
        for (int i = 0; i < items.Length; i++) p.GetArrayElementAtIndex(i).objectReferenceValue = items[i];
        so.ApplyModifiedPropertiesWithoutUndo();
    }
    static T Load<T>(string path) where T : Object
    {
        var o = AssetDatabase.LoadAssetAtPath<T>(path); if (o == null) throw new System.Exception("missing " + path);
        return o;
    }

    // ------------------------------------------------------------------ one-time assets
    [MenuItem("PB22/Cockpit Setup Assets")]
    public static void SetupAssets()
    {
        var log = new StringBuilder();
        AssetDatabase.Refresh();
        foreach (var n in new[] { "_n", "_m", "_ao" }) Importer(CK + "PB22_cockpit" + n + ".png", n == "_n");
        Importer(CK + "PB22_cockpit_b.png", false, true);
        Importer(CK + "PB22_screen_e.png", false, true);   // rear station screens

        // cockpit material: same settings as a stock cockpit material, our own maps
        var stock = Load<Material>(PH + "Material/SFB_cockpit_PLACEHOLDER.mat");
        var ck = new Material(stock) { name = "PB22_cockpit" };
        SetMaps(ck, "PB22_cockpit");
        Save(ck, CK + "PB22_cockpit.mat");

        // cabin lining for the hull interior around the crew; the exterior build's PB22_cabin faces are UV'd at 2.5 m per unit,
        // one texture tile is 0.60 m, so the material tiles 2.5/0.6 times
        foreach (var n in new[] { "_n", "_m", "_ao" }) Importer(CK + "PB22_cabinwall" + n + ".png", n == "_n");
        Importer(CK + "PB22_cabinwall_b.png", false, true);
        var cw = new Material(stock) { name = "PB22_cabin" };
        SetMaps(cw, "PB22_cabinwall");
        cw.SetTextureScale("_BaseMap", new Vector2(4.1667f, 4.1667f)); cw.SetTextureScale("_MainTex", new Vector2(4.1667f, 4.1667f));
        Save(cw, CK + "PB22_cabin.mat");

        // lit display glass (flight and nav pages); the inboard pair shows the live tac screen instead
        var sc = new Material(stock) { name = "PB22_screen" };
        sc.SetTexture("_BaseMap", null); sc.SetTexture("_MainTex", null); sc.SetTexture("_BumpMap", null);
        sc.SetTexture("_MetallicGlossMap", null); sc.SetTexture("_OcclusionMap", null);
        sc.DisableKeyword("_NORMALMAP"); sc.DisableKeyword("_METALLICSPECGLOSSMAP"); sc.DisableKeyword("_OCCLUSIONMAP");
        sc.SetColor("_BaseColor", new Color(0.02f, 0.025f, 0.03f, 1f)); sc.SetFloat("_Smoothness", 0.85f);
        sc.SetTexture("_EmissionMap", Load<Texture2D>(CK + "PB22_screen_e.png")); sc.SetColor("_EmissionColor", new Color(0.55f, 0.55f, 0.55f, 1f));
        sc.EnableKeyword("_EMISSION"); sc.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
        Save(sc, CK + "PB22_screen.mat");

        // Medusa ejection seat, bundled with the Trident as its own named assets (2026-10-19)
        Copy(PH + "Mesh/ejectionSeat_PLACEHOLDER.asset", CK + "PB22_EjectionSeat.asset");
        var seatMesh = Load<Mesh>(CK + "PB22_EjectionSeat.asset"); seatMesh.name = "PB22_EjectionSeat"; EditorUtility.SetDirty(seatMesh);
        foreach (var n in new[] { "b", "n", "m", "ao" }) Copy(PH + "Texture2D/seats_" + n + "_PLACEHOLDER.png", CK + "PB22_seat_" + n + ".png");
        var seat = new Material(Load<Material>(PH + "Material/Seats_PLACEHOLDER.mat")) { name = "PB22_seat" };
        SetMaps(seat, "PB22_seat");
        Save(seat, CK + "PB22_seat.mat");

        TacScreen(log);
        AssetDatabase.SaveAssets();
        Debug.Log("PB22 cockpit assets ready\n" + log);
    }
    static void Importer(string path, bool normal, bool srgb = false)
    {
        var ti = AssetImporter.GetAtPath(path) as TextureImporter; if (ti == null) throw new System.Exception("missing " + path);
        ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
        ti.sRGBTexture = srgb; ti.maxTextureSize = 2048; ti.mipmapEnabled = true;
        ti.SaveAndReimport();
    }
    static void SetMaps(Material m, string prefix)
    {
        var b = Load<Texture2D>(CK + prefix + "_b.png");
        m.SetTexture("_BaseMap", b); m.SetTexture("_MainTex", b);
        m.SetTexture("_BumpMap", Load<Texture2D>(CK + prefix + "_n.png"));
        m.SetTexture("_MetallicGlossMap", Load<Texture2D>(CK + prefix + "_m.png"));
        m.SetTexture("_OcclusionMap", Load<Texture2D>(CK + prefix + "_ao.png"));
    }
    static void Save(Material m, string path)
    {
        var old = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (old != null) { old.shader = m.shader; old.CopyPropertiesFromMaterial(m); old.shaderKeywords = m.shaderKeywords; EditorUtility.SetDirty(old); }
        else AssetDatabase.CreateAsset(m, path);
    }
    static void Copy(string src, string dst)
    {
        if (AssetDatabase.LoadMainAssetAtPath(dst) != null) return;
        if (!AssetDatabase.CopyAsset(src, dst)) throw new System.Exception("copy failed " + src);
    }

    // ------------------------------------------------------------------ tac screen page
    // One stock tac screen render texture (1024x512) feeds every front display; the model maps each glass to one region
    // (RT_REGIONS in pb22_cockpit_model.py, pixels from the top-left):
    //   tac    (0,0,440,400)     outer displays: map / radar, target and landing cameras
    //   centre (440,0,584,230)   merged centre display: flight data, both engines, fuel and throttle
    //   stores (440,230,310,282) middle displays: PB-22 planform with the five weapon stations
    //   annun  (0,400,440,46)    both pilots' lamp strips on the glareshield lip
    //   adi    (760,250,256,256) standby attitude ball on both pilots' round gauges (stock ArtificialHorizon)
    // Everything on the page is a stock HUD app (Medusa page as the base, Darkreach engine rows); no plugin code.
    static readonly Color LAMP_OFF = new Color(0.055f, 0.06f, 0.055f, 1f);
    static readonly Color LEGEND = new Color(0.42f, 0.42f, 0.40f, 1f);
    static readonly Color GREEN = new Color(0f, 1f, 0f, 1f);
    static readonly Color AMBER_LAMP = new Color(1f, 0.62f, 0f, 1f);
    // panel lamps lit through the screen texture (model LAMP_CELLS, region lamps (0,446,440,66), 8 x 3 cells of 55 x 22)
    static readonly string[] PANEL_LAMPS = { "GEAR", "FLAP", "MSL WARN", "NOSE", "LEFT", "RIGHT", "FIRE L", "FIRE R" };

    static void TacScreen(StringBuilder log)
    {
        string dst = CK + "PB22_tacScreen.prefab";
        AssetDatabase.DeleteAsset(dst);
        Copy(PH + "GameObject/tacScreen_EW1_PLACEHOLDER.prefab", dst);

        Importer(CK + "PB22_planform.png", false, true);
        var ti = (TextureImporter)AssetImporter.GetAtPath(CK + "PB22_planform.png");
        ti.textureType = TextureImporterType.Sprite; ti.alphaIsTransparency = true; ti.mipmapEnabled = false; ti.SaveAndReimport();
        var planform = Load<Sprite>(CK + "PB22_planform.png");

        var sfb = PrefabUtility.LoadPrefabContents(AssetDatabase.GUIDToAssetPath(AssetDatabase.FindAssets("tacScreen_SFB_PLACEHOLDER t:Prefab")[0]));
        var root = PrefabUtility.LoadPrefabContents(dst);
        try
        {
            root.name = "PB22_tacScreen";
            System.Func<string, RectTransform> R = n => root.GetComponentsInChildren<RectTransform>(true).First(t => t.name == n);
            var canvas = R("Canvas"); int layer = canvas.gameObject.layer;
            var font = Object.Instantiate(R("Box_Bay").Find("Title").gameObject, root.transform, false);   // text template, removed before saving
            font.SetActive(false);

            // canvas is 1024x512 with (0,0) at the centre, y up; Rgn turns an RT pixel rect into a canvas centre point
            System.Func<float, float, float, float, Vector2> Rgn = (x, y, w, h) => new Vector2(x + w/2f - 512f, 256f - y - h/2f);
            System.Action<RectTransform, Vector2, float> Place = (t, p, s) =>
            {
                t.anchorMin = t.anchorMax = t.pivot = new Vector2(0.5f, 0.5f);
                t.anchoredPosition = p; t.localScale = new Vector3(s, s, 1f);
            };
            System.Func<string, Transform, Vector2, Vector2, RectTransform> Node = (n, parent, p, size) =>
            {
                var go = new GameObject(n, typeof(RectTransform)); go.layer = layer;
                var t = (RectTransform)go.transform; t.SetParent(parent, false);
                Place(t, p, 1f); t.sizeDelta = size; return t;
            };
            System.Func<string, Transform, Vector2, Vector2, Color, UnityEngine.UI.Image> Img = (n, parent, p, size, col) =>
            {
                var t = Node(n, parent, p, size); var im = t.gameObject.AddComponent<UnityEngine.UI.Image>();
                im.color = col; im.raycastTarget = false; return im;
            };
            System.Func<string, Transform, Vector2, Vector2, string, float, Color, Component> Txt = (n, parent, p, size, text, fs, col) =>
            {
                var go = Object.Instantiate(font, parent, false); go.name = n; go.layer = layer; go.SetActive(true);
                foreach (Transform ch in go.transform) Object.DestroyImmediate(ch.gameObject);
                var t = (RectTransform)go.transform; Place(t, p, 1f); t.sizeDelta = size;
                var tmp = go.GetComponent("TMPro.TextMeshProUGUI"); var ty = tmp.GetType();
                ty.GetProperty("text").SetValue(tmp, text);
                ty.GetProperty("enableAutoSizing").SetValue(tmp, false);
                ty.GetProperty("fontSize").SetValue(tmp, fs);
                ty.GetProperty("color").SetValue(tmp, col);
                var al = ty.GetProperty("alignment"); al.SetValue(tmp, System.Enum.Parse(al.PropertyType, "Center"));
                ty.GetProperty("enableWordWrapping").SetValue(tmp, false);
                ty.GetProperty("raycastTarget").SetValue(tmp, false);
                return tmp;
            };
            System.Func<Transform, Vector2, Vector2, Color, Transform> Frame = (parent, p, size, col) =>
            {
                var f = Node("frame", parent, p, size);
                Img("top", f, new Vector2(0, size.y/2f - 1f), new Vector2(size.x, 2f), col);
                Img("bottom", f, new Vector2(0, -size.y/2f + 1f), new Vector2(size.x, 2f), col);
                Img("left", f, new Vector2(-size.x/2f + 1f, 0), new Vector2(2f, size.y), col);
                Img("right", f, new Vector2(size.x/2f - 1f, 0), new Vector2(2f, size.y), col);
                return f;
            };
            var frameCol = new Color(0f, 1f, 0f, 0.35f);

            // ---------------- tac: radar scope filling the outer glass, camera feeds over it, clock top left
            var tacC = Rgn(0, 0, 440, 400);
            Place(R("Radar"), tacC, 400f/512f);
            foreach (var cn in new[] { "TargetCam", "LandingCam" })
            {   // the feed is 3:2, the glass 1.1:1: fill the glass height and trim the sides evenly (2026-10-19: feed was letterboxed)
                var cam = R(cn); Place(cam, tacC, 1f); cam.sizeDelta = new Vector2(440f, 400f);
                var raw = cam.GetComponent<UnityEngine.UI.RawImage>();
                if (raw != null) { float uw = (440f/400f)/(360f/240f); raw.uvRect = new Rect((1f - uw)/2f, 0f, uw, 1f); }
            }
            Place(R("TimeObject"), tacC + new Vector2(-150f, 172f), 1f);
            foreach (var n in new[] { "Buttons", "divider", "divider (2)", "nozzleGauge" }) R(n).gameObject.SetActive(false);
            canvas.Find("border").gameObject.SetActive(false);      // the page-wide Medusa frame (the radar keeps its own)

            // ---------------- centre: flight block | engine rows (Darkreach engine telemetry) | fuel and throttle bars
            var cen = Rgn(440, 0, 584, 230);
            Frame(canvas, cen, new Vector2(580f, 226f), frameCol);
            var bfi = R("BasicFlightInstrument");
            Place(bfi, cen + new Vector2(-207f, 0f), 1.05f);
            bfi.GetComponent<UnityEngine.UI.Image>().enabled = true;
            var engRows = Node("EngineRows", canvas, cen + new Vector2(43f, 0f), new Vector2(330f, 220f));
            var sfbEng = sfb.GetComponentsInChildren<RectTransform>(true);
            foreach (var side in new[] { "L", "R" })
            {
                var row = (RectTransform)Object.Instantiate(sfbEng.First(t => t.name == "eng" + side).gameObject, engRows, false).transform;
                row.name = "eng" + side; SetLayer(row, layer);
                Object.DestroyImmediate(row.GetComponent<UnityEngine.UI.VerticalLayoutGroup>());
                Place(row, new Vector2(0f, side == "L" ? 54f : -54f), 1f); row.sizeDelta = new Vector2(326f, 104f);
                var title = (RectTransform)row.Find("Title");
                Place(title, new Vector2(-115f, 18f), 0.6f);
                title.GetComponent("TMPro.TextMeshProUGUI").GetType().GetProperty("text").SetValue(title.GetComponent("TMPro.TextMeshProUGUI"), "ENG " + side);
                var status = (RectTransform)title.Find("status"); status.anchoredPosition = new Vector2(0f, -50f);
                float[] xs = { -28f, 46f, 120f };
                string[] dials = { "ThrustGauge1", "RPMGauge1", "ThrottleGauge1" };
                for (int k = 0; k < 3; k++) Place((RectTransform)row.Find(dials[k]), new Vector2(xs[k], 6f), 0.9f);
                var et = row.GetComponent(GameType("EngineTelemetry"));
                Set(et, "engineName", side == "L" ? "engine1" : "engine3");      // the Turbofan parts on engines_L / engines_R
                Set(et, "thrustGauge.maxValue", 160000f); Set(et, "rpmGauge.maxValue", 3000f); Set(et, "throttleGauge.maxValue", 100f);
            }
            var sg = R("StatusGauges");
            Place(sg, cen + new Vector2(250f, -4f), 1f); sg.sizeDelta = new Vector2(84f, 214f);
            Place((RectTransform)sg.Find("Fuel"), new Vector2(-20f, -10f), 0.8f);
            Place((RectTransform)sg.Find("Throttle"), new Vector2(20f, -10f), 0.8f);
            foreach (var tn in new[] { "Fuel/Title Fuel", "Throttle/Title Throttle" })
            {
                var tt = (RectTransform)sg.Find(tn); tt.localScale = new Vector3(0.4f, 0.4f, 1f);
                var tmp = tt.GetComponent("TMPro.TextMeshProUGUI"); if (tn.EndsWith("Throttle")) tmp.GetType().GetProperty("text").SetValue(tmp, "THR");
            }
            foreach (var n in new[] { "IRGauge", "Mass", "TWR" }) sg.Find(n).gameObject.SetActive(false);

            // ---------------- stores: planform with the stations where they really are, labelled boxes either side
            var sto = Rgn(440, 230, 310, 282);
            Frame(canvas, sto, new Vector2(306f, 278f), frameCol);
            var wp = R("WeaponPanel"); Place(wp, sto, 1f); wp.sizeDelta = new Vector2(306f, 278f);
            foreach (Transform ch in wp.Cast<Transform>().ToArray()) Object.DestroyImmediate(ch.gameObject);
            const float PX = 0.525f * 12.8f;      // sprite drawn at 0.525 scale, 12.8 px per metre in the sprite
            var pfImg = Img("planform", wp, new Vector2(0f, -4f), new Vector2(354f, 438f), GREEN);
            pfImg.sprite = planform; pfImg.rectTransform.localScale = new Vector3(0.525f, 0.525f, 1f);
            System.Func<float, float, Vector2> At = (x, z) => new Vector2(x*PX, -4f + (z - 0.02f)*PX);
            Txt("Title", wp, new Vector2(112f, -122f), new Vector2(80f, 16f), "STORES", 13f, GREEN);
            var markers = new Dictionary<string, UnityEngine.UI.Image>
            {
                { "fwd", Img("bay_fwd", wp, At(0f, 1.10f), new Vector2(9f, 26f), GREEN) },
                { "aft", Img("bay_aft", wp, At(0f, -4.85f), new Vector2(9f, 26f), GREEN) },
                { "inL", Img("pylon_inner_L", wp, At(-1.55f, 2.00f), new Vector2(8f, 8f), GREEN) },
                { "inR", Img("pylon_inner_R", wp, At(1.55f, 2.00f), new Vector2(8f, 8f), GREEN) },
                { "outL", Img("pylon_outer_L", wp, At(-5.45f, -5.25f), new Vector2(8f, 8f), GREEN) },
                { "outR", Img("pylon_outer_R", wp, At(5.45f, -5.25f), new Vector2(8f, 8f), GREEN) },
            };
            // combined bays: a bracket around both bays
            var comb = new List<UnityEngine.UI.Image>();
            {
                var top = At(0f, 1.10f).y + 17f; var bot = At(0f, -4.85f).y - 17f;
                comb.Add(Img("comb_l", wp, new Vector2(-9f, (top + bot)/2f), new Vector2(2f, top - bot), GREEN));
                comb.Add(Img("comb_r", wp, new Vector2(9f, (top + bot)/2f), new Vector2(2f, top - bot), GREEN));
                comb.Add(Img("comb_t", wp, new Vector2(0f, top), new Vector2(20f, 2f), GREEN));
                comb.Add(Img("comb_b", wp, new Vector2(0f, bot), new Vector2(20f, 2f), GREEN));
            }
            System.Func<string, string, Vector2, List<Object>> Box = (n, title, p) =>
            {
                var bg = Img(n, wp, p, new Vector2(76f, 26f), new Color(0f, 1f, 0f, 0.08f));
                var fr = Frame(bg.transform, Vector2.zero, new Vector2(76f, 26f), new Color(0f, 1f, 0f, 0.6f));
                var a = Txt("Title", bg.transform, Vector2.zero, new Vector2(74f, 20f), title, 12f, GREEN);
                var l = new List<Object> { bg, a }; l.AddRange(fr.GetComponentsInChildren<UnityEngine.UI.Image>());
                return l;
            };
            var bFwd = Box("box_fwd", "FWD BAY", new Vector2(-113f, 108f));
            var bInL = Box("box_inL", "L INNER", new Vector2(-113f, 66f));
            var bOutL = Box("box_outL", "L OUTER", new Vector2(-113f, 24f));
            var bAft = Box("box_aft", "AFT BAY", new Vector2(113f, 108f));
            var bInR = Box("box_inR", "R INNER", new Vector2(113f, 66f));
            var bOutR = Box("box_outR", "R OUTER", new Vector2(113f, 24f));
            var bComb = Box("box_comb", "BAYS COMB", new Vector2(-113f, -116f));
            // leader lines from each box to its station (Darkreach style)
            System.Func<Vector2, Vector2, Object> Lead = (from, to) =>
            {
                var d = to - from; var im = Img("lead", wp, (from + to)/2f, new Vector2(d.magnitude, 1.5f), new Color(0f, 1f, 0f, 0.55f));
                im.rectTransform.localEulerAngles = new Vector3(0f, 0f, Mathf.Atan2(d.y, d.x)*Mathf.Rad2Deg); return im;
            };
            var lFwd = Lead(new Vector2(-75f, 108f), At(0f, 1.10f) + new Vector2(-5f, 8f));
            var lAft = Lead(new Vector2(75f, 108f), At(0f, -4.85f) + new Vector2(5f, 8f));
            var lInL = Lead(new Vector2(-75f, 66f), At(-1.55f, 2.00f)); var lInR = Lead(new Vector2(75f, 66f), At(1.55f, 2.00f));
            var lOutL = Lead(new Vector2(-75f, 24f), At(-5.45f, -5.25f)); var lOutR = Lead(new Vector2(75f, 24f), At(5.45f, -5.25f));
            var lComb = Lead(new Vector2(-75f, -116f), new Vector2(-9f, At(0f, -4.85f).y - 17f));
            // hardpoint sets: 0 forward bay, 1 rear bay, 2 combined bays, 3 inner pylons, 4 outer pylons
            var sets = new[]
            {
                new List<Object> { markers["fwd"], lFwd }.Concat(bFwd).ToList(),
                new List<Object> { markers["aft"], lAft }.Concat(bAft).ToList(),
                comb.Cast<Object>().Concat(new[] { lComb }).Concat(bComb).ToList(),
                new List<Object> { markers["inL"], markers["inR"], lInL, lInR }.Concat(bInL).Concat(bInR).ToList(),
                new List<Object> { markers["outL"], markers["outR"], lOutL, lOutR }.Concat(bOutL).Concat(bOutR).ToList(),
            };
            var pi = wp.GetComponent(GameType("PylonIndicator"));
            var so2 = new SerializedObject(pi); var arr = so2.FindProperty("pylonElementSets"); arr.arraySize = sets.Length;
            for (int i = 0; i < sets.Length; i++)
            {
                var e = arr.GetArrayElementAtIndex(i);
                var imgs = sets[i].Where(o => o is UnityEngine.UI.Image).ToArray();
                var txts = sets[i].Where(o => !(o is UnityEngine.UI.Image)).ToArray();
                var a = e.FindPropertyRelative("pylonImages"); a.arraySize = imgs.Length;
                for (int k = 0; k < imgs.Length; k++) a.GetArrayElementAtIndex(k).objectReferenceValue = imgs[k];
                var b = e.FindPropertyRelative("pylonTexts"); b.arraySize = txts.Length;
                for (int k = 0; k < txts.Length; k++) b.GetArrayElementAtIndex(k).objectReferenceValue = txts[k];
                log.AppendLine("stores set " + i + ": " + imgs.Length + " images, " + txts.Length + " texts");
            }
            so2.ApplyModifiedPropertiesWithoutUndo();

            // ---------------- annunciator strip: 8 x 2 lamps, dark until a stock app lights them
            var ann = Node("Annunciators", canvas, Rgn(0, 400, 440, 46), new Vector2(440f, 46f));
            Img("bg", ann, Vector2.zero, new Vector2(440f, 46f), new Color(0.02f, 0.02f, 0.02f, 1f));
            var lampFill = new Dictionary<string, UnityEngine.UI.Image>(); var lampBar = new Dictionary<string, UnityEngine.UI.Image>();
            var lampText = new Dictionary<string, Component>();
            string[] labels = { "MSL", "GEAR DN", "BRAKE", "SLOW", "ON SPD", "FAST", "RADAR", "FCS",
                                "ENG L", "ENG R", "FUEL", "MODE", "HYD", "ELEC", "FUEL FIRE", "IFF" };   // FUEL FIRE took ICE's place (2026-10-19)
            var fillCol = new Dictionary<string, Color> { { "MSL", new Color(1f, 0.1f, 0.05f) }, { "GEAR DN", GREEN }, { "BRAKE", new Color(1f, 0.7f, 0f) },
                                                          { "SLOW", GREEN }, { "ON SPD", GREEN }, { "FAST", GREEN },
                                                          // lit by the PB-22 plugin (PB22Gauges): no stock signal drives these
                                                          { "HYD", AMBER_LAMP }, { "ELEC", AMBER_LAMP }, { "FUEL FIRE", new Color(1f, 0.1f, 0.05f) }, { "IFF", AMBER_LAMP } };
            for (int k = 0; k < labels.Length; k++)
            {
                var p = new Vector2(-220f + 27.5f + (k % 8)*55f, k < 8 ? 11.5f : -11.5f);
                var cell = Node("lamp_" + labels[k], ann, p, new Vector2(51f, 19f));
                Img("off", cell, Vector2.zero, new Vector2(51f, 19f), LAMP_OFF);
                if (fillCol.ContainsKey(labels[k]))
                {
                    var f = Img("lit", cell, Vector2.zero, new Vector2(51f, 19f), fillCol[labels[k]]); f.enabled = false; lampFill[labels[k]] = f;
                }
                else lampBar[labels[k]] = Img("bar", cell, new Vector2(0f, -8f), new Vector2(45f, 2f), LEGEND);
                lampText[labels[k]] = Txt("legend", cell, Vector2.zero, new Vector2(49f, 17f), labels[k], 10f, LEGEND);
                if (labels[k] == "MODE" || labels[k] == "FUEL FIRE")
                {   // SystemStatusDisplay writes "MODE : NAV" / "MODE : COMBAT" here
                    var tm = lampText[labels[k]]; var ty = tm.GetType();
                    ty.GetProperty("enableAutoSizing").SetValue(tm, true); ty.GetProperty("fontSizeMin").SetValue(tm, 5f); ty.GetProperty("fontSizeMax").SetValue(tm, 10f);
                }
            }
            ann.SetAsLastSibling();

            // ---------------- panel lamps (switch box, gear panel, engine fire): one cell each, shared by both pilots
            var plamps = Node("PanelLamps", canvas, Rgn(0, 446, 440, 66), new Vector2(440f, 66f));
            Img("bg", plamps, Vector2.zero, new Vector2(440f, 66f), new Color(0.02f, 0.02f, 0.02f, 1f));
            UnityEngine.UI.Image mslPanel = null;
            for (int k = 0; k < PANEL_LAMPS.Length; k++)
            {
                string n = PANEL_LAMPS[k];
                Color col = n == "FLAP" ? AMBER_LAMP : (n == "MSL WARN" || n.StartsWith("FIRE") ? new Color(1f, 0.1f, 0.05f) : GREEN);
                var cell = Node("panel_" + n, plamps, new Vector2(-220f + 27.5f + (k % 8)*55f, 33f - 11f - (k / 8)*22f), new Vector2(55f, 22f));
                Img("off", cell, Vector2.zero, new Vector2(53f, 20f), col*0.30f + new Color(0f, 0f, 0f, 0.70f));
                var lit = Img("lit", cell, Vector2.zero, new Vector2(53f, 20f), col); lit.enabled = false;
                Txt("legend", cell, Vector2.zero, new Vector2(51f, 18f), n, n.Length > 6 ? 8f : 10f, new Color(0.10f, 0.09f, 0.07f, 1f));
                if (n == "MSL WARN") mslPanel = lit;
            }

            var apps = new List<Object>();
            var ann_go = ann.gameObject;
            // gear down and brake: stock GearIndicator; its overspeed voice already plays from the HUD, so the limit is out of reach here
            var gi = ann_go.AddComponent(GameType("GearIndicator"));
            Set(gi, "speedLimit", 100000f); Set(gi, "gearIcon", lampFill["GEAR DN"]); Set(gi, "brakeIcon", lampFill["BRAKE"]);
            Set(gi, "lowerGearWarning", false);
            var lgt = Txt("lowerGearText", ann, new Vector2(0f, 400f), new Vector2(10f, 10f), "", 8f, LEGEND); Set(gi, "lowerGearText", lgt);
            apps.Add(gi);
            // approach indexer: stock AoAIndexer (gear down, below 70% throttle, airborne)
            var ai = ann_go.AddComponent(GameType("AoAIndexer"));
            var outline = Img("aoaOutline", ann, new Vector2(0f, 400f), new Vector2(2f, 2f), new Color(0f, 0f, 0f, 0f)); outline.enabled = false;
            Set(ai, "outline", outline); Set(ai, "slowArrow", lampFill["SLOW"]); Set(ai, "fastArrow", lampFill["FAST"]); Set(ai, "onSpeedCircle", lampFill["ON SPD"]);
            Set(ai, "targetAoA", 8f); Set(ai, "AoARange", 2f);            // FastBomber1 HUD values
            apps.Add(ai);
            // missile launch: stock MissileWarningLight (flashes with the CockpitWarningLights on the glareshield)
            var mw = ann_go.AddComponent(GameType("MissileWarningLight"));
            ObjArray(mw, "images", lampFill["MSL"], mslPanel); apps.Add(mw);
            // radar, flight control, fuel and HUD mode: the Medusa page's SystemStatusDisplay, re-pointed at the lamps
            var ss = R("SystemStatus");
            var ssd = ss.GetComponent(GameType("SystemStatusDisplay"));
            Set(ssd, "systemRadarImg", lampBar["RADAR"]); Set(ssd, "systemRadarTxt", lampText["RADAR"]);
            Set(ssd, "systemFlightControlImg", lampBar["FCS"]); Set(ssd, "systemFlightControlTxt", lampText["FCS"]);
            Set(ssd, "systemFuelImg", lampBar["FUEL"]); Set(ssd, "systemFuelTxt", lampText["FUEL"]);
            Set(ssd, "systemModeImg", lampBar["MODE"]); Set(ssd, "systemModeTxt", lampText["MODE"]);
            ss.gameObject.GetComponent<UnityEngine.UI.GridLayoutGroup>().enabled = false;
            Place(ss, new Vector2(0f, 3000f), 1f);       // engine and gear entries stay wired to the old grid, off the page
            ((RectTransform)ss.Find("SystemMode").Find("Mode")).gameObject.SetActive(false);
            // engines: each engine row also colours its lamp (green running, amber fault, red out)
            foreach (var side in new[] { "L", "R" })
            {
                var et = engRows.Find("eng" + side).GetComponent(GameType("EngineTelemetry"));
                var so = new SerializedObject(et);
                var ci = so.FindProperty("colorableImages"); ci.arraySize++; ci.GetArrayElementAtIndex(ci.arraySize - 1).objectReferenceValue = lampBar["ENG " + side];
                var ct = so.FindProperty("colorableTexts"); ct.arraySize++; ct.GetArrayElementAtIndex(ct.arraySize - 1).objectReferenceValue = lampText["ENG " + side];
                so.ApplyModifiedPropertiesWithoutUndo();
            }
            // standby attitude ball (2026-10-19: make the horizon work): stock ArtificialHorizon app in its own 256 px square,
            // shown on both pilots' round standby gauges. Ground is a filled square turned with roll, its fill height follows pitch.
            {
                string whp = CK + "PB22_white.png";
                if (!System.IO.File.Exists(whp))
                {
                    var wt = new Texture2D(8, 8); var px = new Color[64]; for (int i = 0; i < 64; i++) px[i] = Color.white; wt.SetPixels(px); wt.Apply();
                    System.IO.File.WriteAllBytes(whp, wt.EncodeToPNG()); Object.DestroyImmediate(wt); AssetDatabase.ImportAsset(whp);
                }
                var wi = (TextureImporter)AssetImporter.GetAtPath(whp);
                wi.textureType = TextureImporterType.Sprite; wi.mipmapEnabled = false; wi.SaveAndReimport();
                var white = Load<Sprite>(whp);
                var adi = Node("StandbyADI", canvas, Rgn(760, 250, 256, 256), new Vector2(256f, 256f));
                adi.gameObject.AddComponent<UnityEngine.UI.RectMask2D>();
                var sky = Img("sky", adi, Vector2.zero, new Vector2(256f, 256f), new Color(0.20f, 0.46f, 0.78f, 1f));
                var ground = Img("ground", adi, Vector2.zero, new Vector2(512f, 512f), new Color(0.47f, 0.31f, 0.16f, 1f));
                ground.sprite = white; ground.type = UnityEngine.UI.Image.Type.Filled;
                ground.fillMethod = UnityEngine.UI.Image.FillMethod.Vertical; ground.fillOrigin = 0; ground.fillAmount = 0.5f;
                var skyFill = Img("skyFill", adi, Vector2.zero, new Vector2(2f, 2f), new Color(0f, 0f, 0f, 0f));   // the app also drives a sky fill; ours stays hidden
                skyFill.sprite = white; skyFill.type = UnityEngine.UI.Image.Type.Filled; skyFill.enabled = false;
                var tick = Color.white;
                foreach (var ang in new[] { -60f, -30f, -20f, -10f, 0f, 10f, 20f, 30f, 60f })
                {
                    float rad = ang*Mathf.Deg2Rad, len = (ang % 30f == 0f) ? 18f : 11f, r0 = 126f - len/2f;
                    var tk = Img("bank" + ang, adi, new Vector2(Mathf.Sin(rad)*r0, Mathf.Cos(rad)*r0), new Vector2(4f, len), tick);
                    tk.rectTransform.localEulerAngles = new Vector3(0f, 0f, -ang);
                }
                var sym = Node("aircraft", adi, Vector2.zero, new Vector2(150f, 12f));
                var amber = new Color(1f, 0.66f, 0.12f, 1f);
                Img("wingL", sym, new Vector2(-48f, 0f), new Vector2(46f, 7f), amber); Img("wingR", sym, new Vector2(48f, 0f), new Vector2(46f, 7f), amber);
                Img("dot", sym, Vector2.zero, new Vector2(10f, 10f), amber);
                var ah = adi.gameObject.AddComponent(GameType("ArtificialHorizon"));
                Set(ah, "attitude_img", sym.Find("dot").GetComponent<UnityEngine.UI.Image>());
                Set(ah, "horizon_img", ground); Set(ah, "sky_img", skyFill);
                apps.Add(ah);
            }

            // the stock apps on this page, plus ours
            var mgr = root.GetComponent(GameType("MFDAppManager"));
            ObjArray(mgr, "apps", new Object[] { ssd, sg.GetComponent(GameType("StatusGauges")), bfi.GetComponent(GameType("BasicFlightInstruments")) }.Concat(apps).ToArray());

            // the old Medusa engine panels and nozzle gauge are replaced by the engine rows
            foreach (var n in new[] { "engPanel1", "engPanel2", "nozzleGauge" }) Object.DestroyImmediate(R(n).gameObject);
            Object.DestroyImmediate(font);
            var mgrSo = new SerializedObject(mgr); log.AppendLine("tac apps: " + mgrSo.FindProperty("apps").arraySize);
            PrefabUtility.SaveAsPrefabAsset(root, dst);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); PrefabUtility.UnloadPrefabContents(sfb); }
    }
    static void SetLayer(Transform t, int layer) { foreach (var c in t.GetComponentsInChildren<Transform>(true)) c.gameObject.layer = layer; }

    // ------------------------------------------------------------------ crew hatch interiors (2026-10-19)
    // Each roof hatch gets an inner door liner built from the hatch's own PB22_cabin faces at build time, so it follows
    // whatever shape the exterior pass gives the hatch (portholes included): painted door panel, yellow/black ejection
    // border round the outer edge, a dark frame round any window, hinge knuckles along the spine, a grab handle,
    // a jettison handle and latch lugs. The liner is a child of the hatch, so it leaves with it.
    const float LINER_OFF = 0.004f, BAND = 0.035f;
    static readonly Rect UV_HAZARD = new Rect(1024f/2048f, 1f - 1982f/2048f, 256f/2048f, 32f/2048f);
    static readonly Vector2 UV_DARK = new Vector2(1180f/2048f, 1f - 200f/2048f);
    class MB
    {
        public List<Vector3> v = new List<Vector3>(); public List<Vector3> n = new List<Vector3>(); public List<Vector2> uv = new List<Vector2>();
        public List<int> t = new List<int>();
        public void Quad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector2 ua, Vector2 ub, Vector2 uc, Vector2 ud)
        {
            var nn = Vector3.Cross(b - a, d - a).normalized; int k = v.Count;
            v.AddRange(new[] { a, b, c, d }); n.AddRange(new[] { nn, nn, nn, nn }); uv.AddRange(new[] { ua, ub, uc, ud });
            t.AddRange(new[] { k, k + 1, k + 2, k, k + 2, k + 3 });     // front face is the side Cross(b - a, d - a) points to
        }
        public void Flip()
        {   // turn the last quad round
            int q = t.Count - 6; (t[q + 1], t[q + 2]) = (t[q + 2], t[q + 1]); (t[q + 4], t[q + 5]) = (t[q + 5], t[q + 4]);
            for (int z = n.Count - 4; z < n.Count; z++) n[z] = -n[z];
        }
        // box from centre and three half-axes; all six faces, flat dark paint unless uvFront given for the +w face
        public void Box(Vector3 c, Vector3 u, Vector3 vv, Vector3 w, Vector2? uvFront = null, Rect? band = null)
        {
            Vector3[] s = { -u - vv - w, u - vv - w, u + vv - w, -u + vv - w, -u - vv + w, u - vv + w, u + vv + w, -u + vv + w };
            int[][] f = { new[] { 4, 5, 6, 7 }, new[] { 1, 0, 3, 2 }, new[] { 0, 4, 7, 3 }, new[] { 5, 1, 2, 6 }, new[] { 7, 6, 2, 3 }, new[] { 0, 1, 5, 4 } };
            for (int i = 0; i < 6; i++)
            {
                Vector2 a = UV_DARK, b = UV_DARK, cc = UV_DARK, d = UV_DARK;
                if (band.HasValue && i < 1) { var r = band.Value; a = new Vector2(r.xMin, r.yMin); b = new Vector2(r.xMax, r.yMin); cc = new Vector2(r.xMax, r.yMax); d = new Vector2(r.xMin, r.yMax); }
                Quad(c + s[f[i][0]], c + s[f[i][1]], c + s[f[i][2]], c + s[f[i][3]], a, b, cc, d);
                var fc = (s[f[i][0]] + s[f[i][2]])/2f; if (Vector3.Dot(n[n.Count - 1], fc) < 0f) Flip();
            }
        }
        public Mesh Mesh(string name, Mesh into = null)
        {   // refilling the existing asset keeps its GUID and makes the editor re-upload it
            var m = into ?? new Mesh(); m.Clear(); m.name = name;
            m.SetVertices(v); m.SetNormals(n); m.SetUVs(0, uv); m.SetTriangles(t, 0); m.RecalculateBounds(); m.RecalculateTangents();
            return m;
        }
    }

    // Called by PB22Builder.Cockpit() once the hatches exist (after Build), so the liners sit on this build's hatches.
    public static void Hatches(Transform root, Transform c, Transform fFF, Component ac, StringBuilder log)
    {
        var ck = Load<Material>(CK + "PB22_cockpit.mat");
        var added = new List<Object>();
        foreach (var (hn, part, layer) in new[] { ("hatch_PL", c, c.Find("PB22_cockpit_int").gameObject.layer), ("hatch_PR", c, c.Find("PB22_cockpit_int").gameObject.layer),
                                                  ("hatch_NL", fFF, fFF.Find("PB22_rear_int").gameObject.layer), ("hatch_NR", fFF, fFF.Find("PB22_rear_int").gameObject.layer) })
        {
            var h = part.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == hn);
            if (h == null) { log.AppendLine("cockpit: no " + hn); continue; }
            var r = HatchInterior(root, h, layer, ck, log); if (r != null) added.Add(r);
        }
        var so = new SerializedObject(ac); var p = Prop(so, "cockpitRenderers");
        var have = Enumerable.Range(0, p.arraySize).Select(i => p.GetArrayElementAtIndex(i).objectReferenceValue).Where(o => o != null).ToList();
        ObjArray(ac, "cockpitRenderers", have.Concat(added).ToArray());
    }

    static Renderer HatchInterior(Transform root, Transform hatch, int layer, Material ck, StringBuilder log)
    {
        var old = hatch.Find("PB22_hatchliner"); if (old != null) Object.DestroyImmediate(old.gameObject);
        var mr = hatch.GetComponent<MeshRenderer>(); var src = hatch.GetComponent<MeshFilter>().sharedMesh;
        int sub = System.Array.FindIndex(mr.sharedMaterials, m => m != null && m.name.StartsWith("PB22_cabin"));
        if (sub < 0) { log.AppendLine("hatch " + hatch.name + ": no PB22_cabin faces, liner skipped"); return null; }
        var V = src.vertices; var tri = src.GetTriangles(sub);
        // weld by position so the boundary is found across split vertices
        var key = new Dictionary<Vector3Int, int>(); var P = new List<Vector3>(); var remap = new int[V.Length];
        for (int i = 0; i < V.Length; i++)
        {
            var k = Vector3Int.RoundToInt(V[i]*10000f);
            if (!key.TryGetValue(k, out var id)) { id = P.Count; key[k] = id; P.Add(V[i]); }
            remap[i] = id;
        }
        var T = tri.Select(i => remap[i]).ToArray();
        var N = new Vector3[P.Count];
        for (int i = 0; i < T.Length; i += 3)
        {
            var fn = Vector3.Cross(P[T[i + 1]] - P[T[i]], P[T[i + 2]] - P[T[i]]);   // points out of the front (cabin) side
            for (int j = 0; j < 3; j++) N[T[i + j]] += fn;
        }
        for (int i = 0; i < N.Length; i++) N[i] = N[i].normalized;                // into the cabin
        var mb = new MB();
        // door panel: the hatch's inner faces lifted LINER_OFF into the cabin, box-projected light panel paint
        System.Func<Vector3, Vector3, Vector2> Paint = (p, n) =>
        {
            var q = root.InverseTransformPoint(hatch.TransformPoint(p)); var a = Mathf.Abs(n.x) > Mathf.Abs(n.y) ? new Vector2(q.z, q.y) : new Vector2(q.x, q.z);
            return new Vector2(0.03f + Mathf.Repeat(a.x*0.30f, 0.44f), 0.53f + Mathf.Repeat(a.y*0.30f, 0.44f));
        };
        int baseV = mb.v.Count;
        for (int i = 0; i < P.Count; i++) { var p = P[i] + N[i]*LINER_OFF; mb.v.Add(p); mb.n.Add(N[i]); mb.uv.Add(Paint(p, N[i])); }
        mb.t.AddRange(T.Select(i => i + baseV));
        // boundary edges (used by one triangle), kept in triangle order so the inside is on a known side
        var count = new Dictionary<long, int>();
        System.Func<int, int, long> E = (a, b) => a < b ? ((long)a << 32) | (uint)b : ((long)b << 32) | (uint)a;
        for (int i = 0; i < T.Length; i += 3) for (int j = 0; j < 3; j++) { var e = E(T[i + j], T[i + (j + 1)%3]); count[e] = count.TryGetValue(e, out var c0) ? c0 + 1 : 1; }
        var edges = new List<(int a, int b, Vector3 cen)>();
        for (int i = 0; i < T.Length; i += 3)
            for (int j = 0; j < 3; j++)
            {
                int a = T[i + j], b = T[i + (j + 1)%3];
                if (count[E(a, b)] == 1) edges.Add((a, b, (P[T[i]] + P[T[i + 1]] + P[T[i + 2]])/3f));
            }
        // group into loops; the longest loop is the hatch's outer edge (hazard band), the rest are windows (dark frame)
        var next = new Dictionary<int, int>(); for (int i = 0; i < edges.Count; i++) next[edges[i].a] = i;
        var loopOf = new int[edges.Count]; for (int i = 0; i < loopOf.Length; i++) loopOf[i] = -1;
        var loopLen = new List<float>();
        for (int i = 0; i < edges.Count; i++)
        {
            if (loopOf[i] >= 0) continue;
            int id = loopLen.Count; loopLen.Add(0f); int cur = i;
            while (cur >= 0 && loopOf[cur] < 0)
            {
                loopOf[cur] = id; loopLen[id] += (P[edges[cur].b] - P[edges[cur].a]).magnitude;
                cur = next.TryGetValue(edges[cur].b, out var nx) ? nx : -1;
            }
        }
        int outer = loopLen.Count == 0 ? -1 : loopLen.IndexOf(loopLen.Max());
        for (int i = 0; i < edges.Count; i++)
        {
            var (a, b, cen) = edges[i];
            var nrm = (N[a] + N[b]).normalized; var along = P[b] - P[a];
            var inw = Vector3.Cross(nrm, along).normalized; if (Vector3.Dot(inw, cen - (P[a] + P[b])/2f) < 0f) inw = -inw;
            bool haz = loopOf[i] == outer;
            float w = haz ? BAND : 0.02f, lift = LINER_OFF + 0.003f;
            int pieces = Mathf.Max(1, Mathf.CeilToInt(along.magnitude/0.10f));
            for (int k = 0; k < pieces; k++)
            {
                var p0 = P[a] + along*(k/(float)pieces) + nrm*lift; var p1 = P[a] + along*((k + 1)/(float)pieces) + nrm*lift;
                float u1 = UV_HAZARD.xMin + UV_HAZARD.width*Mathf.Min(1f, (p1 - p0).magnitude/0.10f);
                Vector2 A = haz ? new Vector2(UV_HAZARD.xMin, UV_HAZARD.yMin) : UV_DARK, B = haz ? new Vector2(u1, UV_HAZARD.yMin) : UV_DARK;
                Vector2 C = haz ? new Vector2(u1, UV_HAZARD.yMax) : UV_DARK, D = haz ? new Vector2(UV_HAZARD.xMin, UV_HAZARD.yMax) : UV_DARK;
                mb.Quad(p0, p1, p1 + inw*w, p0 + inw*w, A, B, C, D);
                if (Vector3.Dot(mb.n[mb.n.Count - 1], nrm) < 0f) mb.Flip();      // face the crew
            }
        }
        // fittings, placed on the liner in the aircraft frame
        // only points well inside the panel, so a fitting never lands on a window frame or the door edge
        System.Func<Vector3, float> RimDist = q => edges.Min(e =>
        {   // distance to the edge segment, not just its end points (window edges are long)
            var ab = P[e.b] - P[e.a]; float s = Mathf.Clamp01(Vector3.Dot(q - P[e.a], ab)/Mathf.Max(ab.sqrMagnitude, 1e-8f));
            return (P[e.a] + ab*s - q).magnitude;
        });
        var used = new HashSet<int>(T);
        // candidate spots sampled across the faces (the door mesh is coarse, its vertices all sit on edges)
        var spots = new List<(Vector3 p, Vector3 n, float d)>();
        for (int i = 0; i < T.Length; i += 3)
            for (int a = 0; a <= 8; a++) for (int b = 0; a + b <= 8; b++)
            {
                float wa = a/8f, wb = b/8f, wc = 1f - wa - wb;
                var q = P[T[i]]*wa + P[T[i + 1]]*wb + P[T[i + 2]]*wc;
                float dq = RimDist(q); if (dq > 0.035f) spots.Add((q, (N[T[i]]*wa + N[T[i + 1]]*wb + N[T[i + 2]]*wc).normalized, dq));
            }
        if (spots.Count == 0) foreach (var i in used) spots.Add((P[i], N[i], 1f));
        System.Func<Vector3, float, (Vector3 p, Vector3 n)> Spot = (target, clearance) =>
        {   // nearest clear spot to a point given in the aircraft frame, lifted onto the liner
            var tl = hatch.InverseTransformPoint(root.TransformPoint(target));
            var s0 = spots.Where(x => x.d > clearance).DefaultIfEmpty(spots[0]).OrderBy(x => (x.p - tl).sqrMagnitude).First();
            return (s0.p + s0.n*LINER_OFF, s0.n);
        };
        var rootP = P.Where((p, i) => used.Contains(i)).Select(p => root.InverseTransformPoint(hatch.TransformPoint(p))).ToList();
        float side = Mathf.Sign(rootP.Average(p => p.x));
        float zMin = rootP.Min(p => p.z), zMax = rootP.Max(p => p.z), zc = (zMin + zMax)/2f, len = zMax - zMin;
        var fwd = hatch.InverseTransformDirection(root.forward);
        // grab handle, upper middle of the door
        {
            var (p, n) = Spot(new Vector3(side*0.85f, 0.45f, zc + len*0.10f), 0.10f);
            foreach (var dz in new[] { -0.075f, 0.075f }) mb.Box(p + fwd*dz + n*0.025f, fwd*0.008f, Vector3.Cross(n, fwd).normalized*0.008f, n*0.025f);
            mb.Box(p + n*0.052f, fwd*0.095f, Vector3.Cross(n, fwd).normalized*0.011f, n*0.008f);
        }
        // jettison handle: striped T-handle low and aft on the door, on a dark base plate
        {
            var (p, n) = Spot(new Vector3(side*0.88f, 0.30f, zc - len*0.25f), 0.10f); var up = Vector3.Cross(fwd, n).normalized*side;
            mb.Box(p + n*0.003f, fwd*0.05f, up*0.035f, n*0.003f);
            mb.Box(p + n*0.022f, fwd*0.007f, up*0.007f, n*0.018f);
            mb.Box(p + n*0.045f, fwd*0.045f, up*0.012f, n*0.008f, null, new Rect(UV_HAZARD.xMin, UV_HAZARD.yMin, UV_HAZARD.width*0.9f, UV_HAZARD.height));
        }
        // latch lugs along the lower edge
        {
            float yLow = rootP.Min(p => p.y);
            foreach (var f in new[] { 0.2f, 0.5f, 0.8f })
            {
                var (p, n) = Spot(new Vector3(side*0.9f, yLow + 0.03f, zMin + len*f), 0.035f);
                mb.Box(p + n*0.012f, fwd*0.03f, Vector3.Cross(n, fwd).normalized*0.018f, n*0.012f);
            }
        }
        // hinge knuckles along the spine edge
        {
            float edgeX = rootP.Min(p => Mathf.Abs(p.x));
            var spine = rootP.Where(p => Mathf.Abs(p.x) < edgeX + 0.02f).ToList();
            if (spine.Count > 0)
            {   // knuckles straddle the seam just under the spine, leaves reach onto the door frame
                float y = spine.Min(p => p.y) - 0.012f, x = side*(edgeX - 0.004f);
                foreach (var f in new[] { 0.18f, 0.5f, 0.82f })
                {
                    var c = hatch.InverseTransformPoint(root.TransformPoint(new Vector3(x, y, zMin + len*f)));
                    var upL = hatch.InverseTransformDirection(root.up); var sd = hatch.InverseTransformDirection(root.right);
                    mb.Box(c, fwd*0.045f, upL*0.014f, sd*0.014f);
                    mb.Box(c + sd*(side*0.028f) + upL*0.008f, fwd*0.04f, upL*0.004f, sd*0.024f);      // hinge leaf onto the door
                }
            }
        }
        string path = CK + "PB22_hatchliner_" + hatch.name + ".asset";
        var have = AssetDatabase.LoadAssetAtPath<Mesh>(path);
        var mesh = mb.Mesh("PB22_hatchliner_" + hatch.name, have);
        if (have != null) EditorUtility.SetDirty(mesh); else AssetDatabase.CreateAsset(mesh, path);
        var go = new GameObject("PB22_hatchliner"); go.layer = layer; go.transform.SetParent(hatch, false);
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        var r = go.AddComponent<MeshRenderer>(); r.sharedMaterial = ck; r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
        log.AppendLine("hatch " + hatch.name + ": liner " + mesh.vertexCount + " verts, " + loopLen.Count + " edge loops");
        return r;
    }

    // ------------------------------------------------------------------ build into the prefab
    // c = cockpit part (front crew), fFF = forward fuselage part (rear crew), ac = Aircraft, engines = engine sound sources.
    public static void Build(Transform root, Transform c, Transform fFF, Component ac, Object[] engines, StringBuilder log)
    {
        foreach (var n in MINE)
            foreach (var p in new[] { c, fFF }) { var old = p.Find(n); if (old != null) Object.DestroyImmediate(old.gameObject); }

        var fbx = AssetDatabase.LoadAllAssetsAtPath(CK + "PB22_cockpit.fbx");
        var meshes = fbx.OfType<Mesh>().ToDictionary(m => m.name);
        var model = Load<GameObject>(CK + "PB22_cockpit.fbx");
        var ck = Load<Material>(CK + "PB22_cockpit.mat");
        var mats = new Dictionary<string, Material>
        {
            { "PB22_cockpit", ck }, { "PB22_screen", Load<Material>(CK + "PB22_screen.mat") }, { "PB22_cabin", Load<Material>(CK + "PB22_cabin.mat") },
            { "tacScreenDisplay", Load<Material>(PH + "Material/tacScreenDisplay_PLACEHOLDER.mat") },
            { "CockpitWarningLight", Load<Material>(PH + "Material/CockpitWarningLight_PLACEHOLDER.mat") },
            { "Matte_black", Load<Material>(PH + "Material/Matte_black_PLACEHOLDER.mat") },
            { "aircraft_structure", Load<Material>(PH + "Material/aircraft_structure_PLACEHOLDER.mat") },
        };
        System.Func<string, Transform, Vector3, Transform> Part = (name, parent, pivot) =>
        {
            var src = model.transform.Cast<Transform>().First(t => t.name == name);
            var go = new GameObject("PB22_" + name); go.layer = parent.gameObject.layer;
            go.transform.SetParent(parent, false);
            go.transform.position = root.TransformPoint(pivot); go.transform.rotation = root.rotation;
            go.AddComponent<MeshFilter>().sharedMesh = meshes[src.GetComponent<MeshFilter>().sharedMesh.name];
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterials = src.GetComponent<MeshRenderer>().sharedMaterials.Select(m => mats.First(kv => m.name.StartsWith(kv.Key)).Value).ToArray();
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            return go.transform;
        };

        var interior = Part("cockpit_int", c, Vector3.zero);
        var lights = Part("warningLights", c, Vector3.zero);
        var tac = Part("tacScreen", c, Vector3.zero);
                var throttle = Part("throttle", c, THROTTLE_PIVOT);
        var simple = Part("cockpit_int_simple", c, Vector3.zero);
        var rear = Part("rear_int", fFF, Vector3.zero);
        var rearScreens = Part("rear_screens", fFF, Vector3.zero);
        var rearSimple = Part("rear_int_simple", fFF, Vector3.zero);

        // stock cockpit systems on our interior
        var cockpit = interior.gameObject.AddComponent(GameType("Cockpit"));
        Set(cockpit, "tacScreenRender", tac.GetComponent<Renderer>());
        Set(cockpit, "tacScreenUIPrefab", Load<GameObject>(CK + "PB22_tacScreen.prefab"));
        Set(cockpit, "aircraft", ac);
        ObjArray(cockpit, "engineSources", engines);
        { var so = new SerializedObject(cockpit); so.FindProperty("joysticks").arraySize = 0;
          var th = so.FindProperty("throttles"); th.arraySize = 1; var e = th.GetArrayElementAtIndex(0);
          e.FindPropertyRelative("rotation").boolValue = true; e.FindPropertyRelative("motion").boolValue = false;
          e.FindPropertyRelative("transform").objectReferenceValue = throttle; e.FindPropertyRelative("range").floatValue = 54f;   // stock throttle swing (Medusa, Alkyon)
          so.ApplyModifiedPropertiesWithoutUndo(); }
        var cwl = interior.gameObject.AddComponent(GameType("CockpitWarningLights"));
        Set(cwl, "aircraft", ac); ObjArray(cwl, "lightRenderers", lights.GetComponent<Renderer>());
        lights.GetComponent<Renderer>().enabled = false;   // stock: off until a missile is tracked, and kept out of cockpitRenderers so the view switch never lights it

        // yokes: column pitches about the floor pivot, wheel rolls about its own axis; both are stock ControlSurfaces on the cockpit part
        var aero = c.GetComponent(GameType("AeroPart"));
        var yokeRenderers = new List<Renderer>();
        foreach (var s in new[] { "L", "R" })
        {
            var colPivot = s == "L" ? COL_PIVOT_L : COL_PIVOT_R; var hub = s == "L" ? HUB_L : HUB_R;
            var yoke = new GameObject("PB22_yoke_" + s).transform; yoke.SetParent(c, false);
            yoke.position = root.TransformPoint(colPivot); yoke.rotation = root.rotation; yoke.gameObject.layer = c.gameObject.layer;
            var colHinge = new GameObject("yoke_col_" + s + "_hinge").transform; colHinge.SetParent(yoke, false);
            var col = Part("yoke_col_" + s, colHinge, colPivot);
            Surface(yoke.gameObject, colHinge.gameObject, aero, 12f, 0f);              // pull back: column top comes aft

            float t = COL_TILT * Mathf.Deg2Rad;
            var axis = root.TransformDirection(new Vector3(0f, -Mathf.Sin(t), Mathf.Cos(t)));     // wheel normal, pointing forward
            var up = root.TransformDirection(new Vector3(0f, Mathf.Cos(t), Mathf.Sin(t)));
            var wheel = new GameObject("yoke_wheel_" + s).transform; wheel.SetParent(colHinge, false);
            wheel.position = root.TransformPoint(hub); wheel.rotation = Quaternion.LookRotation(Vector3.Cross(axis, up), up);   // local X = wheel axis
            var wheelHinge = new GameObject("yoke_wheel_" + s + "_hinge").transform; wheelHinge.SetParent(wheel, false);
            var wm = Part("yoke_wheel_" + s, wheelHinge, hub);
            Surface(wheel.gameObject, wheelHinge.gameObject, aero, 0f, -60f);          // right roll: wheel top turns right
            yokeRenderers.Add(col.GetComponent<Renderer>()); yokeRenderers.Add(wm.GetComponent<Renderer>());
            foreach (var tr in yoke.GetComponentsInChildren<Transform>(true)) tr.gameObject.layer = c.gameObject.layer;   // cockpit camera layer, or the yokes never draw
        }

        // crew: front seats up RAISE, rear crew turned to face their aft display wall; seats are the bundled PB-22 copies
        var seatMesh = Load<Mesh>(CK + "PB22_EjectionSeat.asset"); var seatMat = Load<Material>(CK + "PB22_seat.mat");
        foreach (var n in new[] { "crew_Pilot", "crew_CoPilot", "crew_Navigator", "crew_WSO" })
        {
            var crew = c.Find(n) ?? fFF.Find(n); if (crew == null) { log.AppendLine("cockpit: no " + n); continue; }
            if (n == "crew_Pilot" || n == "crew_CoPilot")
            {   // absolute height (0.4.4 seat y -0.34 + RAISE), so a layout that already raised the seat refs is not raised twice
                var lp = root.InverseTransformPoint(crew.position); lp.y = FRONT_SEAT_Y; crew.position = root.TransformPoint(lp);
            }
            else crew.rotation = Quaternion.AngleAxis(180f, root.up) * crew.rotation;
            var seat = crew.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == "EjectionSeat");
            if (seat == null) { log.AppendLine("cockpit: " + n + " has no EjectionSeat"); continue; }
            seat.GetComponent<MeshFilter>().sharedMesh = seatMesh;
            seat.GetComponent<MeshRenderer>().sharedMaterials = new[] { seatMat };
            var mc = seat.GetComponent<MeshCollider>(); if (mc != null) mc.sharedMesh = seatMesh;
        }

        // gauge needles, attitude balls and rudder pedals: moved by the PB-22 plugin (PB22Gauges). Every one is its own mesh object
        // with no empty parent: a needle's mesh is re-based so the object's z is the gauge axis (into the panel) and y is 12 o'clock.
        var needleRenderers = new List<Renderer>();
        foreach (var old in c.Cast<Transform>().Where(t => t.name.StartsWith("PB22_gauge_") || t.name.StartsWith("PB22_adi_") || t.name.StartsWith("PB22_pedal_")).ToList())
            Object.DestroyImmediate(old.gameObject);
        string ntxt = Application.dataPath + "/../" + CK + "PB22_cockpit_needles.txt";
        foreach (var line in System.IO.File.ReadAllLines(ntxt))
        {
            var f = line.Split(' '); if (f.Length < 10) continue;
            System.Func<int, float> F = i => float.Parse(f[i], System.Globalization.CultureInfo.InvariantCulture);
            var pv = new Vector3(F(1), F(2), F(3)); var axis = new Vector3(F(4), F(5), F(6)); var up = new Vector3(F(7), F(8), F(9));
            var nd = Part(f[0], c, pv);
            if (f[0].StartsWith("ndl_"))
            {
                var q = Quaternion.LookRotation(axis, up); var qi = Quaternion.Inverse(q);
                var mf = nd.GetComponent<MeshFilter>(); var src = mf.sharedMesh;
                string mpath = CK + "PB22_gauge_" + f[0].Substring(4) + ".asset";
                var m = AssetDatabase.LoadAssetAtPath<Mesh>(mpath); bool fresh = m == null; if (fresh) m = new Mesh();
                m.Clear(); m.name = "PB22_gauge_" + f[0].Substring(4);
                m.SetVertices(src.vertices.Select(v => qi * v).ToList()); m.SetNormals(src.normals.Select(v => qi * v).ToList());
                m.SetUVs(0, src.uv.ToList()); m.subMeshCount = src.subMeshCount;
                for (int s = 0; s < src.subMeshCount; s++) m.SetTriangles(src.GetTriangles(s), s);
                m.RecalculateBounds(); m.RecalculateTangents();
                if (fresh) AssetDatabase.CreateAsset(m, mpath); else EditorUtility.SetDirty(m);
                mf.sharedMesh = m;
                nd.rotation = root.rotation * q; nd.name = "PB22_gauge_" + f[0].Substring(4);
            }
            needleRenderers.Add(nd.GetComponent<Renderer>());
        }
        log.AppendLine("cockpit: " + needleRenderers.Count + " plugin-driven parts (needles, balls, pedals)");

        var inside = new List<Object> { interior.GetComponent<Renderer>(), tac.GetComponent<Renderer>(),
                                        throttle.GetComponent<Renderer>(), rear.GetComponent<Renderer>(),
                                        rearScreens.GetComponent<Renderer>() };
        inside.AddRange(yokeRenderers.Cast<Object>());
        inside.AddRange(needleRenderers.Cast<Object>());
        ObjArray(ac, "cockpitRenderers", inside.ToArray());
        ObjArray(ac, "exteriorRenderers", simple.GetComponent<Renderer>(), rearSimple.GetComponent<Renderer>());
        log.AppendLine("cockpit: PB-22 interior built (" + inside.Count + " interior renderers)");
    }

    static void Surface(GameObject host, GameObject hinge, Component aero, float pitch, float roll)
    {
        var cs = host.AddComponent(GameType("ControlSurface"));
        Set(cs, "pitchRange", pitch); Set(cs, "rollRange", roll); Set(cs, "yawRange", 0f); Set(cs, "brakeRange", 0f);
        Set(cs, "attachedSurface", aero); Set(cs, "visibleMesh", hinge); Set(cs, "flap", false);
        Set(cs, "servoSpeed", 120f); Set(cs, "maxVolumeSpeed", 340f); Set(cs, "splitPitchMin", 0.5f); Set(cs, "splitPitchMax", 2f);
    }
}
