Damage on the PB-22 now works the way it does on the stock aircraft, and the repository has a Livery Bundle for anyone who wants to paint their own liveries.

### Changes

- Damage now works like the stock aircraft. Parts break off along straight panel lines with no gaps at the joints, the skin can be seen from both sides, and torn metal edges come from the damage texture. A broken-off section shows the frames and the inside of the skin instead of a flat lid.
- Honeycomb core shows under torn skin, using the game's own honeycomb material.
- Tyres shred when the main gear pods are hit.
- Afterburner flame drawn at its intended length.
- Nose tip straightened. It sat 12 cm low and looked hooked.
- Structure no longer pokes through the skin behind the dorsal grilles or along the spine.
- Dorsal chaff dispensers restyled so they no longer read as holes.

### Livery Bundle

The [Livery Bundle](https://github.com/NicksSoftwareFun/nuclear-option-pb-22-trident-aircraft-mod/tree/main/Livery%20Bundle) folder has the complete exterior as an FBX with the in-game texture layout, the base colour, the surface maps, a UV layout overlay and all nine shipped liveries. Import `PB22 Exterior.fbx` into Blender and paint on the skin; the README in the folder has the steps.

The texture layout changed in this release, so liveries painted for 1.0.0 do not line up on 1.1.0.

### Install

You need BepInEx 5 and Blueprinter 2.0.1 or newer. Drop `PB22Trident.dll` into `Nuclear Option\BepInEx\plugins`, replacing the old one, and start the game.
