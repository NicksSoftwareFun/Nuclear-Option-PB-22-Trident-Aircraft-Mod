using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

// Rebuilds PB22Trident.prefab from a pristine copy of the Alkyon AB-4 clone plus the PB-22 art (PB22_parts.fbx + PB22_layout.json).
// Run from the menu (PB22 > Rebuild Prefab) or PB22Builder.Build(). Every value is a literal on purpose.
public static class PB22Builder
{
    const string MOD = "Assets/Blueprinter/Mods/PB22Trident/";
    const string ART = MOD + "Art/";
    const string SRC = "Assets/PB22Tools/PB22Trident_ab4src.prefab";
    const string DST = MOD + "PB22Trident.prefab";

    [System.Serializable] class E { public string name, coll, kind, parent; public float[] pos, rot, bmin, bmax; public string[] mats; public bool keep_frame; }
    [System.Serializable] class W { public E[] items; }

    static Dictionary<string, E> L;
    static Dictionary<string, Mesh> M;
    static Dictionary<string, Material> MAT;
    static Transform root;
    static StringBuilder log;
    static Material lodMat;
    static readonly HashSet<Object> doomed = new HashSet<Object>();
    static readonly List<GameObject> doomedRoots = new List<GameObject>();
    static readonly List<Component> doomedComps = new List<Component>();

    [MenuItem("PB22/Rebuild Prefab")]
    public static void Menu() { Debug.Log(Build()); }

    // ------------------------------------------------------------------ helpers
    static Vector3 BtoU(float[] p) { return new Vector3(p[0], p[2] - 2.85f, p[1]); }
    static Vector3 P(string n) { return BtoU(Lget(n).pos); }
    static Quaternion R(string n) { var r = Lget(n).rot; return new Quaternion(-r[1], -r[3], -r[2], r[0]); }
    static E Lget(string n) { E e; if (!L.TryGetValue(n, out e)) throw new System.Exception("layout missing " + n); return e; }

