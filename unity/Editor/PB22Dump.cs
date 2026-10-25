// Editor helper: write a prefab's hierarchy, components and serialized fields to a text file.
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

public static class PB22Dump
{
    static string Val(SerializedProperty p)
    {
        switch (p.propertyType)
        {
            case SerializedPropertyType.ObjectReference: return p.objectReferenceValue ? p.objectReferenceValue.name + "<" + p.objectReferenceValue.GetType().Name + ">" : "null";
            case SerializedPropertyType.Float: return p.floatValue.ToString("0.###");
            case SerializedPropertyType.Integer: return p.intValue.ToString();
            case SerializedPropertyType.Boolean: return p.boolValue.ToString();
            case SerializedPropertyType.Enum: return p.enumValueIndex >= 0 && p.enumValueIndex < p.enumDisplayNames.Length ? p.enumDisplayNames[p.enumValueIndex] : p.enumValueIndex.ToString();
            case SerializedPropertyType.String: return "\"" + p.stringValue + "\"";
            case SerializedPropertyType.Vector3: return p.vector3Value.ToString("F2");
            default: return p.isArray ? "[" + p.arraySize + "]" : p.propertyType.ToString();
        }
    }

    static void Walk(Transform t, int depth, StringBuilder sb, bool fields)
    {
        string ind = new string(' ', depth * 2);
        sb.AppendLine(ind + t.name + "  pos" + t.localPosition.ToString("F2") + (t.gameObject.activeSelf ? "" : " (inactive)"));
        foreach (var c in t.GetComponents<Component>())
        {
            if (c == null || c is Transform) continue;
            var n = c.GetType().Name;
            if (n == "MeshFilter") { var mf = (MeshFilter)c; sb.AppendLine(ind + "  - mesh " + (mf.sharedMesh ? mf.sharedMesh.name + " v" + mf.sharedMesh.vertexCount + " b" + mf.sharedMesh.bounds.size.ToString("F2") : "null")); continue; }
            if (n == "MeshRenderer") { var r = (Renderer)c; var s = ""; foreach (var m in r.sharedMaterials) s += (m ? m.name : "null") + ","; sb.AppendLine(ind + "  - renderer [" + s + "]" + (r.enabled ? "" : " disabled")); continue; }
            if (n == "MeshCollider") { var mc = (MeshCollider)c; sb.AppendLine(ind + "  - meshcollider " + (mc.sharedMesh ? mc.sharedMesh.name : "null") + (mc.convex ? " convex" : "")); continue; }
            sb.Append(ind + "  - " + n);
            if (fields && n != "AudioSource" && n != "ParticleSystem" && n != "ParticleSystemRenderer" && n != "Light" && n != "UniversalAdditionalLightData")
            {
                sb.Append(" {");
                var it = new SerializedObject(c).GetIterator(); bool enter = true;
                while (it.NextVisible(enter))
                {
                    enter = false;
                    if (it.name == "m_Script") continue;
                    sb.Append(it.name + "=" + Val(it));
                    if (it.isArray && it.propertyType == SerializedPropertyType.Generic && it.arraySize > 0 && it.arraySize <= 12)
                    {
                        sb.Append("(");
                        for (int i = 0; i < it.arraySize; i++) { var el = it.GetArrayElementAtIndex(i); sb.Append(Val(el) + (el.propertyType == SerializedPropertyType.Generic ? ":" + Sub(el) : "") + "|"); }
                        sb.Append(")");
                    }
                    else if (it.propertyType == SerializedPropertyType.Generic && !it.isArray) sb.Append(":" + Sub(it));
                    sb.Append("; ");
                }
                sb.Append("}");
            }
            sb.AppendLine();
        }
        foreach (Transform ch in t) Walk(ch, depth + 1, sb, fields);
    }

    static string Sub(SerializedProperty p)
    {
        var sb = new StringBuilder("{"); var end = p.GetEndProperty(); var it = p.Copy(); bool enter = true; int k = 0;
        while (it.NextVisible(enter) && !SerializedProperty.EqualContents(it, end) && k < 20) { enter = false; k++; sb.Append(it.name + "=" + Val(it) + " "); }
        return sb.Append("}").ToString();
    }

    public static string Dump(string prefab, string outPath)
    {
        var go = AssetDatabase.LoadAssetAtPath<GameObject>(prefab);
        var sb = new StringBuilder();
        Walk(go.transform, 0, sb, true);
        File.WriteAllText(outPath, sb.ToString());
        return outPath + " " + sb.Length;
    }
}
