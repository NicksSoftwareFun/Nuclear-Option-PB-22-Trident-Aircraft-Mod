using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

// Builds the four external racks the PB-22 stock loadouts need that the game does not have:
// AShM-300 x2, Tusko-B x2 and GPO-500 x3 in tandem (front to back, about a Piledriver long) and a compact
// AGM-99 x3. Each is built from stock rack and missile prefabs (placeholder copies), so Blueprinter rewires
// every mesh back to the game's own assets. Child names are unique because Blueprinter patches by hierarchy path.
// Run PB22Mounts.Build(); it is idempotent (each prefab and mount is rebuilt from the placeholders).
public static class PB22Mounts
{
    const string DIR = "Assets/Blueprinter/Mods/PB22Trident/Mounts/";
    static StringBuilder log;

    [MenuItem("PB22/Rebuild Racks")]
    public static void Menu() { Debug.Log(Build()); }

    public static string Placeholder(string name, string type)
    {
        foreach (var g in AssetDatabase.FindAssets(name + "_PLACEHOLDER t:" + type))
        {
            var p = AssetDatabase.GUIDToAssetPath(g);
            if (System.IO.Path.GetFileNameWithoutExtension(p) == name + "_PLACEHOLDER") return p;
        }
        throw new System.Exception("no placeholder " + name + " (" + type + ")");
    }
    // stock mounts are the _donotship placeholders (Blueprinter maps them to the game's own); ours live in Mounts/
    public static Object Mount(string name)
    {
        var custom = AssetDatabase.LoadMainAssetAtPath(DIR + name + ".asset");
        if (custom != null) return custom;
        return AssetDatabase.LoadMainAssetAtPath(Placeholder(name, "WeaponMount"));
    }

    public static string Build()
    {
        log = new StringBuilder();
        if (!AssetDatabase.IsValidFolder(DIR.TrimEnd('/'))) AssetDatabase.CreateFolder("Assets/Blueprinter/Mods/PB22Trident", "Mounts");

        // tandem racks: the stores hang nose to tail under one long beam, about a Piledriver's length overall
        Tandem("PB22_AShM1_tandem", "AShM1_single", 2, 0.08f, 6.0f, "AShM-300 x2", "AShM1x2", 2, 40f, 0.26f, 0.02f);
        Tandem("PB22_AShM3_double", "AShM3_single", 2, 0.08f, 5.9f, "Tusko-B (HE) x2", "AShM3_single", 2, 50f, 0.09f, 0.02f);
        Tandem("PB22_bomb_500_triple", "bomb_500_single", 3, 0.06f, 6.6f, "GPO-500 x3", "bomb_500_double", 3, 0f, 0.55f, 0.03f);
        // AGM-99 x3: compact triangle (two on the shoulders, one underneath), laid out like the Scythe triple rack
        CompactTriple();
        AssetDatabase.SaveAssets();
        return log.ToString();
    }

    static GameObject CopyPrefab(string src, string dst)
    {
        var srcPath = Placeholder(src, "GameObject");
        var tmp = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(srcPath));
        PrefabUtility.UnpackPrefabInstance(tmp, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        tmp.name = dst;
        return tmp;
    }
    static GameObject Child(string prefabName, string childName)
    {
        var pf = AssetDatabase.LoadAssetAtPath<GameObject>(Placeholder(prefabName, "GameObject"));
        var t = pf.GetComponentsInChildren<Transform>(true).First(x => x.name == childName);
        return t.gameObject;
    }
    static Transform MissileOf(Transform t)
    {
        return t.GetComponentsInChildren<Component>(true).First(c => c != null && c.GetType().Name == "MountedMissile").transform;
    }
    static Bounds BoundsOf(Transform t)
    {
        var rs = t.GetComponentsInChildren<Renderer>(true);
        var b = rs[0].bounds; foreach (var r in rs) b.Encapsulate(r.bounds);
        return b;
    }

    // n copies of a stock single mount's store (with its own launch pylon, if it has one) in a line, front to back,
    // under a beam made from the Tusko-B single pylon stretched along the rack. Centred where the Piledriver hangs.
    static void Tandem(string key, string single, int n, float gap, float beamLen, string mountName, string copyFrom,
                       int ammo, float emptyMass, float drag, float emptyDrag)
    {
        const float CENTRE_Z = -0.04f;
        var go = CopyPrefab(single, key);
        try
        {
            var root = go.transform;
            var missile = MissileOf(root);
            var unit = missile.parent == root ? missile : missile.parent;
            var oldBeam = root.Cast<Transform>().FirstOrDefault(t => t != unit && t.name == "pylon");
            if (oldBeam != null) Object.DestroyImmediate(oldBeam.gameObject);
            var b = BoundsOf(unit);
            float len = b.size.z, total = n * len + (n - 1) * gap, front = CENTRE_Z + total / 2f;
            string baseName = unit.name;
            var lp = unit.localPosition;
            for (int i = 0; i < n; i++)
            {
                var u = i == 0 ? unit : Object.Instantiate(unit.gameObject, root).transform;
                u.name = baseName + "_" + (i + 1);
                u.localPosition = new Vector3(lp.x, lp.y, lp.z + (front - i * (len + gap)) - b.max.z);
                u.localRotation = unit.localRotation;
            }
            var beam = Object.Instantiate(Child("AShM3_single", "pylon"), root).transform;
            beam.name = "beam";
            beam.localPosition = new Vector3(0f, 0f, CENTRE_Z); beam.localRotation = Quaternion.identity;
            beam.localScale = new Vector3(0.9f, 0.75f, beamLen / 2.08f);
            log.AppendLine(key + ": store length " + len.ToString("F2") + " m, rack length " + total.ToString("F2") + " m");
            Save(go, key, copyFrom, copyFrom, mountName, ammo, emptyMass, drag, emptyDrag);
        }
        finally { Object.DestroyImmediate(go); }
    }

