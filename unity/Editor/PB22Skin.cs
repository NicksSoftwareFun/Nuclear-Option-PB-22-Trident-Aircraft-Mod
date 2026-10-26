// PB-22 Trident: wire the painted skin textures into PB22_skin.mat and the grey livery.
// Menu: PB22/Apply Skin Textures. Expects Art/Skin/PB22_skin_{b,n,m,ao,dmg_b,dmg_n}.png and
// Art/Skin/PB22_livery_{maritime,lowlevel}_b.png and PB22_livery_{grey,maritime,lowlevel}_{bdf,pala}_b.png inside the
// mod folder; creates the extra LiveryData assets.
using UnityEditor;
using UnityEngine;

public static class PB22Skin
{
    const string MOD = "Assets/Blueprinter/Mods/PB22Trident/";
    const string SKIN = MOD + "Art/Skin/";

    static Texture2D Tex(string name, bool srgb, bool normal, bool alpha, int size = 2048)
    {
        string path = SKIN + name + ".png";
        var ti = (TextureImporter)AssetImporter.GetAtPath(path);
        if (ti == null) throw new System.Exception("missing " + path);
        ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
        ti.sRGBTexture = srgb;
        ti.alphaSource = alpha ? TextureImporterAlphaSource.FromInput : TextureImporterAlphaSource.None;
        ti.alphaIsTransparency = false;
        ti.mipmapEnabled = true;
        ti.maxTextureSize = size;
        // the 4K base colours carry the painted markings and panel lines; plain DXT keeps them at 4K affordable
        ti.textureCompression = size > 2048 ? TextureImporterCompression.Compressed : TextureImporterCompression.CompressedHQ;
        ti.wrapMode = TextureWrapMode.Clamp;
        ti.anisoLevel = 4;
        ti.SaveAndReimport();
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    static void Livery(string name, Texture2D tex)
    {
        string path = MOD + "Art/" + name + ".asset";
        if (AssetDatabase.LoadAssetAtPath<ScriptableObject>(path) == null)
            AssetDatabase.CopyAsset(MOD + "Art/PB22_livery_grey.asset", path);
        var liv = AssetDatabase.LoadAssetAtPath<ScriptableObject>(path);
        var so = new SerializedObject(liv);
        var tp = so.FindProperty("Texture"); if (tp != null) tp.objectReferenceValue = tex; else Debug.LogWarning(name + " has no Texture field");
        var gp = so.FindProperty("Glossiness"); if (gp != null) gp.floatValue = 0f;
        so.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(liv);
    }

    [MenuItem("PB22/Apply Skin Textures")]
    public static void Apply()
    {
        var b = Tex("PB22_skin_b", true, false, false);
        var n = Tex("PB22_skin_n", false, true, false);
        var m = Tex("PB22_skin_m", false, false, true);
        var ao = Tex("PB22_skin_ao", false, false, false);
        var db = Tex("PB22_skin_dmg_b", true, false, true);
        var dn = Tex("PB22_skin_dmg_n", false, true, false);

        var mat = AssetDatabase.LoadAssetAtPath<Material>(MOD + "Art/PB22_skin.mat");
        void Set(string prop, Texture t) { if (mat.HasProperty(prop)) mat.SetTexture(prop, t); else Debug.LogWarning("PB22_skin has no " + prop); }
        Set("_Basecolor", b); Set("_Normal", n); Set("_Metallic", m); Set("_AO", ao);
        Set("_BasecolorDmg", db); Set("_NormalDmg", dn); Set("_Livery", b);
        if (mat.HasProperty("_Glossiness")) mat.SetFloat("_Glossiness", 0f);
        EditorUtility.SetDirty(mat);

        Livery("PB22_livery_grey", b);
        // the two painted liveries are copies of the grey LiveryData with their own base-colour texture
        Livery("PB22_livery_maritime", Tex("PB22_livery_maritime_b", true, false, false));
        Livery("PB22_livery_lowlevel", Tex("PB22_livery_lowlevel_b", true, false, false));
        // faction versions (2026-10-25): each livery once with the BDF and once with the PALA insignia painted in
        foreach (var l in new[] { "grey", "maritime", "lowlevel" })
            foreach (var f in new[] { "bdf", "pala" })
                Livery("PB22_livery_" + l + "_" + f, Tex("PB22_livery_" + l + "_" + f + "_b", true, false, false));
        AssetDatabase.SaveAssets();
        Debug.Log("PB22 skin applied: " + AssetDatabase.GetAssetPath(b));
    }
}