    static Transform Find(Transform under, string name)
    {
        if (under.name == name) return under;
        foreach (Transform c in under) { var r = Find(c, name); if (r != null) return r; }
        return null;
    }
    static Transform Need(Transform under, string name)
    {
        var t = Find(under, name);
        if (t == null) throw new System.Exception("missing " + name + " under " + under.name);
        return t;
    }
    static Transform New(string name, Transform parent)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        return go.transform;
    }
    static Component C(Transform t, string type)
    {
        return t.GetComponents<Component>().FirstOrDefault(c => c != null && c.GetType().Name == type);
    }
    static void Place(Transform t, string n, bool rot = false)
    {
        t.position = P(n);
        t.rotation = rot ? R(n) : Quaternion.identity;
    }
    static Material[] Mats(string mesh)
    {
        var e = Lget(mesh);
        return e.mats.Select(m => MAT[m]).ToArray();
    }
    static void SetMesh(Transform t, string mesh)
    {
        var mf = t.GetComponent<MeshFilter>(); if (mf == null) mf = t.gameObject.AddComponent<MeshFilter>();
        mf.sharedMesh = M[mesh];
        var mr = t.GetComponent<MeshRenderer>(); if (mr == null) mr = t.gameObject.AddComponent<MeshRenderer>();
        mr.sharedMaterials = Mats(mesh);
    }
    static void NoMesh(Transform t)
    {
        var mf = t.GetComponent<MeshFilter>();
        if (mf != null) mf.sharedMesh = null;
    }
    static void SetCol(Transform t, string col)
    {
        var mc = t.GetComponent<MeshCollider>();
        if (mc == null) { mc = t.gameObject.AddComponent<MeshCollider>(); mc.convex = true; }
        mc.sharedMesh = M[col];
    }
    static void SetLoD(Transform t, string col)
    {
        var l = t.Find("LoD");
        if (l == null)
        {
            l = New("LoD", t);
            l.gameObject.AddComponent<MeshFilter>();
            l.gameObject.AddComponent<MeshRenderer>().sharedMaterial = lodMat;
        }
        l.localPosition = Vector3.zero; l.localRotation = Quaternion.identity; l.localScale = Vector3.one;
        l.GetComponent<MeshFilter>().sharedMesh = M[col];
    }
    // mesh object with its own pivot: position from the layout, world-aligned unless the layout says keep_frame
    static Transform Part(Transform t, string mesh)
    {
        Place(t, mesh, Lget(mesh).keep_frame);
        SetMesh(t, mesh);
        return t;
    }

    static SerializedProperty Prop(SerializedObject so, string path)
    {
        var p = so.FindProperty(path);
        if (p == null) log.AppendLine("MISSING PROP " + so.targetObject.GetType().Name + "." + path);
        return p;
    }
    static void Set(Component c, string path, object v)
    {
        if (c == null) { log.AppendLine("NULL COMPONENT for " + path); return; }
        var so = new SerializedObject(c);
        var p = Prop(so, path);
        if (p == null) return;
        if (v is float) p.floatValue = (float)v;
        else if (v is int) { if (p.propertyType == SerializedPropertyType.Float) p.floatValue = (int)v; else p.intValue = (int)v; }
        else if (v is bool) p.boolValue = (bool)v;
        else if (v is Vector3) p.vector3Value = (Vector3)v;
        else if (v is string) p.stringValue = (string)v;
        else if (v is AnimationCurve) p.animationCurveValue = (AnimationCurve)v;
        else if (v == null || v is Object) p.objectReferenceValue = (Object)v;
        else log.AppendLine("UNSUPPORTED " + path);
        so.ApplyModifiedPropertiesWithoutUndo();
    }
    static Object Get(Component c, string path)
    {
        var so = new SerializedObject(c);
        var p = Prop(so, path);
        return p == null ? null : p.objectReferenceValue;
    }
    static void Size(Component c, string path, int n)
    {
        var so = new SerializedObject(c);
        var p = Prop(so, path);
        if (p == null) return;
        p.arraySize = n;
        so.ApplyModifiedPropertiesWithoutUndo();
    }
    static void Joints(Component ap, params object[] pairs)
    {
        // pairs: connected AeroPart, break strength (force and torque), ...
        int n = pairs.Length / 2;
        Size(ap, "joints", n);
        for (int i = 0; i < n; i++)
        {
            string j = "joints.Array.data[" + i + "].";
            Set(ap, j + "connectedPart", (Object)pairs[2 * i]);
            Set(ap, j + "tensor", null);
            Set(ap, j + "anchor", null);
            Set(ap, j + "breakForce", (float)pairs[2 * i + 1]);
            Set(ap, j + "breakTorque", (float)pairs[2 * i + 1]);
            Set(ap, j + "solverIterations", 6);
        }
    }
    static void ObjAppend(Component c, string path, Object item)
    {
        var so = new SerializedObject(c);
        var p = Prop(so, path);
        if (p == null || item == null) return;
        for (int i = 0; i < p.arraySize; i++) if (p.GetArrayElementAtIndex(i).objectReferenceValue == item) return;
        p.arraySize++;
        p.GetArrayElementAtIndex(p.arraySize - 1).objectReferenceValue = item;
        so.ApplyModifiedPropertiesWithoutUndo();
    }
    static void ObjArray(Component c, string path, params Object[] items)
    {
        var so = new SerializedObject(c);
        var p = Prop(so, path);
        if (p == null) return;
        p.arraySize = items.Length;
        for (int i = 0; i < items.Length; i++) p.GetArrayElementAtIndex(i).objectReferenceValue = items[i];
        so.ApplyModifiedPropertiesWithoutUndo();
    }

    static void Doom(Transform t)
    {
        if (t == null) return;
        doomedRoots.Add(t.gameObject);
        foreach (var tr in t.GetComponentsInChildren<Transform>(true))
        {
            doomed.Add(tr.gameObject);
            foreach (var c in tr.GetComponents<Component>()) if (c != null) doomed.Add(c);
        }
    }
    // remove every reference to a doomed object: the innermost array element holding it goes, a plain field is nulled
    static void Purge()
    {
        foreach (var c in root.GetComponentsInChildren<Component>(true))
        {
            if (c == null || doomed.Contains(c) || c is Transform) continue;
            var so = new SerializedObject(c);
            var it = so.GetIterator();
            var hits = new List<string>();
            while (it.Next(true))
                if (it.propertyType == SerializedPropertyType.ObjectReference && it.objectReferenceValue != null && doomed.Contains(it.objectReferenceValue))
                    hits.Add(it.propertyPath);
            if (hits.Count == 0) continue;
            var dels = new List<KeyValuePair<string, int>>();
            foreach (var h in hits)
            {
                int k = h.LastIndexOf(".Array.data[");
                if (k < 0) { so.FindProperty(h).objectReferenceValue = null; log.AppendLine("null " + c.name + "." + c.GetType().Name + "." + h); continue; }
                int e = h.IndexOf(']', k);
                dels.Add(new KeyValuePair<string, int>(h.Substring(0, k), int.Parse(h.Substring(k + 12, e - k - 12))));
            }
            foreach (var d in dels.Distinct().OrderByDescending(x => x.Value))
            {
                var arr = so.FindProperty(d.Key);
                int before = arr.arraySize;
                arr.DeleteArrayElementAtIndex(d.Value);
                if (arr.arraySize == before) arr.DeleteArrayElementAtIndex(d.Value);
                log.AppendLine("drop " + c.name + "." + c.GetType().Name + "." + d.Key + "[" + d.Value + "]");
            }
            so.ApplyModifiedPropertiesWithoutUndo();
        }
        foreach (var g in doomedRoots) if (g != null) Object.DestroyImmediate(g);
        foreach (var c in doomedComps) if (c != null) Object.DestroyImmediate(c);
        doomed.Clear(); doomedRoots.Clear(); doomedComps.Clear();
    }

    // nozzles: bare brushed metal on every livery (the liveries only repaint the skin material)
    static void NozzleMetal(Transform nz)
    {
        // dull heat-worn steel, not polished stainless (set every build: LitMat keeps an existing asset as it is)
        var m = LitMat("PB22_nozzle_metal", new Color32(100, 97, 92, 255), 0.18f);
        m.SetColor("_BaseColor", new Color32(100, 97, 92, 255)); m.SetFloat("_Smoothness", 0.18f);
        m.SetFloat("_Metallic", 0.45f); EditorUtility.SetDirty(m);
        var mr = nz.GetComponent<MeshRenderer>(); var mats = mr.sharedMaterials;
        for (int i = 0; i < mats.Length; i++) if (mats[i] != null && mats[i] == MAT["PB22_mech"]) mats[i] = m;
        mr.sharedMaterials = mats;
    }

    static Material LitMat(string name, Color col, float smooth)
    {
        string path = ART + name + ".mat";
        var m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m != null) return m;
        m = new Material(MAT["PB22_mech"]);
        m.name = name;
        m.SetColor("_BaseColor", col);
        m.SetFloat("_Smoothness", smooth);
        m.SetTexture("_BaseMap", null);
        AssetDatabase.CreateAsset(m, path);
        return m;
    }

    static float Radius(string wheelMesh) { return M[wheelMesh].bounds.extents.y; }
    static void FitBox(Transform t, Mesh m)
    {
        var b = t.GetComponent<BoxCollider>();
        if (b == null) return;
        b.center = m.bounds.center; b.size = m.bounds.size;
    }

    // ------------------------------------------------------------------ build
    public static string Build()
    {
        log = new StringBuilder();
        if (AssetDatabase.LoadAssetAtPath<GameObject>(SRC) == null)
        {
            if (!AssetDatabase.IsValidFolder("Assets/PB22Tools")) AssetDatabase.CreateFolder("Assets", "PB22Tools");
            AssetDatabase.CopyAsset(DST, SRC);
            log.AppendLine("saved pristine AB-4 copy to " + SRC);
        }
        var json = System.IO.File.ReadAllText(ART + "PB22_layout.json");
        L = JsonUtility.FromJson<W>("{\"items\":" + json + "}").items.ToDictionary(e => e.name);
        M = new Dictionary<string, Mesh>();
        foreach (var o in AssetDatabase.LoadAllAssetsAtPath(ART + "PB22_parts.fbx")) if (o is Mesh) M[o.name] = (Mesh)o;
        MAT = new Dictionary<string, Material>();
        foreach (var n in new[] { "PB22_skin", "PB22_mech", "PB22_glass" }) MAT[n] = AssetDatabase.LoadAssetAtPath<Material>(ART + n + ".mat");
        // mechanism grey a touch above the skin base (86,94,97) so aux doors, petals and well machinery do not stand out
        MAT["PB22_mech"].SetColor("_BaseColor", new Color32(86, 94, 97, 255)); EditorUtility.SetDirty(MAT["PB22_mech"]);
        MAT["PB22_dark"] = LitMat("PB22_dark", new Color(0.05f, 0.05f, 0.055f), 0.3f);
        MAT["PB22_tyre"] = LitMat("PB22_tyre", new Color(0.07f, 0.07f, 0.07f), 0.2f);
        MAT["PB22_int"] = LitMat("PB22_int", new Color(0.16f, 0.17f, 0.18f), 0.25f);
        // systems colours: fuel cells, hydraulics, wiring, oxygen, fuel lines, fire bottles
        MAT["PB22_fuelcell"] = LitMat("PB22_fuelcell", new Color(0.30f, 0.26f, 0.19f), 0.2f);
        MAT["PB22_hyd"] = LitMat("PB22_hyd", new Color(0.78f, 0.60f, 0.12f), 0.35f);
        MAT["PB22_wire"] = LitMat("PB22_wire", new Color(0.58f, 0.56f, 0.48f), 0.2f);
        MAT["PB22_oxy"] = LitMat("PB22_oxy", new Color(0.17f, 0.40f, 0.22f), 0.35f);
        MAT["PB22_fuelline"] = LitMat("PB22_fuelline", new Color(0.48f, 0.15f, 0.09f), 0.3f);
        MAT["PB22_red"] = LitMat("PB22_red", new Color(0.58f, 0.08f, 0.06f), 0.35f);
        // visible-surface materials (0.4.6): anything seen on an intact aircraft (gear, wells, bays, sensors) is solid painted
        // metal; the engine fan matches the nozzles; the crew compartment lining takes the cockpit's own cabin texture
        MAT["PB22_metal"] = LitMat("PB22_metal", new Color32(86, 94, 97, 255), 0.3f);
        MAT["PB22_noz"] = LitMat("PB22_nozzle_metal", new Color32(100, 97, 92, 255), 0.18f);
        MAT["PB22_cabin"] = AssetDatabase.LoadAssetAtPath<Material>(MOD + "Art/Cockpit/PB22_cabin.mat");
        if (MAT["PB22_cabin"] == null) { Debug.LogWarning("Art/Cockpit/PB22_cabin.mat not found: run the cockpit SetupAssets"); MAT["PB22_cabin"] = LitMat("PB22_cabin_plain", new Color32(150, 152, 150, 255), 0.25f); }
        // internal structure uses the game's own shared structure materials, like every stock aircraft
        // (mechanism and frames: jet_mechanical; tubs, liners and floors: aircraft_structure); UVs are at stock world scale
        var jm = AssetDatabase.LoadAssetAtPath<Material>(PH_MAT + "jet_mechanical_PLACEHOLDER.mat");
        var asm = AssetDatabase.LoadAssetAtPath<Material>(PH_MAT + "aircraft_structure_PLACEHOLDER.mat");
        if (jm != null) MAT["PB22_mech"] = jm; else Debug.LogWarning("jet_mechanical_PLACEHOLDER not found");
        if (asm != null) MAT["PB22_int"] = asm; else Debug.LogWarning("aircraft_structure_PLACEHOLDER not found");
        // canopy and window glass: the Darkreach's glass, as stock
        var sfb = AssetDatabase.LoadAssetAtPath<Material>(PH_MAT + "SFB_glass_PLACEHOLDER.mat");
        if (sfb != null) MAT["PB22_glass"] = sfb; else Debug.LogWarning("SFB_glass_PLACEHOLDER not found");

        root = PrefabUtility.LoadPrefabContents(SRC).transform;
        try
        {
            lodMat = root.Find("LoD").GetComponent<MeshRenderer>().sharedMaterial;
            Body();
            Cockpit();
            Wings();
            Tail();
            Engines();
            MainGear("L", -1); MainGear("R", 1);
            NoseGear();
            Bays();
            Pylons();
            Misc();
            Purge();
            if (capsule != null) { Object.DestroyImmediate(capsule); capsule = null; }
            Aero();
            Durability();
            Lights();
            SkinCoverage();
            Loadouts();
            Decals();
            Lods();
            PrefabUtility.SaveAsPrefabAsset(root.gameObject, DST);
            log.AppendLine("saved " + DST);
        }
        catch (System.Exception ex) { log.AppendLine("ERROR " + ex); }
        finally { PrefabUtility.UnloadPrefabContents(root.gameObject); }
        return log.ToString();
    }

    // ------------------------------------------------------------------ fuselage
    static void Body()
    {
        SetMesh(root, "fuselage"); SetCol(root, "fuselage_colmesh"); SetLoD(root, "fuselage_colmesh");
        var fF = root.Find("fuselage_F"); Part(fF, "fuselage_F"); SetCol(fF, "fuselage_F_colmesh"); SetLoD(fF, "fuselage_F_colmesh");
        var fFF = fF.Find("fuselage_FF"); Part(fFF, "fuselage_FF"); SetCol(fFF, "fuselage_FF_colmesh"); SetLoD(fFF, "fuselage_FF_colmesh");
        var nose = fFF.Find("nose"); Part(nose, "nose"); SetCol(nose, "nose_colmesh"); SetLoD(nose, "nose_colmesh");
        nose.Find("targetCamPoint_F").position = BtoU(new[] { 0f, 17f - 4.7f, 1.28f });
        Doom(fFF.Find("cheek_FL")); Doom(fFF.Find("cheek_FR")); Doom(fF.Find("cheek_RL")); Doom(fF.Find("cheek_RR"));

        var fR = root.Find("fuselage_R");
        // the AB-4 rear fuselage carried the rear bay; ours sits in the centre section (root)
        fR.Find("weaponBay_rear").SetParent(root, true);
        fR.Find("bayDoorHinge_RL1").SetParent(root, true);
        fR.Find("bayDoorHinge_RR1").SetParent(root, true);
        Part(fR, "fuselage_R"); SetCol(fR, "fuselage_R_colmesh"); SetLoD(fR, "fuselage_R_colmesh");
        fR.Find("CoM").position = new Vector3(0f, 0.2f, -12.5f);
        var tail = fR.Find("tail"); Part(tail, "tail"); SetCol(tail, "tail_colmesh"); SetLoD(tail, "tail_colmesh");
        tail.Find("targetCamPoint_R").position = BtoU(new[] { 0f, 17f - 33.4f, 3.28f });
        tail.Find("landingCam").position = BtoU(new[] { 0f, 17f - 27f, 1.35f });

        foreach (var s in new[] { "L", "R" })
        {
            var it = root.Find("intake_" + s); Part(it, "intake_" + s); SetCol(it, "intake_" + s + "_colmesh"); SetLoD(it, "intake_" + s + "_colmesh");
            foreach (Transform c in it.Cast<Transform>().ToArray())
                if (c.name.StartsWith("heater") || c.name.StartsWith("slimelight")) Doom(c);
            var gb = root.Find("gearbay_" + s); Part(gb, "gearbay_" + s); SetCol(gb, "gearbay_" + s + "_colmesh"); SetLoD(gb, "gearbay_" + s + "_colmesh");
            var wr = root.Find("wingroot_" + s); Part(wr, "wingroot_" + s); SetCol(wr, "wingroot_" + s + "_colmesh"); SetLoD(wr, "wingroot_" + s + "_colmesh");
        }
    }

    // ------------------------------------------------------------------ cockpit: integrated crew cabin, four ejection seats (Medusa crew stations)
    const string EW1 = "Assets/Blueprinter/_donotship/GameObject/EW1_PLACEHOLDER.prefab";
    static System.Type GameType(string n)
    {
        foreach (var a in System.AppDomain.CurrentDomain.GetAssemblies()) { var t = a.GetType(n); if (t != null) return t; }
        throw new System.Exception("no type " + n);
    }
    static Transform FindIn(Transform under, string name) { return under.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == name); }
    // copy a Medusa object into our prefab, keeping its pose relative to the Medusa front cockpit part
    static Transform CopyEW(Transform src, Transform ewRef, Transform parent, string name = null)
    {
        var go = (GameObject)Object.Instantiate(src.gameObject, parent, false);
        go.name = name ?? src.name;
        go.transform.localPosition = ewRef.InverseTransformPoint(src.position);
        go.transform.localRotation = Quaternion.Inverse(ewRef.rotation) * src.rotation;
        go.transform.localScale = src.lossyScale;
        return go.transform;
    }
    // references that still point into the Medusa prefab are re-pointed to our copy of the same name, or cleared
    static void Repoint(IEnumerable<Transform> copies, Transform ewRoot)
    {
        var mine = root.GetComponentsInChildren<Transform>(true);
        foreach (var t in copies.SelectMany(x => x.GetComponentsInChildren<Transform>(true)))
            foreach (var c in t.GetComponents<Component>())
            {
                if (c == null || c is Transform) continue;
                var so = new SerializedObject(c); var it = so.GetIterator(); bool dirty = false;
                while (it.Next(true))
                {
                    if (it.propertyType != SerializedPropertyType.ObjectReference || it.objectReferenceValue == null) continue;
                    var o = it.objectReferenceValue;
                    if (EditorUtility.IsPersistent(o)) continue;
                    Transform ot = o is Component ? ((Component)o).transform : o is GameObject ? ((GameObject)o).transform : null;
                    if (ot == null || ot.root == root) continue;
                    var hit = mine.FirstOrDefault(m => m.name == ot.name);
                    Object rep = null;
                    if (hit != null) rep = o is GameObject ? (Object)hit.gameObject : o is Transform ? (Object)hit : hit.GetComponent(o.GetType());
                    it.objectReferenceValue = rep; dirty = true;
                    if (rep == null) log.AppendLine("cleared " + c.name + "." + c.GetType().Name + "." + it.propertyPath + " (was " + ot.name + ")");
                }
                if (dirty) so.ApplyModifiedPropertiesWithoutUndo();
            }
    }
    static void SetEnum(Component c, string path, string value)
    {
        var so = new SerializedObject(c); var p = Prop(so, path); if (p == null) return;
        p.enumValueIndex = System.Array.IndexOf(p.enumNames, value); so.ApplyModifiedPropertiesWithoutUndo();
    }
    static void Cockpit()
    {
        var fFF = root.Find("fuselage_F/fuselage_FF");
        var c = Need(fFF, "cockpit");
        Part(c, "cockpit"); SetCol(c, "cockpit_colmesh"); SetLoD(c, "cockpit_colmesh");
        Need(fFF, "nose").SetParent(c, true);
        Part(c.Find("canopy"), "canopy");
        // rear-crew glass outside the hatches (0.4.0 moved the side windows into the hatches, so it can be absent)
        if (L.ContainsKey("canopy_R")) { var canR = New("canopy_R", fFF); Part(canR, "canopy_R"); canR.gameObject.layer = c.Find("canopy").gameObject.layer; }

        // the AB-4 escape capsule goes: the game never fires ejection seats while the cockpit part has an EscapeCapsule
        var oldInt = C(c.Find("cockpit_int"), "Cockpit");
        var engineSources = new SerializedObject(oldInt).FindProperty("engineSources");
        var engines = Enumerable.Range(0, engineSources.arraySize).Select(i => engineSources.GetArrayElementAtIndex(i).objectReferenceValue).ToArray();
        foreach (var n in new[] { "cushion1", "cushion2", "cushion3", "EjectSmoke", "EjectFlame", "EjectFlame", "ejectionForceTransform", "Parachute", "DrogueChute",
                                  "cushionTransform_rear", "cushionTransform_front", "CoM", "doorHinge_L1", "doorHinge_R1", "cockpit_int", "cockpit_int_simple",
                                  "canopy_int", "Pilot", "WSO" })
        {
            var t = c.Cast<Transform>().FirstOrDefault(x => x.name == n && !doomed.Contains(x.gameObject));
            if (t != null) Doom(t); else log.AppendLine("cockpit: no " + n);
        }
        capsule = C(c, "EscapeCapsule");

        var ew = PrefabUtility.LoadPrefabContents(EW1).transform;
        try
        {
            var copies = new List<Transform>();
            // four crew stations: pilot and co-pilot in front, navigator and weapons officer behind, each on an ejection seat
            var ewPilot = FindIn(ew, "pilot");
            var crew = new[] { new { n = "crew_Pilot", seat = "seat_PL", part = c, dir = "Left", pitch = 353.2f },
                               new { n = "crew_CoPilot", seat = "seat_PR", part = c, dir = "Right", pitch = 353.2f },
                               new { n = "crew_Navigator", seat = "seat_NL", part = fFF, dir = "Left", pitch = 356f },
                               new { n = "crew_WSO", seat = "seat_NR", part = fFF, dir = "Right", pitch = 356f } };
            var pilots = new List<Object>();
            foreach (var k in crew)
            {
                var go = (GameObject)Object.Instantiate(ewPilot.gameObject, k.part, false);
                go.name = k.n; go.transform.position = P(k.seat); go.transform.rotation = Quaternion.Euler(k.pitch, 0f, 0f);
                copies.Add(go.transform);
            }
            Repoint(copies, ew);
            var ac = C(root, "Aircraft");
            foreach (var k in crew)
            {
                var pc = C(k.part.Find(k.n), "Pilot");
                Set(pc, "unitPart", C(k.part, "AeroPart")); Set(pc, "aircraft", ac); Set(pc, "ejectionSeat", true);
                SetEnum(pc, "exitDirection", k.dir);
                pilots.Add(pc);
            }
            // PB-22 cockpit interior, rear crew station, yokes, throttle, tac screen and bundled ejection seats
            PB22Cockpit.Build(root, c, fFF, ac, engines, log);

            // crew hatches (hinged on the centre spine, open outward): blown off 250 ms before the first seat fires, opened on their hinges on the ground
            var canopyType = GameType("Canopy");
            var clip = Get(C(FindIn(ew, "door_L"), "Canopy"), "ejectSound");
            var canopies = new List<Object>();
            foreach (var n in new[] { "PL", "PR", "NL", "NR" })
            {
                var owner = n[0] == 'P' ? c : fFF;
                var h1 = New("hatchHinge_" + n + "1", owner); h1.position = P("hatchHinge_" + n + "1"); h1.rotation = R("hatchHinge_" + n + "1");
                var h2 = New("hatchHinge_" + n + "2", h1);
                var ht = New("hatch_" + n, h2); Part(ht, "hatch_" + n); ht.gameObject.layer = owner.gameObject.layer;
                var bc = ht.gameObject.AddComponent<BoxCollider>(); var mb = M["hatch_" + n].bounds;
                bc.center = mb.center; bc.size = mb.size; bc.enabled = false;
                var cp = (Component)ht.gameObject.AddComponent(canopyType);
                Set(cp, "ejectionTransform", ht); Set(cp, "attachedPart", C(owner, "AeroPart")); Set(cp, "mass", 60f);
                Set(cp, "ejectionCollider", bc); Set(cp, "ejectionForce", new Vector3(0f, 20000f, 0f)); Set(cp, "forcePosition", new Vector3(0f, 0f, -0.2f));
                Set(cp, "ejectSound", clip); Set(cp, "fireTime", 0.2f); Set(cp, "openSpeed", 1f);
                Size(cp, "canopyHinges", 1);
                Set(cp, "canopyHinges.Array.data[0].transform", h2);
                Set(cp, "canopyHinges.Array.data[0].hingeAngle", n[1] == 'R' ? 100f : -100f);
                canopies.Add(cp);
            }
            // hatch interior liners (cockpit side): added once the hatch meshes are in place
            PB22Cockpit.Hatches(root, c, fFF, ac, log);
            ObjArray(ac, "pilots", pilots.ToArray());
            ObjArray(ac, "canopies", canopies.ToArray());
            Set(ac, "cockpitViewPoint", FindIn(c.Find("crew_Pilot"), "helmetCamPoint"));
            // livery and damage reach every hull renderer of the two cabin parts
            ObjArray(C(c, "AeroPart"), "damageMaterial.renderers", c.GetComponent<MeshRenderer>(), FindIn(c, "hatch_PL").GetComponent<MeshRenderer>(), FindIn(c, "hatch_PR").GetComponent<MeshRenderer>());
            ObjArray(C(fFF, "AeroPart"), "damageMaterial.renderers", fFF.GetComponent<MeshRenderer>(), FindIn(fFF, "hatch_NL").GetComponent<MeshRenderer>(), FindIn(fFF, "hatch_NR").GetComponent<MeshRenderer>());
            Joints(C(c.Find("nose"), "AeroPart"), C(c, "AeroPart"), 200000f);
            Joints(C(c, "AeroPart"), C(fFF, "AeroPart"), 300000f);
            Set(C(c, "AeroPart"), "armorProperties.pierceArmor", 50f); Set(C(c, "AeroPart"), "armorProperties.blastArmor", 80f);
        }
        finally { PrefabUtility.UnloadPrefabContents(ew.gameObject); }
    }
    static Component capsule;

    // ------------------------------------------------------------------ wings: sweep, flaps + slats on airspeed, spoilers for roll and airbrake
    static void Wings()
    {
        var swing = C(root, "SwingWingController");
        foreach (var s in new[] { "L", "R" })
        {
            float sg = s == "R" ? 1f : -1f;
            var wr = root.Find("wingroot_" + s);
            var ha = wr.Find("wingHinge_" + s + "a"); ha.position = P("wingHinge_" + s + "a");
            var hb = ha.GetChild(0); hb.localPosition = Vector3.zero; hb.localRotation = Quaternion.identity;
            var w1 = wr.Find("wing1_" + s); Part(w1, "wing1_" + s); SetLoD(w1, "wing1_" + s + "_colmesh");
            // the wing hull rides a child nudged 0.25 m outboard so its root clears the gear bay at full sweep
            var w1Mc = w1.GetComponent<MeshCollider>(); if (w1Mc != null) Object.DestroyImmediate(w1Mc);
            var w1Col = w1.Find("wing1_" + s + "_col"); if (w1Col == null) w1Col = New("wing1_" + s + "_col", w1);
            w1Col.localRotation = Quaternion.identity; w1Col.position = w1.position + new Vector3(0.25f * sg, 0f, 0f);
            SetCol(w1Col, "wing1_" + s + "_colmesh");
            w1.Find("wing1_" + s + "_liftNormal").localPosition = Vector3.zero;
            w1.Find("wing1_" + s + "_anchor").position = P("wingHinge_" + s + "a");

            // glove pylon lives on the fixed glove, so it no longer counter-rotates with the sweep
            var ph = w1.Find("pylon_" + s + "_hinge"); ph.SetParent(wr, true);
            ph.position = P("glovePylon_" + s);
            var wp = ph.GetChild(0); wp.localPosition = Vector3.zero; wp.rotation = Quaternion.identity;
            SetMesh(wp, "glovePylon_" + s);
            wp.GetChild(0).position = P("pylonMount_glove_" + s);

            var w2 = w1.Find("wing2_" + s);
            var tipOld = w2.Find("wingtip_" + s);
            // the AB-4's outer panel and tip carry on as our outer panel (wing2) and tip, so the wing breaks up in three stages
            Part(w2, "wing2_" + s); SetCol(w2, "wing2_" + s + "_colmesh"); SetLoD(w2, "wing2_" + s + "_colmesh");
            var tip = tipOld; Part(tip, "wingtip_" + s); SetCol(tip, "wingtip_" + s + "_colmesh"); SetLoD(tip, "wingtip_" + s + "_colmesh");
            // our own lens on the tip pod (the housing is part of the wing mesh); the game swaps it to its lit material
            var nav = tipOld.Find("navlight_" + s); nav.SetParent(tip, false); Part(nav, "navlight_" + s);
            nav.GetComponent<MeshRenderer>().sharedMaterial = AssetDatabase.LoadAssetAtPath<Material>(PH_MAT + (s == "L" ? "light_red_off" : "light_green_off") + "_PLACEHOLDER.mat");
            nav.GetChild(0).localPosition = new Vector3(0.05f * sg, 0f, 0.12f);
            var vort = tipOld.Find("wingtipvortex_" + s); vort.SetParent(tip, false); vort.localPosition = new Vector3(0f, 0f, -0.4f);
            Set(C(root, "NavLights"), "navLights.Array.data[" + (s == "L" ? 1 : 2) + "].part", C(tip, "AeroPart"));
            var tipCS = C(tipOld, "ControlSurface");
            var splitSound = Get(tipCS, "splitSound");
            // the tip's airbrake goes (our speed brake is the spoiler split)
            Doom(tip.Find("airbrake_" + s + "_mount")); doomed.Add(tipCS); doomedComps.Add(tipCS);
            Size(C(tip, "AeroPart"), "damageMaterial.renderers", 1);
            Set(C(tip, "AeroPart"), "damageMaterial.renderers.Array.data[0]", tip.GetComponent<MeshRenderer>());
            Size(C(w2, "AeroPart"), "damageMaterial.renderers", 1);
            Set(C(w2, "AeroPart"), "damageMaterial.renderers.Array.data[0]", w2.GetComponent<MeshRenderer>());

            // spoiler: reuse the AB-4 aileron part (AeroPart + ControlSurface), rebuilt hinge chain
            var sp = w2.Find("aileron_" + s); sp.SetParent(w1, true); sp.name = "spoiler_" + s;
            foreach (Transform ch in sp.Cast<Transform>().ToArray()) Object.DestroyImmediate(ch.gameObject);
            sp.position = P("spoiler_" + s); sp.rotation = Quaternion.identity;
            var h1 = New("spoilerHinge_" + s + "1", sp); h1.position = P("spoilerHinge_" + s + "1"); h1.rotation = R("spoilerHinge_" + s + "1");
            var h2 = New("spoilerHinge_" + s + "2", h1);
            // the visible panel rides the split (which only opens upward); the roll deflection turns h2 and the lift normal
            // under it, both ways, so roll still works but the panel never sinks into the wing
            var su = New("spoilerSplit_" + s, h1);
            var sl = New("spoilerSplitLower_" + s, h1);
            var ln = New("spoiler_" + s + "_liftNormal", h2);
            var vis = New("spoiler_" + s + "_visible", su); Part(vis, "spoiler_" + s + "_visible"); SetLoD(vis, "spoiler_" + s + "_visible_colmesh");
            // no hull on the spoiler: it slides under the fixed glove at full sweep and the two are not jointed
            var spMc = sp.GetComponent<Collider>(); if (spMc != null) Object.DestroyImmediate(spMc);
            var cs = C(sp, "ControlSurface");
            Set(cs, "pitchRange", 0f); Set(cs, "rollRange", 15f * sg); Set(cs, "yawRange", 0f);
            Set(cs, "visibleMesh", h2.gameObject); Set(cs, "servoSpeed", 60f);
            Set(cs, "splitUpper", su); Set(cs, "splitLower", sl); Set(cs, "maxSplit", 45f); Set(cs, "splitDrag", 0.08f);   // speed brake (opens at idle throttle; the AI idles to slow down on final)
            Set(cs, "yawSplitFactor", 0f); Set(cs, "splitSound", splitSound); Set(cs, "splitVolumeMultiplier", 1.23f);
            Set(cs, "splitPitchMin", 0.5f); Set(cs, "splitPitchMax", 1.2f);
            Set(C(sp, "AeroPart"), "liftNormal", ln);
            // the AB-4 aileron renderer is gone; a null entry here throws in UnitPart.SetLivery and stops the livery load
            Size(C(sp, "AeroPart"), "damageMaterial.renderers", 1);
            Set(C(sp, "AeroPart"), "damageMaterial.renderers.Array.data[0]", vis.GetComponent<MeshRenderer>());
            Joints(C(sp, "AeroPart"), C(w1, "AeroPart"), 100000f);

            // flap
            var fl = w1.Find("flap_" + s); fl.position = P("flap_" + s); fl.rotation = Quaternion.identity;
            var f1 = fl.Find("flapHinge_" + s + "1"); f1.position = P("flapHinge_" + s + "1"); f1.rotation = R("flapHinge_" + s + "1");
            var f2 = f1.GetChild(0); f2.localPosition = Vector3.zero; f2.localRotation = Quaternion.identity;
            var fv = f2.GetChild(0); fv.name = "flap_" + s + "_visible"; Part(fv, "flap_" + s + "_visible");
            foreach (var l in fl.GetComponentsInChildren<Transform>(true).Where(x => x.name == "LoD").ToArray()) Object.DestroyImmediate(l.gameObject);
            SetLoD(fv, "flap_" + s + "_visible_colmesh");
            // no hull on the flap: it slides under the fixed glove at full sweep and the two are not jointed
            foreach (var fc in fl.GetComponents<Collider>()) Object.DestroyImmediate(fc);

            // slat (visual only, driven by the flap's HighLiftDevice)
            var sla = New("slat_" + s, w1); sla.position = P("slat_" + s);
            var s1 = New("slatHinge_" + s + "1", sla); s1.position = P("slatHinge_" + s + "1"); s1.rotation = R("slatHinge_" + s + "1");
            var s2 = New("slatHinge_" + s + "2", s1);
            var sv = New("slat_" + s + "_visible", s2); Part(sv, "slat_" + s + "_visible"); SetLoD(sv, "slat_" + s + "_visible_colmesh");
            // outer slat section rides the outer panel on its own hinge (same axis and deflection)
            var slb = New("slat2_" + s, w2); slb.position = P("slat2_" + s);
            var t1 = New("slat2Hinge_" + s + "1", slb); t1.position = P("slat2Hinge_" + s + "1"); t1.rotation = R("slat2Hinge_" + s + "1");
            var t2 = New("slat2Hinge_" + s + "2", t1);
            var sv2 = New("slat2_" + s + "_visible", t2); Part(sv2, "slat2_" + s + "_visible"); SetLoD(sv2, "slat2_" + s + "_visible_colmesh");

            var hld = C(fl, "HighLiftDevice");
            // flaps stay fully down through the takeoff run (the engines scrape past 6.4 deg pitch, so the jet must fly by about 5 deg):
            // fully deployed to 504 km/h, in by 630 km/h
            Set(hld, "speedDeployed", 140f); Set(hld, "speedRetracted", 175f); Set(hld, "deployedArea", 120f);
            Size(hld, "movingParts", 4);
            Set(hld, "movingParts.Array.data[1].transform", f2);
            Set(hld, "movingParts.Array.data[1].anglesDeployed", new Vector3(-25f, 0f, 0f));
            Set(hld, "movingParts.Array.data[2].move", false);
            Set(hld, "movingParts.Array.data[2].rotate", true);
            Set(hld, "movingParts.Array.data[2].transform", s2);
            Set(hld, "movingParts.Array.data[2].positionRetracted", Vector3.zero);
            Set(hld, "movingParts.Array.data[2].positionDeployed", Vector3.zero);
            Set(hld, "movingParts.Array.data[2].anglesRetracted", Vector3.zero);
            Set(hld, "movingParts.Array.data[2].anglesDeployed", new Vector3(20f, 0f, 0f));
            Set(hld, "movingParts.Array.data[3].move", false);
            Set(hld, "movingParts.Array.data[3].rotate", true);
            Set(hld, "movingParts.Array.data[3].transform", t2);
            Set(hld, "movingParts.Array.data[3].positionRetracted", Vector3.zero);
            Set(hld, "movingParts.Array.data[3].positionDeployed", Vector3.zero);
            Set(hld, "movingParts.Array.data[3].anglesRetracted", Vector3.zero);
            Set(hld, "movingParts.Array.data[3].anglesDeployed", new Vector3(20f, 0f, 0f));

            int i = s == "L" ? 0 : 1;
            string rp = "rotators.Array.data[" + i + "].";
            Size(swing, rp + "counterRotators", 0);
            Size(swing, rp + "sweepAeroProperties", 3);
            Set(swing, rp + "sweepAeroProperties.Array.data[0].part", C(w1, "AeroPart"));
            Set(swing, rp + "sweepAeroProperties.Array.data[0].swingAreaChange", -47f);
            Set(swing, rp + "sweepAeroProperties.Array.data[0].swingDragChange", -0.6f);
            Set(swing, rp + "sweepAeroProperties.Array.data[1].part", C(wr, "AeroPart"));
            Set(swing, rp + "sweepAeroProperties.Array.data[1].swingAreaChange", -18f);
            Set(swing, rp + "sweepAeroProperties.Array.data[1].swingDragChange", 0f);
            Set(swing, rp + "sweepAeroProperties.Array.data[2].part", C(w2, "AeroPart"));
            Set(swing, rp + "sweepAeroProperties.Array.data[2].swingAreaChange", -13f);
            Set(swing, rp + "sweepAeroProperties.Array.data[2].swingDragChange", -0.2f);
            Set(swing, rp + "maxAngle", 45f);
            Set(swing, rp + "rotationSpeed", 6f);
        }
        Set(swing, "forwardMach", 0.5f);
        Set(swing, "sweptMach", 0.95f);
        Set(swing, "displayAngleMin", 20f);
        Set(swing, "displayAngleMax", 65f);
    }

    // ------------------------------------------------------------------ tailerons and fin
    static void Tail()
    {
        var fR = root.Find("fuselage_R");
        var tail = fR.Find("tail");
        foreach (var s in new[] { "L", "R" })
        {
            float sg = s == "R" ? 1f : -1f;
            var el = Need(root, "elevator_" + s); el.SetParent(fR, true);
            el.position = P("elevator_" + s); el.rotation = Quaternion.identity;
            var e1 = el.Find("elevatorHinge_" + s + "1"); e1.position = P("elevatorHinge_" + s + "1"); e1.rotation = R("elevatorHinge_" + s + "1");
            var e2 = e1.GetChild(0); e2.localPosition = Vector3.zero; e2.localRotation = Quaternion.identity;
            var ev = e2.GetChild(0); Part(ev, "elevator_" + s + "_visible"); SetLoD(ev, "elevator_" + s + "_visible_colmesh");
            SetCol(el, "elevator_" + s + "_visible_colmesh");
            var cs = C(el, "ControlSurface");
            Set(cs, "pitchRange", -20f); Set(cs, "rollRange", 8f * sg); Set(cs, "yawRange", 0f);
            var ap = C(el, "AeroPart");
            Joints(ap, C(fR, "AeroPart"), 300000f, C(tail, "AeroPart"), 300000f,
                C(Need(root, "engines_" + s), "AeroPart"), 200000f, C(Need(root, "nozzles_" + s), "AeroPart"), 200000f);
        }
        var rud = Need(root, "rudder_L"); rud.SetParent(tail, true);
        Part(rud, "rudder_L"); SetCol(rud, "rudder_L_colmesh"); SetLoD(rud, "rudder_L_colmesh");
        var r1 = rud.Find("rudder_L_hinge1"); r1.position = P("rudderHinge_L1"); r1.rotation = R("rudderHinge_L1");
        var r2 = r1.GetChild(0); r2.localPosition = Vector3.zero; r2.localRotation = Quaternion.identity;
        var rv = r2.GetChild(0); Part(rv, "rudder_L_visible"); SetLoD(rv, "rudder_L_visible_colmesh");
        var rln = rv.Find("rudder_L_liftNormal"); rln.localPosition = Vector3.zero; rln.rotation = Quaternion.Euler(0f, 0f, 270f);
        var rcs = C(rud, "ControlSurface");
        Set(rcs, "yawRange", -15f);
        var rap = C(rud, "AeroPart");
        Joints(rap, C(tail, "AeroPart"), 300000f, C(fR, "AeroPart"), 300000f, C(root, "AeroPart"), 200000f);
        Doom(Need(root, "rudderFoldHinge_La"));
    }

    // ------------------------------------------------------------------ engines (buried in the rear fuselage) and nozzles
    static void Engines()
    {
        var fR = root.Find("fuselage_R");
        foreach (var s in new[] { "L", "R" })
        {
            string n = s == "L" ? "1" : "3";
            var en = Need(root, "engines_" + s); en.SetParent(fR, true);
            en.position = P("engines_" + s); en.rotation = Quaternion.identity;
            NoMesh(en); SetCol(en, "engines_" + s + "_colmesh"); SetLoD(en, "engines_" + s + "_colmesh");
            // the engine body (casing, accessories, stators) and the fan face the plugin spins with the engine RPM; both hang
            // off the engine part so they leave with it when it breaks away
            foreach (var em in new[] { "engine_body_" + s, "fan_" + s })
                if (L.ContainsKey(em)) Part(Find(en, em) ?? New(em, en), em);
            var eng = en.Find("engine" + n); eng.position = P("engine" + n);
            var cap = eng.GetComponent<CapsuleCollider>(); cap.center = Vector3.zero; cap.radius = 0.5f; cap.height = 5f; cap.direction = 2;
            var ap = C(en, "AeroPart");
            Joints(ap, C(fR, "AeroPart"), 600000f, C(root, "AeroPart"), 600000f, C(fR.Find("tail"), "AeroPart"), 200000f);

            var nz = en.Find("nozzles_" + s); nz.position = P("nozzles_" + s); nz.rotation = Quaternion.identity;
            SetMesh(nz, "nozzle" + n); SetCol(nz, "nozzle" + n + "_colmesh"); SetLoD(nz, "nozzle" + n + "_colmesh");
            NozzleMetal(nz);
            var nap = C(nz, "AeroPart");
            Joints(nap, C(en, "AeroPart"), 300000f, C(fR, "AeroPart"), 300000f, C(fR.Find("tail"), "AeroPart"), 200000f);
            var jn = nz.Find("nozzle" + n);
            jn.position = P("thrustTransform" + n); jn.rotation = Quaternion.identity;
            var glow = jn.Find("afterburner" + n + "_nozzle_glow");
            // size = mesh x glow scale x flame scale (the JetNozzle only drives brightness). Nozzle exit is 0.97 m across: the glow
            // (mesh 0.92 x 0.42) comes to 0.90 x 0.88 m, the flame (mesh 1.36 x 0.50 x 3.6, widest at its start) to 0.78 m wide, 19.4 m long
            glow.localPosition = new Vector3(0f, 0f, 0.1f); glow.localRotation = Quaternion.identity; glow.localScale = new Vector3(0.98f, 2.1f, 1f);
            var flame = glow.GetChild(0);
            flame.localPosition = new Vector3(0f, 0f, 0.09f); flame.localRotation = Quaternion.identity; flame.localScale = new Vector3(0.46f, 0.58f, 7.0f);
        }
    }

    // ------------------------------------------------------------------ main gear: six-wheel bogie swinging outboard into the glove fairing
    static void MainGear(string s, float sg)
    {
        var gb = root.Find("gearbay_" + s);
        var mount = gb.Find("gearMount_" + s);
        mount.position = P("gearHinge_" + s); mount.rotation = Quaternion.Euler(0f, 90f, 0f);
        var hinge = mount.GetChild(0); hinge.localPosition = Vector3.zero; hinge.localRotation = Quaternion.identity;
        var g = hinge.Find("gear_" + s); g.localPosition = Vector3.zero; g.rotation = Quaternion.identity;
        SetMesh(g, "gear_" + s); FitBox(g, M["gear_" + s]);

        float r = Radius("wheel_" + s + "Fo"), travel = 0.8f;
        Vector3 axle = P("gear_unsprung_" + s);
        var bump = g.Find("bumpstop"); bump.position = axle + Vector3.up * (travel - r); bump.rotation = Quaternion.identity;
        var un = g.Find("gear_unsprung_" + s); un.position = axle; un.rotation = Quaternion.identity; SetMesh(un, "gear_unsprung_" + s);
        var bog = un.Find("bogey"); Part(bog, "bogey_" + s);
        var wF = bog.Find("wheel_" + s + "F"); wF.name = "wheel_" + s + "Fo"; Part(wF, "wheel_" + s + "Fo");
        var wR = bog.Find("wheel_" + s + "R"); wR.name = "wheel_" + s + "Ro"; Part(wR, "wheel_" + s + "Ro");
        var wheels = new List<Transform> { wF };
        foreach (var w in new[] { "Fi", "Mi", "Mo", "Ri" })
        {
            var t = New("wheel_" + s + w, bog); Part(t, "wheel_" + s + w); wheels.Add(t);
        }
        wheels.Add(wR);
        var ch = bog.Find("chocks"); ch.position = new Vector3(axle.x, axle.y - r + 0.01f, axle.z);

        var fl = gb.Find("flareEjector_" + s);
        var gbe = Lget("gearbay_" + s);
        fl.position = P("gearbay_" + s) + new Vector3(0f, -0.3f, gbe.bmin[1] + 0.4f);

        // bi-fold main door on the outboard edge of the bay: AB-4 outer door (LL/RR) -> outer panel, AB-4 inner door (L/R) -> inner
        // panel, re-hung on the outer panel's free edge
        var o1 = gb.Find("gearDoorHinge_" + s + s + "1"); o1.name = "gearDoorHinge_" + s + "O1";
        o1.position = P("gearDoorHinge_" + s + "O1"); o1.rotation = Quaternion.identity;
        var o2 = o1.GetChild(0); o2.name = "gearDoorHinge_" + s + "O2"; o2.localPosition = Vector3.zero; o2.localRotation = Quaternion.identity;
        var od = o2.GetChild(0); od.name = "gearDoor_" + s + "O"; Part(od, "gearDoor_" + s + "O");
        var i1 = gb.Find("gearDoorHinge_" + s + "1"); i1.SetParent(od, true); i1.name = "gearDoorHinge_" + s + "I1";
        i1.position = P("gearDoorHinge_" + s + "I1"); i1.rotation = Quaternion.identity;
        var i2 = i1.GetChild(0); i2.name = "gearDoorHinge_" + s + "I2"; i2.localPosition = Vector3.zero; i2.localRotation = Quaternion.identity;
        var id = i2.GetChild(0); id.name = "gearDoor_" + s + "I"; Part(id, "gearDoor_" + s + "I");

        // leg door rides the leg; retraction actuator (cylinder on the fairing, rod on the leg, each aims at the other end);
        // side brace (upper link turns with the fold, lower link on the leg aims at the knee)
        var ld = New("legDoor_" + s, g); Part(ld, "legDoor_" + s);
        var acyl = New("actCyl_" + s, gb); Part(acyl, "actCyl_" + s);
        var arod = New("actRod_" + s, g); Part(arod, "actRod_" + s);
        var tRod = New("actTgtRod_" + s, g); tRod.position = P("actTgtRod_" + s);
        var tAnc = New("actTgtAnchor_" + s, gb); tAnc.position = P("actTgtAnchor_" + s);
        var bu = New("braceU_" + s, gb); Part(bu, "braceU_" + s);
        var knee = New("braceKnee_" + s, bu); knee.position = P("braceKnee_" + s);
        var bl = New("braceL_" + s, g); Part(bl, "braceL_" + s);
        bl.LookAt(knee); acyl.LookAt(tRod); arod.LookAt(tAnc);

        var lg = C(g, "LandingGear");
        Set(lg, "suspensionTravel", travel); Set(lg, "wheelRadius", r);
        Set(lg, "springRate", 4000000f); Set(lg, "dampingRate", 300000f); Set(lg, "maxCompression", 0.65f); Set(lg, "contactArea", 0.1f);
        Set(lg, "mass", 900f);
        Set(lg, "foldDegrees", -90f * sg); Set(lg, "hingeFoldMotion", Vector3.zero); Set(lg, "foldSpeed", 25f);
        Set(lg, "axle", bog);
        ObjArray(lg, "wheels", wheels.ToArray());
        Size(lg, "gearDoors", 2);
        Set(lg, "gearDoors.Array.data[0].transform", o2);
        Set(lg, "gearDoors.Array.data[0].closedAngle", Vector3.zero);
        Set(lg, "gearDoors.Array.data[0].openAngle", new Vector3(0f, 0f, 90f * sg));
        Set(lg, "gearDoors.Array.data[1].transform", i2);
        Set(lg, "gearDoors.Array.data[1].closedAngle", Vector3.zero);
        Set(lg, "gearDoors.Array.data[1].openAngle", new Vector3(0f, 0f, -180f * sg));
        Size(lg, "movingParts", 4);
        Set(lg, "movingParts.Array.data[0].transform", bu);
        Set(lg, "movingParts.Array.data[0].target", null);
        Set(lg, "movingParts.Array.data[0].foldAngles", new Vector3(0f, 0f, -48.9f * sg));
        Set(lg, "movingParts.Array.data[1].transform", bl);
        Set(lg, "movingParts.Array.data[1].target", knee);
        Set(lg, "movingParts.Array.data[1].foldAngles", Vector3.zero);
        Set(lg, "movingParts.Array.data[2].transform", acyl);
        Set(lg, "movingParts.Array.data[2].target", tRod);
        Set(lg, "movingParts.Array.data[2].foldAngles", Vector3.zero);
        Set(lg, "movingParts.Array.data[3].transform", arod);
        Set(lg, "movingParts.Array.data[3].target", tAnc);
        Set(lg, "movingParts.Array.data[3].foldAngles", Vector3.zero);
    }

    // ------------------------------------------------------------------ nose gear: raked strut, twin wheels, steering about the strut axis
    static void NoseGear()
    {
        var gh = root.Find("gearhinge_F"); gh.position = P("gearhinge_F"); gh.rotation = Quaternion.identity;
        var g = gh.Find("gear_F"); g.position = P("gear_F"); g.rotation = R("gear_unsprung_F");
        NoMesh(g);
        var strut = New("gear_F_strut", g); Part(strut, "gear_F");
        var box = g.GetComponent<BoxCollider>();
        if (box != null) { box.center = g.InverseTransformPoint(strut.TransformPoint(M["gear_F"].bounds.center)); box.size = M["gear_F"].bounds.size; }

        float r = Radius("wheel_FL"), travel = 0.6f;
        Vector3 axle = P("gear_unsprung_F");
        var un = g.Find("gear_unsprung_F"); un.position = axle; un.localRotation = Quaternion.identity; SetMesh(un, "gear_unsprung_F");
        var bump = g.Find("bumpstop"); bump.localRotation = Quaternion.identity; bump.position = axle + g.up * (travel - r);
        var wl = un.Find("wheel_F"); wl.name = "wheel_FL"; Part(wl, "wheel_FL");
        var wr = New("wheel_FR", un); Part(wr, "wheel_FR");
        var ch = un.Find("chocks"); ch.position = new Vector3(0f, axle.y - r + 0.01f, axle.z); ch.rotation = Quaternion.identity;
        var light = g.Find("gearlight_F"); light.position = P("gear_F") + new Vector3(0f, -0.55f, 0.35f);
        Doom(g.Find("arm")); Doom(root.Find("gear_F_armtarget"));
        // nose-wheel steering: the stability assist steers the nose wheel to hold the yaw rate at zero; with the AB-4's 45 deg lock
        // on this much heavier airframe that loop overshoots and the rudder and nose wheel wag harder with speed. 20 deg halves
        // the loop gain and still gives about a 28 m taxi turn radius.
        Set(C(g, "LandingGear"), "steeringLock", 45f);

        var fF = root.Find("fuselage_F");
        Transform[] d2 = new Transform[2];
        int k = 0;
        foreach (var s in new[] { "FL", "FR" })
        {
            var h1 = fF.Find("gearDoorHinge_" + s + "1"); h1.position = P("gearDoorHinge_" + s + "1"); h1.rotation = Quaternion.identity;
            var h2 = h1.GetChild(0); h2.localPosition = Vector3.zero; h2.localRotation = Quaternion.identity;
            Part(h2.GetChild(0), "gearDoor_" + s);
            d2[k++] = h2;
        }

        var lg = C(g, "LandingGear");
        Set(lg, "suspensionTravel", travel); Set(lg, "wheelRadius", r);
        Set(lg, "springRate", 1200000f); Set(lg, "dampingRate", 150000f); Set(lg, "maxCompression", 0.45f); Set(lg, "contactArea", 0.07f); Set(lg, "aligningStrength", 5f);
        Set(lg, "mass", 300f);
        Set(lg, "foldDegrees", 95f); Set(lg, "hingeFoldMotion", Vector3.zero);
        Set(lg, "axle", un);
        ObjArray(lg, "wheels", wl, wr);
        Size(lg, "gearDoors", 2);
        Set(lg, "gearDoors.Array.data[0].transform", d2[0]);
        Set(lg, "gearDoors.Array.data[0].closedAngle", Vector3.zero);
        Set(lg, "gearDoors.Array.data[0].openAngle", new Vector3(0f, 0f, -90f));
        Set(lg, "gearDoors.Array.data[1].transform", d2[1]);
        Set(lg, "gearDoors.Array.data[1].closedAngle", Vector3.zero);
        Set(lg, "gearDoors.Array.data[1].openAngle", new Vector3(0f, 0f, 90f));
        Size(lg, "movingParts", 0);
    }

    // ------------------------------------------------------------------ weapon bays
    static void Bays()
    {
        Need(root, "weaponBay_forward").position = P("weaponBay_forward");
        Need(root, "weaponBay_combined").position = P("weaponBay_combined");
        Need(root, "weaponBay_rear").position = P("weaponBay_rear");
        foreach (var d in new[] { "FL", "FR", "RL", "RR" })
        {
            var h1 = root.Find("bayDoorHinge_" + d + "1");
            h1.position = P("bayDoorHinge_" + d + "1"); h1.rotation = Quaternion.identity;
            var h2 = h1.GetChild(0); h2.localPosition = Vector3.zero; h2.localRotation = Quaternion.identity;
            Part(h2.GetChild(0), "bayDoor_" + d);
        }
        var wm = C(Need(root, "cockpit"), "WeaponManager");
        Set(wm, "hardpointSets.Array.data[1].hardpoints.Array.data[0].part", C(root, "AeroPart"));
    }

    // ------------------------------------------------------------------ pylons: two sets so the stock loadouts can load them differently
    // [3] Inner Pylons = new mid pair under the intakes, [4] Outer Pylons = glove pair (the AB-4 wing pylons)
    static void Pylons()
    {
        var wm = C(Need(root, "cockpit"), "WeaponManager");
        var so = new SerializedObject(wm);
        var sets = so.FindProperty("hardpointSets");
        sets.DeleteArrayElementAtIndex(4);          // AB-4 heater bays
        sets.InsertArrayElementAtIndex(3);          // duplicate the wing pylon set
        so.ApplyModifiedPropertiesWithoutUndo();
        Set(wm, "hardpointSets.Array.data[3].name", "Inner Pylons");
        Set(wm, "hardpointSets.Array.data[4].name", "Outer Pylons");
        int k = 0;
        foreach (var s in new[] { "L", "R" })
        {
            var it = root.Find("intake_" + s);
            var py = New("midPylon_" + s, it); Part(py, "midPylon_" + s);
            var mount = New("pylonMount_mid_" + s, py); mount.position = P("pylonMount_mid_" + s);
            string hp = "hardpointSets.Array.data[3].hardpoints.Array.data[" + k + "].";
            Set(wm, hp + "transform", mount);
            Set(wm, hp + "part", C(it, "AeroPart"));
            Set(wm, hp + "pylonOptions.Array.data[0].renderer", py.GetComponent<MeshRenderer>());
            Set(wm, hp + "Pylon", py.GetComponent<MeshRenderer>());
            Set(wm, hp + "HardpointIndex", 3);
            // glove pylons hang off the fixed glove now
            string ho = "hardpointSets.Array.data[4].hardpoints.Array.data[" + k + "].";
            Set(wm, ho + "part", C(root.Find("wingroot_" + s), "AeroPart"));
            Set(wm, ho + "HardpointIndex", 4);
            k++;
        }
    }

    // ------------------------------------------------------------------ weapon options and the stock (AI) loadouts from PB22TridentFlightModel/PB22_NPC_Loadouts.md
    // sets: 0 forward bay, 1 rear bay, 2 combined bays, 3 inner pylons, 4 outer pylons
    static readonly string[] PylonOptions = { "JammingPod1", "ARM1_double", "BallisticMissile1_single", "BallisticMissile1_tacNuke_single",
        "PB22_AShM1_tandem", "PB22_AShM3_double", "PB22_AShM2_triple", "PB22_bomb_500_triple" };
    static readonly object[][] Stock = {
        //            name                          fuel   forward bay                    rear bay                       combined bays                    inner pylons                         outer pylons
        new object[] { "Trident-X 'Broadside'",     0.6f, "AShM2_internalx6",            "AShM2_internalx6",            null,                            "PB22_AShM3_double",                 "PB22_bomb_500_triple" },
        new object[] { "Trident-M 'Sea Lance'",     0.6f, "AShM1_internalx4_stack",      "AShM1_internalx4_stack",      null,                            "PB22_AShM1_tandem",                           "PB22_AShM1_tandem" },
        new object[] { "Trident-P 'Needle'",        0.6f, "AShM3_internalx4_stack",      "AShM3_internalx4_stack",      null,                            "PB22_AShM3_double",                 "PB22_AShM3_double" },
        new object[] { "Trident-C 'Carpet'",        0.5f, null,                          null,                          "bomb_250_rotaryx30",            "PB22_bomb_500_triple",              "PB22_bomb_500_triple" },
        new object[] { "Trident-N 'Doomsday'",      0.5f, null,                          null,                          "CruiseMissile20kt_internalx2",  "BallisticMissile1_tacNuke_single",  "BallisticMissile1_single" },
        new object[] { "Trident-W 'Wild Weasel'",   0.6f, "AShM3_internalx4_stack",      "AShM3_internalx4_stack",      null,                            "ARM1_double",                       "ARM1_double" },
        // added in 0.9.1
        new object[] { "Trident-J 'Static'",        0.6f, "AShM3_internalx4_stack",      "AShM3_internalx4_stack",      null,                            "PB22_bomb_500_triple",              "JammingPod1" },
        new object[] { "Trident-G 'Gauntlet'",      0.6f, "bomb_500_rotaryx6",           "bomb_500_rotaryx6",           null,                            "ARM1_double",                       "AAM2_double" },
    };
    static Object Mnt(object n) { return n == null ? null : PB22Mounts.Mount((string)n); }
    static void Loadouts()
    {
        var wm = C(Need(root, "cockpit"), "WeaponManager");
        // combined bays: no internal Piledriver; add the ALND-4 pair
        ObjArray(wm, "hardpointSets.Array.data[2].weaponOptions", null, Mnt("bomb_demolition_internal"), Mnt("bomb_250_rotaryx30"),
                 Mnt("bomb_250_glide_rotaryx30"), Mnt("CruiseMissile20kt_internalx2"));
        // AGM-99 x6 (stock Darkreach bay rack, 2 wide x 3 high) in the forward and the rear bay
        ObjAppend(wm, "hardpointSets.Array.data[0].weaponOptions", Mnt("AShM2_internalx6"));
        ObjAppend(wm, "hardpointSets.Array.data[1].weaponOptions", Mnt("AShM2_internalx6"));
        // no Scythe (AAM2x8) or Scimitar (AAM4x8) racks in the forward and rear bays
        for (int s = 0; s < 2; s++)
        {
            var wso = new SerializedObject(wm);
            var o = wso.FindProperty("hardpointSets.Array.data[" + s + "].weaponOptions");
            for (int i = o.arraySize - 1; i >= 0; i--)
            {
                var r = o.GetArrayElementAtIndex(i).objectReferenceValue;
                if (r != null && (r.name == "AAM2x8" || r.name == "AAM4x8")) { o.GetArrayElementAtIndex(i).objectReferenceValue = null; o.DeleteArrayElementAtIndex(i); }
            }
            wso.ApplyModifiedPropertiesWithoutUndo();
        }
        var opts = new List<Object> { null }; opts.AddRange(PylonOptions.Select(n => Mnt(n)));
        ObjArray(wm, "hardpointSets.Array.data[3].weaponOptions", opts.ToArray());
        // outer (glove) pylons also take the stock side-by-side Scythe pair; inner pylons never do (balancing)
        var outer = new List<Object>(opts) { Mnt("AAM2_double") };
        ObjArray(wm, "hardpointSets.Array.data[4].weaponOptions", outer.ToArray());

        var par = AssetDatabase.LoadMainAssetAtPath(MOD + "PB22Trident_Parameters.asset");
        var so = new SerializedObject(par);
        var st = so.FindProperty("StandardLoadouts");
        st.arraySize = Stock.Length;
        for (int i = 0; i < Stock.Length; i++)
        {
            var e = st.GetArrayElementAtIndex(i);
            e.FindPropertyRelative("disabled").boolValue = false;
            e.FindPropertyRelative("Name").stringValue = (string)Stock[i][0];
            e.FindPropertyRelative("FuelRatio").floatValue = (float)Stock[i][1];
            var w = e.FindPropertyRelative("loadout.weapons"); w.arraySize = 5;
            for (int j = 0; j < 5; j++) w.GetArrayElementAtIndex(j).objectReferenceValue = Mnt(Stock[i][2 + j]);
        }
        // loadouts[0] = editor default, loadouts[1] = what a freshly spawned PB-22 carries
        var lo = so.FindProperty("loadouts"); lo.arraySize = 2;
        int[] pick = { 1, 0 };
        for (int i = 0; i < 2; i++)
        {
            var w = lo.GetArrayElementAtIndex(i).FindPropertyRelative("weapons"); w.arraySize = 5;
            for (int j = 0; j < 5; j++) w.GetArrayElementAtIndex(j).objectReferenceValue = Mnt(Stock[pick[i]][2 + j]);
        }
        so.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(par);
        AssetDatabase.SaveAssets();
        foreach (var n in PylonOptions) if (Mnt(n) == null) log.AppendLine("MISSING MOUNT " + n);
        foreach (var row in Stock) for (int j = 2; j < 7; j++) if (row[j] != null && Mnt(row[j]) == null) log.AppendLine("MISSING MOUNT " + row[j]);
        log.AppendLine("loadouts: " + Stock.Length + " stock, 5 sets");
    }

    // ------------------------------------------------------------------ misc placements
    static void Misc()
    {
        root.Find("CoM").position = P("CoM");
        root.Find("vaporCone").position = BtoU(new[] { 0f, 17f - 16f, 2.5f });
        var lad = root.Find("ladder"); lad.position = new Vector3(-2.78f, -2.85f, 17f - 7.5f);
    }

    // ------------------------------------------------------------------ markings: painted into each livery's skin texture, as the
    // stock aircraft do (LiveryData swaps _Livery). The separate decal meshes of 0.4.0 - 0.4.2 are removed from the prefab.
    static void Decals()
    {
        int n = 0;
        foreach (var t in root.GetComponentsInChildren<Transform>(true).Where(t => t != null && t.name.StartsWith("decal_")).ToList())
        {
            if (t == null) continue;
            Object.DestroyImmediate(t.gameObject); n++;
        }
        foreach (var liv in new[] { "grey", "maritime", "lowlevel" })
            if (AssetDatabase.LoadAssetAtPath<Material>(ART + "PB22_decal_" + liv + ".mat") != null) AssetDatabase.DeleteAsset(ART + "PB22_decal_" + liv + ".mat");
        log.AppendLine("decal objects removed: " + n);
    }

    // ------------------------------------------------------------------ durability (0.4.1): armour / tolerance, joints, fuel fire, engine damage
    // Pitched between the Medusa and the Darkreach (stock values in tu22/internals/armor_all_stock.tsv). A hit does
    // (pierce - armour) / tolerance to a 100 HP part, so tolerance is the HP multiplier: the core takes ~29 hits of a 60-pierce round
    // (Medusa 17, Darkreach 67), the crew section is armoured like the stock crew tubs, and the moving surfaces stay fragile so
    // damage shows (pieces come off) long before a kill.
    static void Arm(string path, float pa, float pt, float ba, float bt)
    {
        var t = path == "" ? root : Find(root, path);
        if (t == null) { log.AppendLine("ARMOR: no part " + path); return; }
        var ap = C(t, "AeroPart");
        Set(ap, "armorProperties.pierceArmor", pa); Set(ap, "armorProperties.pierceTolerance", pt);
        Set(ap, "armorProperties.blastArmor", ba); Set(ap, "armorProperties.blastTolerance", bt);
        Set(ap, "armorProperties.fireArmor", 0f); Set(ap, "armorProperties.fireTolerance", 1f);
    }
    static void JointForce(string part, string connected, float force)
    {
        // changes the break strength of an existing joint, keeping its tensor and solver settings
        var t = part == "" ? root : Find(root, part);
        if (t == null) { log.AppendLine("JOINT: no part " + part); return; }
        var so = new SerializedObject(C(t, "AeroPart"));
        var js = so.FindProperty("joints");
        for (int i = 0; i < js.arraySize; i++)
        {
            var j = js.GetArrayElementAtIndex(i);
            var cp = j.FindPropertyRelative("connectedPart").objectReferenceValue as Component;
            // the root is still named after the AB-4 source prefab while building, so match it as the part with no parent
            if (cp == null || (connected == "PB22Trident" ? cp.transform.parent != null : cp.name != connected)) continue;
            j.FindPropertyRelative("breakForce").floatValue = force;
            j.FindPropertyRelative("breakTorque").floatValue = force;
            so.ApplyModifiedPropertiesWithoutUndo();
            return;
        }
        if (Find(root, connected) != null) log.AppendLine("JOINT: " + part + " has no joint to " + connected);
    }
    static void Durability()
    {
        Arm("", 20f, 14f, 70f, 5f);
        Arm("fuselage_F", 20f, 14f, 70f, 5f);
        Arm("fuselage_R", 20f, 14f, 70f, 5f);
        Arm("fuselage_FF", 40f, 30f, 80f, 6f);
        Arm("cockpit", 40f, 30f, 80f, 6f);
        Arm("nose", 15f, 4f, 40f, 2.5f);
        Arm("tail", 20f, 8f, 70f, 4f);
        Arm("rudder_L", 15f, 4f, 40f, 2.5f);
        JointForce("rudder_L", "tail", 120000f); JointForce("rudder_L", "fuselage_R", 120000f); JointForce("rudder_L", "PB22Trident", 100000f);
        foreach (var s in new[] { "L", "R" })
        {
            Arm("intake_" + s, 20f, 8f, 70f, 4f);
            Arm("gearbay_" + s, 20f, 8f, 70f, 4f);
            Arm("wingroot_" + s, 20f, 8f, 70f, 4f);
            Arm("engines_" + s, 20f, 8f, 70f, 4f);
            Arm("nozzles_" + s, 15f, 6f, 40f, 3f);
            Arm("wing1_" + s, 15f, 6f, 60f, 3f);
            Arm("wing2_" + s, 15f, 6f, 60f, 3f);
            Arm("wingtip_" + s, 15f, 4f, 40f, 2.5f);
            Arm("flap_" + s, 15f, 4f, 40f, 2.5f);
            Arm("spoiler_" + s, 15f, 4f, 40f, 2.5f);
            Arm("elevator_" + s, 15f, 4f, 40f, 2.5f);
            // the gear pods carry the main gear loads: an AI takeoff tore one off at the AB-4's 200 k, so they get Darkreach-class mounts
            JointForce("gearbay_" + s, "PB22Trident", 1000000f); JointForce("gearbay_" + s, "fuselage_R", 800000f);
            JointForce("gearbay_" + s, "wingroot_" + s, 800000f); JointForce("gearbay_" + s, "engines_" + s, 600000f);
            JointForce("elevator_" + s, "fuselage_R", 200000f); JointForce("elevator_" + s, "tail", 200000f);
            JointForce("elevator_" + s, "engines_" + s, 150000f); JointForce("elevator_" + s, "nozzles_" + s, 150000f);
            JointForce("flap_" + s, "wing1_" + s, 100000f); JointForce("flap_" + s, "wing2_" + s, 100000f);
            // engine damage: the engine bay weighs most, intake and nozzle a quarter each (the AB-4's 1.3 on the nozzle let nozzle hits
            // kill engines), all at 80 HP like the Darkreach
            string n = s == "L" ? "1" : "3";
            var tf = C(Need(root, "engine" + n), "Turbofan");
            Size(tf, "criticalParts", 3);
            string[] cp = { "engines_" + s, "intake_" + s, "nozzles_" + s }; float[] cw = { 0.5f, 0.25f, 0.25f };
            for (int i = 0; i < 3; i++)
            {
                Set(tf, "criticalParts.Array.data[" + i + "].part", C(Need(root, cp[i]), "AeroPart"));
                Set(tf, "criticalParts.Array.data[" + i + "].threshold", 80f);
                Set(tf, "criticalParts.Array.data[" + i + "].weight", cw[i]);
            }
        }
        // fuel: easier to light than the Medusa (40-100), harder than the Darkreach (2-10); leaks below 60 HP
        foreach (var ft in root.GetComponentsInChildren<Component>(true).Where(c => c != null && c.GetType().Name == "FuelTank"))
        {
            Set(ft, "leakThreshold", 60f); Set(ft, "leakPerHP", 2f); Set(ft, "maxLeakRate", 50f);
            Set(ft, "ignitionPierceMin", 4f); Set(ft, "ignitionPierceMax", 40f);
            Set(ft, "ignitionBlastMin", 4f); Set(ft, "ignitionBlastMax", 40f);
            Set(ft, "fireIntensity", 1.75f);
        }
        log.AppendLine("durability set");
    }

    // ------------------------------------------------------------------ mass, lift, drag, fuel, engines (filled in by the tuning pass)
    // mass kg, wingArea m2, dragArea m2, fuel kg (PB-22 data pack: 56 t empty, 53.55 t fuel, 183.6 m2 wing at 20 deg)
    static void Part(string path, float mass, float area, float drag, float fuel)
    {
        var t = path == "" ? root : Need(root, path);
        var ap = C(t, "AeroPart");
        Set(ap, "mass", mass); Set(ap, "wingArea", area); Set(ap, "dragArea", drag);
        if (fuel >= 0f) Set(C(t, "FuelTank"), "fuelCapacity", fuel);
    }
    static void Aero()
    {
        // lifting area 2x the 0.3.0 values: at full fuel the wing loading was far above the AB-4's and the jet could not
        // reach lift-off before the engines scrape the runway (6.4 deg pitch). The sweep area change is doubled to match.
        // dragArea about 0.4x the first pass (real-world figures): summed 8.4 against the AB-4's 5.0 for 1.6x its thrust
        Part("", 9000f, 40f, 0.6f, 23000f);
        Part("fuselage_F", 4000f, 12f, 0.5f, 10000f);
        Part("fuselage_FF", 2500f, 0f, 0.06f, -1f);
        Part("cockpit", 2500f, 0f, 0.5f, -1f);
        Part("nose", 1300f, 0f, 0.08f, -1f);
        Part("fuselage_R", 3000f, 0f, 0.5f, 1000f);
        Part("tail", 1500f, 0f, 0.3f, -1f);
        Part("rudder_L", 900f, 12f, 0f, -1f);
        foreach (var s in new[] { "L", "R" })
        {
            Part("intake_" + s, 1500f, 0f, 0.35f, -1f);
            Part("gearbay_" + s, 2000f, 0f, 0.6f, 2500f);
            Part("wingroot_" + s, 3000f, 40f, 0.18f, 3500f);
            // the wing is three pieces since 0.4.1; mass, area, drag and fuel split by panel size (sums unchanged)
            Part("wing1_" + s, 2250f, 82f, 0.95f, 3100f);
            Part("wing2_" + s, 450f, 22f, 0.23f, 675f);
            Part("wingtip_" + s, 100f, 0f, 0.02f, -1f);
            Part("spoiler_" + s, 150f, 3f, 0f, -1f);
            Part("flap_" + s, 300f, 4f, 0f, -1f);
            Part("engines_" + s, 3400f, 0f, 0.3f, -1f);
            Part("nozzles_" + s, 400f, 0f, 0.3f, -1f);
            Part("elevator_" + s, 900f, 16f, 0f, -1f);
            // lift points: the flap's deployed area acts near the wing's own lift centre, not at the flap hinge 4 m behind
            // the CG (that nose-down moment beat the tail until the flaps retracted at 504 km/h)
            Set(C(Need(root, "flap_" + s), "AeroPart"), "centerOfLift", new Vector3(0f, 0f, 3.65f));
            // the outer panel and glove lift acted at their hull centres (z -5.67 and -4.87), 3.1 m and 2.3 m behind the CG and
            // behind the main wheels (z -3.9): with the flaps' +8 deg on the outer panels that held the nose wheel down until the
            // flaps retracted (about 400 km/h at full fuel). Like the AB-4, keep the wing lift near the CG and let the tail do the rest.
            Set(C(Need(root, "wing1_" + s), "AeroPart"), "centerOfLift", new Vector3(0f, 0f, 3.0f));      // acts at z -3.17
            Set(C(Need(root, "wingroot_" + s), "AeroPart"), "centerOfLift", new Vector3(0f, 0f, 2.0f));   // acts at z -2.87
            // the outer panel's lift acts at the same point as the inner panel's, so the split leaves the handling as it was
            {
                var w1t = Need(root, "wing1_" + s); var w2t = Need(root, "wing2_" + s);
                var ln1 = Get(C(w1t, "AeroPart"), "liftNormal") as Transform; var ln2 = Get(C(w2t, "AeroPart"), "liftNormal") as Transform;
                Vector3 pt = w1t.position + (ln1 != null ? ln1.rotation : w1t.rotation) * new Vector3(0f, 0f, 3.0f);
                Set(C(w2t, "AeroPart"), "centerOfLift", Quaternion.Inverse(ln2 != null ? ln2.rotation : w2t.rotation) * (pt - w2t.position));
            }
            Set(C(Need(root, "gear_" + s), "LandingGear"), "extendedDrag", 8f);

            string n = s == "L" ? "1" : "3";
            var tf = C(Need(root, "engine" + n), "Turbofan");
            Set(tf, "staticThrust", 142000f);
            Set(tf, "fuelConsumptionMax", 3.2f);
            Set(tf, "fuelConsumptionMin", 0.4f);
            Set(tf, "altitudeThrust", new AnimationCurve(new Keyframe(0f, 1f), new Keyframe(10000f, 0.92f), new Keyframe(14000f, 0.45f), new Keyframe(17000f, 0.15f)));
            var jn = C(Need(root, "nozzle" + n), "JetNozzle");
            Set(jn, "afterburners.Array.data[0].thrust", 103000f);
            Set(jn, "afterburners.Array.data[0].fuelConsumption", 2.4f);
        }
        Set(root.GetComponent<Rigidbody>(), "m_Mass", 56000f);
        // capacitor: stock 400 shows as 500 in game; 680 shows as 850. Recharge 1.75x stock for the two big engines
        var ps = C(root, "PowerSupply");
        Set(ps, "maxCharge", 480f); Set(ps, "maxPower", 105f); Set(ps, "chargePerRPM", 0.0035f);
        // jammer one step above stock (8); with the 480 capacitor it holds full power for about 20 s
        Set(C(root, "RadarJammer"), "jammingIntensity", 9f);

        var par = AssetDatabase.LoadMainAssetAtPath(MOD + "PB22Trident_Parameters.asset");
        var so = new SerializedObject(par);
        so.FindProperty("aircraftGLimit").floatValue = 4f;
        so.FindProperty("PIDReferenceAirspeed").floatValue = 220f;
        so.FindProperty("maxSpeed").floatValue = 300f;
        so.FindProperty("takeoffSpeed").floatValue = 160f;
        so.FindProperty("takeoffDistance").floatValue = 1800f;
        so.FindProperty("turningRadius").floatValue = 5000f;
        so.FindProperty("cornerSpeed").floatValue = 180f;   // stock AB-4 / Darkreach value; the AI flies the landing pattern at this
        so.FindProperty("approachSpeed").floatValue = 85f;
        so.FindProperty("landingSpeed").floatValue = 135f;  // 0.4.9 test at 170 touched down at 420 km/h and floated; keep 135
        so.FindProperty("shortLandingSpeed").floatValue = 80f;
        so.FindProperty("DefaultFuelLevel").floatValue = 0.5f;
        so.FindProperty("rankRequired").intValue = 5;   // 2026-10-25: rank 5, same as the Darkreach
        so.FindProperty("groundTurningRadius").floatValue = 30f;
        // the AB-4 liveries are addressables this project cannot ship and are mapped to the AB-4 UVs anyway;
        // our own damage diagram and sweep gauge art (copies of the AB-4 UI prefabs, see UI/)
        so.FindProperty("StatusDisplay").objectReferenceValue = AssetDatabase.LoadAssetAtPath<GameObject>(MOD + "UI/PB22_StatusDisplay.prefab");
        so.FindProperty("HUDExtras").objectReferenceValue = AssetDatabase.LoadAssetAtPath<GameObject>(MOD + "UI/PB22_HUDExtras.prefab");
        // the hangar preview and the Fly button index liveries[0] and fail on an empty list, so keep one entry
        // our three liveries (LiveryData assets inside the mod folder; PB22Skin.Apply creates them): the mod builder turns
        // each reference into an addressable override. liveries[0] is the default the hangar preview and Fly button use.
        string[,] LIV = { { "Matte Grey", "PB22_livery_grey" }, { "Maritime Blue", "PB22_livery_maritime" }, { "Low-Level Camo", "PB22_livery_lowlevel" } };
        var liv = so.FindProperty("liveries"); liv.arraySize = LIV.GetLength(0);
        for (int i = 0; i < LIV.GetLength(0); i++)
        {
            var li = liv.GetArrayElementAtIndex(i);
            li.FindPropertyRelative("name").stringValue = LIV[i, 0];
            li.FindPropertyRelative("faction").objectReferenceValue = null;
            var ar = li.FindPropertyRelative("assetReference");
            string guid = AssetDatabase.AssetPathToGUID(MOD + "Art/" + LIV[i, 1] + ".asset");
            if (string.IsNullOrEmpty(guid)) log.AppendLine("MISSING LIVERY " + LIV[i, 1] + " (run PB22/Apply Skin Textures first)");
            ar.FindPropertyRelative("m_AssetGUID").stringValue = guid;
            ar.FindPropertyRelative("m_SubObjectName").stringValue = "";
        }
        // four hardpoint sets now (heater bays removed): trim every loadout to four entries
        Object piledriver = null;
        for (int i = 0; i < so.FindProperty("StandardLoadouts").arraySize; i++)
        {
            var w = so.FindProperty("StandardLoadouts.Array.data[" + i + "].loadout.weapons");
            if (w.arraySize > 3 && w.GetArrayElementAtIndex(3).objectReferenceValue != null && w.GetArrayElementAtIndex(3).objectReferenceValue.name == "BallisticMissile1_single")
                piledriver = w.GetArrayElementAtIndex(3).objectReferenceValue;
            w.arraySize = 4;
        }
        for (int i = 0; i < so.FindProperty("loadouts").arraySize; i++) so.FindProperty("loadouts.Array.data[" + i + "].weapons").arraySize = 4;
        // default loadout: four Piledrivers on the pylons (ground clearance check)
        so.FindProperty("loadouts.Array.data[0].weapons.Array.data[3]").objectReferenceValue = piledriver;
        so.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(par);

        var def = AssetDatabase.LoadMainAssetAtPath(MOD + "PB22Trident_def.asset");
        so = new SerializedObject(def);
        so.FindProperty("mass").floatValue = 56000f;
        so.FindProperty("value").floatValue = 225f;   // 2026-10-25: same as the Darkreach (rank 5); AB-4 390 (rank 6)
        so.FindProperty("radarSize").floatValue = 0.08f;  // 2026-10-25: same as the Revoker (Brawler 0.6, Darkreach 0.01)
        so.FindProperty("spawnOffset").vector3Value = new Vector3(0f, 2.85f, 0f);
        so.FindProperty("restRotation").vector3Value = Vector3.zero;
        so.FindProperty("aircraftInfo.emptyWeight").floatValue = 56000f;
        so.FindProperty("aircraftInfo.maxWeight").floatValue = 124000f;
        so.FindProperty("aircraftInfo.maxSpeed").floatValue = 2280f;
        so.FindProperty("aircraftInfo.stallSpeed").floatValue = 290f;
        so.FindProperty("aircraftInfo.maneuverability").floatValue = 4f;
        so.FindProperty("mapIconSize").floatValue = 1.8f;       // stock 1.1-1.3; the long slim planform still read small at 1.5
        // role identity matches the Darkreach (pure surface striker)
        so.FindProperty("roleIdentity.antiSurface").floatValue = 1f;
        so.FindProperty("roleIdentity.antiAir").floatValue = 0f;
        so.FindProperty("roleIdentity.antiMissile").floatValue = 0f;
        so.FindProperty("roleIdentity.antiRadar").floatValue = 0f;
        so.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(def);
        AssetDatabase.SaveAssets();
    }

    // ------------------------------------------------------------------ LOD: LOD0 every visible mesh, LOD1 the LoD colmesh shells
    // formation (slime) light strips on the intake flanks and both faces of the fin: switched with the nav lights, and the
    // taxi wiggle fix (no yaw weathervaning in the fly-by-wire, as on the Darkreach)
    const string PH_MAT = "Assets/Blueprinter/_donotship/Material/";
    static void Lights()
    {
        var nl = C(root, "NavLights");
        var gearF = Get(nl, "navLights.Array.data[0].gear");
        var on = AssetDatabase.LoadAssetAtPath<Material>(PH_MAT + "slimelight_on_PLACEHOLDER.mat");
        var off = AssetDatabase.LoadAssetAtPath<Material>(PH_MAT + "light_green_off_PLACEHOLDER.mat");
        var strips = new[] { new[] { "slimelight_IL", "intake_L" }, new[] { "slimelight_IR", "intake_R" },
                             new[] { "slimelight_FinL", "rudder_L" }, new[] { "slimelight_FinR", "rudder_L" } };
        Size(nl, "navLights", 3 + strips.Length);
        for (int i = 0; i < strips.Length; i++)
        {
            var owner = Need(root, strips[i][1]);
            var t = New(strips[i][0], owner); Part(t, strips[i][0]);
            t.GetComponent<MeshRenderer>().sharedMaterial = off;
            string e = "navLights.Array.data[" + (3 + i) + "].";
            Set(nl, e + "renderer", t.GetComponent<MeshRenderer>());
            Size(nl, e + "objects", 0);
            Set(nl, e + "litMaterial", on);
            Set(nl, e + "part", C(owner, "AeroPart"));
            Set(nl, e + "gear", gearF);
            Set(nl, e + "controlState", 1);
        }
        Set(C(Need(root, "cockpit"), "ControlsFilter"), "flyByWire.yawWeathervaning", 0f);
    }

    // every skin renderer must be in some part's damageMaterial.renderers, or it never gets the livery (it stays default
    // grey: the stabilator tops, slats, leg doors and mid pylons did). Child renderers join their nearest owning part.
    static void SkinCoverage()
    {
        var covered = new HashSet<Renderer>();
        var owners = new List<Component>();
        foreach (var c in root.GetComponentsInChildren<Component>(true))
        {
            if (c == null) continue;
            var p = new SerializedObject(c).FindProperty("damageMaterial.renderers");
            if (p == null) continue;
            owners.Add(c);
            for (int i = 0; i < p.arraySize; i++) { var r = p.GetArrayElementAtIndex(i).objectReferenceValue as Renderer; if (r != null) covered.Add(r); }
        }
        foreach (var r in root.GetComponentsInChildren<MeshRenderer>(true))
        {
            if (covered.Contains(r) || !r.sharedMaterials.Any(m => m != null && m.name.StartsWith("PB22_skin"))) continue;
            if (owners.Any(o => o.transform == r.transform)) continue;        // a part's own renderer is always skinned
            Component own = null;
            for (var t = r.transform.parent; t != null && own == null; t = t.parent) own = owners.FirstOrDefault(o => o.transform == t);
            if (own == null) { log.AppendLine("no skin owner for " + r.name); continue; }
            var so = new SerializedObject(own); var arr = so.FindProperty("damageMaterial.renderers");
            arr.arraySize++; arr.GetArrayElementAtIndex(arr.arraySize - 1).objectReferenceValue = r;
            so.ApplyModifiedPropertiesWithoutUndo();
            log.AppendLine("skin " + r.name + " -> " + own.name);
        }
        // the game only falls back to a part's own renderer when its list is empty; once we add children to a list
        // (gear bay doors, slats...) the part's own skin must be in it too, or that part loses the livery
        foreach (var o in owners)
        {
            var mr = o.GetComponent<MeshRenderer>();
            if (mr == null || !mr.sharedMaterials.Any(m => m != null && m.name.StartsWith("PB22_skin"))) continue;
            var so = new SerializedObject(o); var arr = so.FindProperty("damageMaterial.renderers");
            if (arr.arraySize == 0) continue;
            bool self = false;
            for (int i = 0; i < arr.arraySize; i++) if (arr.GetArrayElementAtIndex(i).objectReferenceValue == mr) self = true;
            if (self) continue;
            arr.arraySize++; arr.GetArrayElementAtIndex(arr.arraySize - 1).objectReferenceValue = mr;
            so.ApplyModifiedPropertiesWithoutUndo();
            log.AppendLine("skin self " + o.name);
        }
    }

    static void Lods()
    {
        var lg = root.GetComponent<LODGroup>();
        var all = root.GetComponentsInChildren<Renderer>(true).Where(x => x is MeshRenderer || x is SkinnedMeshRenderer).ToArray();
        var lod1 = all.Where(x => x.name == "LoD").ToArray();
        var lod0 = all.Where(x => x.name != "LoD").ToArray();
        var lods = lg.GetLODs();
        lods[0].renderers = lod0; lods[1].renderers = lod1;
        lods[0].screenRelativeTransitionHeight = 0.05f; lods[1].screenRelativeTransitionHeight = 0.001f;   // stock bombers
        lg.fadeMode = LODFadeMode.None;
        lg.SetLODs(lods);
        lg.RecalculateBounds();
        log.AppendLine("LOD0 " + lod0.Length + " LOD1 " + lod1.Length);
    }
    // ------------------------------------------------------------------ review snapshots: renders the prefab from a few angles into <project>/PB22Snaps
    // pose: sweep 0..45, gear 0 down..1 up, flap 0..1, spoiler deg, split deg, elev deg, rudder deg, bay 0..1, steer deg
    // stock loadout i hung on the aircraft (gear down, bays open), with a fit report: ground clearance and any collider overlaps
    static int snapLoadout = -1;
    public static string SnapLoadout(int i, string views)
    {
        snapLoadout = i;
        try { return Snap("loadout" + i, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 1f, 0f, views); }
        finally { snapLoadout = -1; }
    }
    static void HangLoadout(GameObject go, int i, StringBuilder rep)
    {
        var wm = go.GetComponentsInChildren<Component>(true).First(c => c != null && c.GetType().Name == "WeaponManager");
        var so = new SerializedObject(wm);
        var sets = so.FindProperty("hardpointSets");
        var spawned = new List<GameObject>();
        rep.AppendLine((string)Stock[i][0]);
        for (int j = 0; j < sets.arraySize && j < 5; j++)
        {
            var m = Mnt(Stock[i][2 + j]); if (m == null) continue;
            var pf = new SerializedObject(m).FindProperty("prefab").objectReferenceValue as GameObject;
            var hps = sets.GetArrayElementAtIndex(j).FindPropertyRelative("hardpoints");
            for (int h = 0; h < hps.arraySize; h++)
            {
                var tr = hps.GetArrayElementAtIndex(h).FindPropertyRelative("transform").objectReferenceValue as Transform;
                var inst = (GameObject)Object.Instantiate(pf, tr); inst.hideFlags = HideFlags.DontSave; inst.name = "LOAD_" + j + "_" + h;
                spawned.Add(inst);
            }
        }
        Physics.SyncTransforms();
        var mine = new HashSet<Collider>(spawned.SelectMany(g => g.GetComponentsInChildren<Collider>(true)));
        var air = go.GetComponentsInChildren<Collider>(true).Where(c => c.enabled && !c.isTrigger && !mine.Contains(c)).ToList();
        foreach (var g in spawned)
        {
            float low = g.GetComponentsInChildren<Renderer>(true).Min(r => r.bounds.min.y);
            rep.AppendLine("  " + g.name + " under " + g.transform.parent.name + ": ground clearance " + (low + 2.85f).ToString("F2") + " m");
            foreach (var c in g.GetComponentsInChildren<Collider>(true))
            {
                foreach (var o in air.Concat(mine.Where(x => !x.transform.IsChildOf(g.transform))))
                {
                    if (!c.bounds.Intersects(o.bounds)) continue;
                    Vector3 d; float dist;
                    if (Physics.ComputePenetration(c, c.transform.position, c.transform.rotation, o, o.transform.position, o.transform.rotation, out d, out dist))
                        rep.AppendLine("    OVERLAP " + c.name + " with " + o.name + " (" + dist.ToString("F2") + " m)");
                }
            }
        }
    }

    public static string Snap(string tag, float sweep, float gear, float flap, float spoiler, float split, float elev, float rudder, float bay, float steer, string views)
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(DST);
        var go = (GameObject)Object.Instantiate(prefab);
        go.hideFlags = HideFlags.DontSave;
        var log2 = new StringBuilder();
        try
        {
            var t = go.transform;
            foreach (var s in new[] { "L", "R" })
            {
                float sg = s == "R" ? 1f : -1f;
                var hb = Find(t, "wingHinge_" + s + "b") ?? Find(t, "wingHinge_rb");
                var w1 = Find(t, "wing1_" + s);
                // shared-rb sweep: the wing rides the anchor
                w1.SetParent(hb, true); hb.localEulerAngles = new Vector3(0f, 0f, sweep);
                Find(t, "flapHinge_" + s + "1").GetChild(0).localEulerAngles = new Vector3(-25f * flap, 0f, 0f);
                Find(t, "slatHinge_" + s + "2").localEulerAngles = new Vector3(20f * flap, 0f, 0f);
                Find(t, "spoilerHinge_" + s + "2").localEulerAngles = new Vector3(spoiler, 0f, 0f);
                Find(t, "spoilerSplit_" + s).localEulerAngles = new Vector3(split, 0f, 0f);
                Find(t, "elevatorHinge_" + s + "1").GetChild(0).localEulerAngles = new Vector3(-elev, 0f, 0f);
                // as the game drives it: leg angle, brace angle and door angles linear in the fold, then the LookAt parts
                Find(t, "gearHinge_" + s).localEulerAngles = new Vector3(-90f * sg * gear, 0f, 0f);
                Find(t, "braceU_" + s).localEulerAngles = new Vector3(0f, 0f, -48.9f * sg * gear);
                float door = 1f - gear;
                Find(t, "gearDoorHinge_" + s + "O2").localEulerAngles = new Vector3(0f, 0f, 90f * sg * door);
                Find(t, "gearDoorHinge_" + s + "I2").localEulerAngles = new Vector3(0f, 0f, -180f * sg * door);
                Find(t, "gearDoorHinge_F" + s + "1").GetChild(0).localEulerAngles = new Vector3(0f, 0f, 90f * sg * door);
                Find(t, "braceL_" + s).LookAt(Find(t, "braceKnee_" + s));
                Find(t, "actCyl_" + s).LookAt(Find(t, "actTgtRod_" + s));
                Find(t, "actRod_" + s).LookAt(Find(t, "actTgtAnchor_" + s));
            }
            Find(t, "gearhinge_F").localEulerAngles = new Vector3(95f * gear, 0f, 0f);
            Find(t, "gear_unsprung_F").localEulerAngles = new Vector3(0f, steer, 0f);
            Find(t, "rudder_L_hinge1").GetChild(0).localEulerAngles = new Vector3(-rudder, 0f, 0f);
            foreach (var d in new[] { "FL", "FR", "RL", "RR" })
            {
                var h1 = Find(t, "bayDoorHinge_" + d + "1"); float sg = d.EndsWith("R") ? 1f : -1f;
                h1.GetChild(0).localEulerAngles = new Vector3(0f, 0f, 90f * sg * bay);
            }
            if (snapLoadout >= 0) HangLoadout(go, snapLoadout, log2);
            var lg = go.GetComponent<LODGroup>(); if (lg != null) lg.ForceLOD(0);
            foreach (var r in go.GetComponentsInChildren<Renderer>(true)) if (r.name == "LoD") r.enabled = false;

            var camGO = new GameObject("snapcam"); camGO.hideFlags = HideFlags.DontSave;
            var cam = camGO.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.55f, 0.6f, 0.68f);
            cam.fieldOfView = 30f; cam.nearClipPlane = 0.1f; cam.farClipPlane = 500f;
            var lightGO = new GameObject("snaplight"); lightGO.hideFlags = HideFlags.DontSave;
            var li = lightGO.AddComponent<Light>(); li.type = LightType.Directional; li.intensity = 1.3f; lightGO.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane); ground.hideFlags = HideFlags.DontSave;
            ground.transform.position = new Vector3(0f, -2.85f, 0f); ground.transform.localScale = new Vector3(10f, 1f, 10f);
            var rt = new RenderTexture(1600, 1000, 24); cam.targetTexture = rt;
            string dir = System.IO.Path.GetFullPath("PB22Snaps"); System.IO.Directory.CreateDirectory(dir);
            var V = new Dictionary<string, KeyValuePair<Vector3, Vector3>> {
                {"3q", new KeyValuePair<Vector3, Vector3>(new Vector3(32f, 14f, 38f), new Vector3(0f, -0.5f, 0f))},
                {"rear3q", new KeyValuePair<Vector3, Vector3>(new Vector3(-30f, 12f, -40f), new Vector3(0f, -0.5f, -2f))},
                {"side", new KeyValuePair<Vector3, Vector3>(new Vector3(-75f, 0f, 0f), new Vector3(0f, -0.5f, 0f))},
                {"front", new KeyValuePair<Vector3, Vector3>(new Vector3(0f, 0f, 75f), new Vector3(0f, -0.5f, 0f))},
                {"top", new KeyValuePair<Vector3, Vector3>(new Vector3(0f, 80f, -0.01f), new Vector3(0f, 0f, 0f))},
                {"under", new KeyValuePair<Vector3, Vector3>(new Vector3(0.01f, -60f, -0.01f), new Vector3(0f, 0f, 0f))},
                {"gear", new KeyValuePair<Vector3, Vector3>(new Vector3(-9f, -1.2f, 6f), new Vector3(-2.6f, -1.7f, -3.8f))},
                {"nose", new KeyValuePair<Vector3, Vector3>(new Vector3(-6f, -1.3f, 11f), new Vector3(0f, -1.6f, 6.0f))},
                {"cockpit", new KeyValuePair<Vector3, Vector3>(new Vector3(-6f, 3f, 16f), new Vector3(0f, 0.3f, 10.0f))},
                {"wing", new KeyValuePair<Vector3, Vector3>(new Vector3(12f, 8f, -16f), new Vector3(7f, -0.7f, -6f))},
                {"tail", new KeyValuePair<Vector3, Vector3>(new Vector3(-12f, 4f, -26f), new Vector3(0f, 0.5f, -14f))},
                {"lofront", new KeyValuePair<Vector3, Vector3>(new Vector3(-13f, -1.6f, 20f), new Vector3(0f, -1.6f, -2f))},
                {"loside", new KeyValuePair<Vector3, Vector3>(new Vector3(-30f, -1.2f, 2f), new Vector3(0f, -1.2f, -1f))},
                {"lounder", new KeyValuePair<Vector3, Vector3>(new Vector3(-14f, -16f, 12f), new Vector3(0f, -1.2f, -1.5f))},
            };
            ground.SetActive(true);
            foreach (var v in views.Split(','))
            {
                var kv = V[v];
                ground.SetActive(v != "under" && v != "top" && v != "lounder");
                cam.transform.position = kv.Key; cam.transform.LookAt(kv.Value);
                cam.Render();
                RenderTexture.active = rt;
                var tex = new Texture2D(1600, 1000, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, 1600, 1000), 0, 0); tex.Apply();
                RenderTexture.active = null;
                var f = System.IO.Path.Combine(dir, tag + "_" + v + ".png");
                System.IO.File.WriteAllBytes(f, tex.EncodeToPNG());
                Object.DestroyImmediate(tex);
                log2.AppendLine(f);
            }
            cam.targetTexture = null; Object.DestroyImmediate(rt);
            Object.DestroyImmediate(camGO); Object.DestroyImmediate(lightGO); Object.DestroyImmediate(ground);
        }
        catch (System.Exception ex) { log2.AppendLine("ERROR " + ex); }
        finally { Object.DestroyImmediate(go); }
        return log2.ToString();
    }

    // ------------------------------------------------------------------ top-down part masks for the damage status display and the sweep gauge
    // writes <project>/PB22Snaps/status/<part>.png (white = part) from one fixed ortho camera, so every mask lines up
    public static string StatusMasks()
    {
        var log2 = new StringBuilder();
        string dir = System.IO.Path.GetFullPath(Application.dataPath + "/../PB22Snaps/status");
        System.IO.Directory.CreateDirectory(dir);
        var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(DST));
        var camGO = new GameObject("statusCam");
        var rt = new RenderTexture(1024, 1024, 24);
        var tex = new Texture2D(1024, 1024, TextureFormat.RGBA32, false);
        var white = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        white.SetColor("_BaseColor", Color.white);
        try
        {
            var t = go.transform;
            t.position = Vector3.zero; t.rotation = Quaternion.identity;
            var parts = go.GetComponentsInChildren<Component>(true).Where(c => c != null && c.GetType().Name == "AeroPart").ToList();
            var gears = go.GetComponentsInChildren<Component>(true).Where(c => c != null && c.GetType().Name == "LandingGear").Select(c => c.transform).ToList();
            var own = new Dictionary<Renderer, string>();
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                if (!(r is MeshRenderer || r is SkinnedMeshRenderer) || !r.enabled || !r.gameObject.activeInHierarchy) continue;
                if (r.name == "LoD" || r.name.StartsWith("afterburner") || r.name.Contains("glow") || r.name.Contains("flame")) continue;
                if (gears.Any(g => r.transform.IsChildOf(g))) continue;
                var mf = r.GetComponent<MeshFilter>(); if (r is MeshRenderer && (mf == null || mf.sharedMesh == null)) continue;
                Transform a = r.transform; string owner = null;
                while (a != null) { if (a.GetComponents<Component>().Any(c => c != null && c.GetType().Name == "AeroPart")) { owner = a.name; break; } a = a.parent; }
                if (owner == null) continue;
                var mats = new Material[r.sharedMaterials.Length]; for (int k = 0; k < mats.Length; k++) mats[k] = white;
                r.sharedMaterials = mats;
                own[r] = owner;
            }
            var b = new Bounds(Vector3.zero, Vector3.zero); bool first = true;
            foreach (var r in own.Keys) { if (first) { b = r.bounds; first = false; } else b.Encapsulate(r.bounds); }
            float half = Mathf.Max(b.size.x, b.size.z) * 0.53f;
            var cam = camGO.AddComponent<Camera>();
            cam.orthographic = true; cam.orthographicSize = half;
            cam.transform.position = new Vector3(b.center.x, b.max.y + 20f, b.center.z);
            cam.transform.rotation = Quaternion.LookRotation(Vector3.down, Vector3.forward);
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0f, 0f, 0f, 0f);
            cam.nearClipPlane = 1f; cam.farClipPlane = 100f; cam.cullingMask = 1 << 31; cam.targetTexture = rt;
            log2.AppendLine("frame center " + b.center + " half " + half);
            System.Func<Vector3, Vector2> px = w => { var v = cam.WorldToViewportPoint(w); return new Vector2(v.x * 1024f, (1f - v.y) * 1024f); };
            foreach (var n in new[] { "wingHinge_La", "wingHinge_Ra" }) { var h = Find(t, n); if (h != null) log2.AppendLine("pivot " + n + " px " + px(h.position)); }
            foreach (var name in own.Values.Distinct().ToList())
            {
                foreach (var kv in own) kv.Key.gameObject.layer = kv.Value == name ? 31 : 0;
                cam.Render();
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, 1024, 1024), 0, 0); tex.Apply(); RenderTexture.active = null;
                System.IO.File.WriteAllBytes(dir + "/" + name + ".png", tex.EncodeToPNG());
                log2.AppendLine("mask " + name);
            }
        }
        catch (System.Exception e) { log2.AppendLine("ERROR " + e); }
        finally { Object.DestroyImmediate(go); Object.DestroyImmediate(camGO); Object.DestroyImmediate(rt); Object.DestroyImmediate(tex); Object.DestroyImmediate(white); }
        return log2.ToString();
    }
}