    static void CompactTriple()
    {
        const string key = "PB22_AShM2_triple";
        var go = CopyPrefab("AAM2_triple", key);
        try
        {
            var root = go.transform;
            foreach (var t in root.Cast<Transform>().Where(t => t.name.StartsWith("aam2")).ToArray()) Object.DestroyImmediate(t.gameObject);
            // shoulder pylons reach out to the side missiles, the belly pylon down to the lower one (kept narrow so the
            // outboard missile clears the main gear fairing on the outer pylons)
            var pl = root.Find("pylon_L"); var pr = root.Find("pylon_R"); var pb = root.Find("pylon_B");
            pl.localPosition = new Vector3(-0.20f, -0.21f, 0f); pl.localScale = new Vector3(0.67f, 1.30f, 1.00f);
            pr.localPosition = new Vector3(0.20f, -0.21f, 0f); pr.localScale = new Vector3(0.67f, 1.30f, 1.00f);
            pb.localPosition = new Vector3(0f, -0.355f, 0f); pb.localScale = new Vector3(0.67f, 1.56f, 1.00f);
            var ad = root.Find("doubleAdapter"); ad.localScale = new Vector3(1.00f, 1.20f, 1.60f);
            var src = Child("AShM2_double", "ASHM2");
            var at = new[] { new Vector3(-0.42f, -0.21f, 0.076f), new Vector3(0.42f, -0.21f, 0.076f), new Vector3(0f, -0.68f, 0.076f) };
            string[] nm = { "agm99_L", "agm99_R", "agm99_B" };
            for (int i = 0; i < 3; i++)
            {
                var m = Object.Instantiate(src, root).transform;
                m.name = nm[i]; m.localPosition = at[i]; m.localRotation = Quaternion.identity; m.localScale = Vector3.one;
            }
            var lod = go.GetComponent<LODGroup>();
            if (lod != null)
            {
                var lods = lod.GetLODs();
                if (lods.Length > 0) lods[0].renderers = go.GetComponentsInChildren<Renderer>(true).ToArray();
                for (int i = 1; i < lods.Length; i++) lods[i].renderers = lods[i].renderers.Where(r => r != null).ToArray();
                lod.SetLODs(lods); lod.RecalculateBounds();
            }
            Save(go, key, "AShM2_double", "AShM2_double", "AGM-99 x3", 3, 80f, 0.22f, 0.03f);
        }
        finally { Object.DestroyImmediate(go); }
    }

    static void Save(GameObject go, string key, string copyFrom, string infoFrom, string mountName, int ammo, float emptyMass, float drag, float emptyDrag)
    {
        var names = go.GetComponentsInChildren<Transform>(true).Select(t => PathOf(t, go.transform)).ToList();
        var dup = names.GroupBy(n => n).Where(g => g.Count() > 1).Select(g => g.Key).ToList();
        if (dup.Count > 0) log.AppendLine("DUPLICATE PATHS in " + key + ": " + string.Join(", ", dup));
        var pf = PrefabUtility.SaveAsPrefabAsset(go, DIR + key + ".prefab");

        string mpath = DIR + key + ".asset";
        var m = AssetDatabase.LoadMainAssetAtPath(mpath);
        if (m == null)
        {
            AssetDatabase.CopyAsset(Placeholder(copyFrom, "WeaponMount"), mpath);
            AssetDatabase.ImportAsset(mpath);
            m = AssetDatabase.LoadMainAssetAtPath(mpath);
        }
        var info = new SerializedObject(AssetDatabase.LoadMainAssetAtPath(Placeholder(infoFrom, "WeaponMount"))).FindProperty("info").objectReferenceValue;
        var so = new SerializedObject(m);
        so.FindProperty("prefab").objectReferenceValue = pf;
        so.FindProperty("jsonKey").stringValue = key;
        so.FindProperty("info").objectReferenceValue = info;
        so.FindProperty("mountName").stringValue = mountName;
        so.FindProperty("ammo").intValue = ammo;
        so.FindProperty("missileBay").boolValue = false;
        so.FindProperty("emptyMass").floatValue = emptyMass;
        so.FindProperty("drag").floatValue = drag;
        so.FindProperty("emptyDrag").floatValue = emptyDrag;
        so.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(m);
        int missiles = pf.GetComponentsInChildren<Component>(true).Count(c => c != null && c.GetType().Name == "MountedMissile");
        log.AppendLine(key + ": " + mountName + ", ammo " + ammo + ", MountedMissiles " + missiles + ", info " + (info ? info.name : "null"));
    }
    static string PathOf(Transform t, Transform root)
    {
        var s = t.name; while (t != root && t.parent != null) { t = t.parent; s = t.name + "/" + s; }
        return s;
    }
}
