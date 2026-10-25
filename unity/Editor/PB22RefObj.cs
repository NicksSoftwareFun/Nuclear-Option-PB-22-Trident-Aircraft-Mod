// Editor helper: export a prefab's MeshFilters to one OBJ (root space, one object per renderer, usemtl per submesh). Reference study only.
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

public static class PB22RefObj
{
    public static string Export(string prefab, string outPath)
    {
        var go = AssetDatabase.LoadAssetAtPath<GameObject>(prefab);
        var sb = new StringBuilder(); int vbase = 1; int n = 0;
        var inv = go.transform.worldToLocalMatrix;
        foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
        {
            var m = mf.sharedMesh; var r = mf.GetComponent<MeshRenderer>();
            if (m == null || r == null || !m.isReadable && false) continue;
            var path = mf.transform.name; var p = mf.transform.parent;
            while (p != null && p != go.transform) { path = p.name + "/" + path; p = p.parent; }
            sb.AppendLine("o " + path.Replace(' ', '_') + "|" + m.name);
            var M = inv * mf.transform.localToWorldMatrix;
            var vs = m.vertices;
            foreach (var v in vs) { var w = M.MultiplyPoint3x4(v); sb.AppendLine("v " + (-w.x).ToString("F4") + " " + w.z.ToString("F4") + " " + w.y.ToString("F4")); }
            for (int s = 0; s < m.subMeshCount; s++)
            {
                var mats = r.sharedMaterials;
                sb.AppendLine("usemtl " + (s < mats.Length && mats[s] ? mats[s].name.Replace(' ', '_') : "none"));
                var t = m.GetTriangles(s);
                for (int i = 0; i < t.Length; i += 3) sb.AppendLine("f " + (t[i] + vbase) + " " + (t[i + 2] + vbase) + " " + (t[i + 1] + vbase));
            }
            vbase += vs.Length; n++;
        }
        File.WriteAllText(outPath, sb.ToString());
        return outPath + " objs " + n;
    }
}
