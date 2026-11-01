Bug fixes, and PB-22 liveries can now go on the Steam Workshop.

### Changes

- Workshop tag "PB-22 Trident" on the aircraft definition, so PB-22 liveries can be uploaded to the Steam Workshop (needs the game update from the end of October).
- Landing gear pods are much tougher: they take damage at half the rate, stay attached until well past zero health like the engine bays, and their mounts to the fuselage are 50% stronger. They were the first thing to fall off.
- Pylon stores now fire alternating left and right, outboard first and front to back. Side by side racks used to empty the whole left rack before the right one.
- A right engine fire is now called out as ENGINE 2 FIRE (it said ENGINE 3).

### Install

You need BepInEx 5, Blueprinter 2.0.1 or newer and the current game version. Drop `PB22Trident.dll` into `Nuclear Option\BepInEx\plugins`, replacing the old one, and start the game.

Livery makers: set `"Aircraft": "PB-22 Trident"` in your livery's meta.json to match the Workshop tag.
