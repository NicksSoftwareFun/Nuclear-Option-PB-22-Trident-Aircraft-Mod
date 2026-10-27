PB-22 Trident Livery Bundle

Everything you need to paint a livery for the PB-22 Trident in Blender (or any 3D paint program).
This bundle matches mod version 1.0.5 and later. Liveries painted on the older template (1.0.0 to 1.0.4) do not
line up on 1.0.5, because the texture layout changed when the airframe was rebuilt.

FILES

PB22 Exterior.fbx
  The complete exterior of the aircraft, assembled: every part in place and named by part, gear up, doors and bays
  shut, wings fully forward, in metres. All of the skin is included; the internal frames and equipment are left out.
  The livery goes on material PB22_skin. It already points at "PB22 Base.png", so keep the FBX and the PNG files
  in the same folder. The other materials (glass, metal, mechanical) are not painted by a livery.

PB22 Base.png
  Base colour of the standard grey livery, 2048 x 2048. Paint your livery over this (or start from one of the
  shipped liveries).

PB22 UV Layout.png
  The outlines of the texture islands on a transparent background. Lay it over your work in a 2D editor.

PB22 Normals.png, PB22 Metallic.png, PB22 Roughness.png, PB22 Metallic Smoothness (game format).png, PB22 AO.png
  The shared surface maps, for previews in Blender or Substance. A livery does not change these.

Shipped Liveries
  The nine liveries that ship with the mod (Grey, Low-Level Camo and Maritime, each plain, BDF and PALA).

PAINTING IN BLENDER

1. File > Import > FBX, pick "PB22 Exterior.fbx". The aircraft appears with the grey base colour on the skin.
2. Select any skin part, switch to the Texture Paint workspace and paint on "PB22 Base" (or on a copy of a shipped
   livery: open it in the Image Editor and swap it into the PB22_skin material's image node).
3. Image > Save As, PNG, 2048 x 2048, in sRGB.

GOOD TO KNOW

- A livery only replaces the base colour. Panel lines, rivets and weathering in the normal and metallic maps stay
  on top of whatever you paint.
- The skin is double-sided in the game: the inside of the skin uses the same texture as the outside, so it shows
  through broken joints and damage holes in your colours, mirrored and in shadow. You don't paint anything extra.
- Keep important artwork away from the island edges in the UV layout. A thin margin round each island helps when
  the game shows the texture smaller at a distance.
