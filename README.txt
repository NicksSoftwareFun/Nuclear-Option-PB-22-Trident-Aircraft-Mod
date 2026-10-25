# PB-22 Trident

A modern long-range naval strike bomber for Nuclear Option, inspired by the Tu-22M3 Backfire. Swing wings, two afterburning engines, a four-seat cockpit and a big weapons load for hitting ships and ground targets from far away.

![PB-22 Trident](docs/images/1_ground_3q.png)

## Requirements

- Nuclear Option 0.34.2
- [BepInEx 5](https://github.com/BepInEx/BepInEx/releases) (Mono, x64)
- [Blueprinter](https://github.com/nikkorap/NOBlueprinter-Releases) 2.0.1 or newer

## Install

1. Install BepInEx 5 and Blueprinter.
2. Download `PB22Trident.dll` from the [releases page](../../releases).
3. Put it in `Nuclear Option\BepInEx\plugins`.
4. Start the game. The PB-22 Trident shows up with the other aircraft.

The mod is a single file. It needs nothing else from this repository.

## Mission: To Sink a Carrier

An optional mission made for the PB-22. Download `PB22-To-Sink-a-Carrier.zip` from the same release and unzip it into `%USERPROFILE%\AppData\LocalLow\Shockfront\NuclearOption\Missions`, so you end up with a `PB-22 - To Sink a Carrier` folder there. It shows up in the mission list. The mission files are also in `missions/` in this repository.

## The aircraft

- Variable-sweep wings, airbrakes, flaps and full landing gear animation.
- Forward and rear weapon bays, two glove pylons and two wing pylons. Preset loadouts for anti-ship, strike and escort roles.
- Built-in jammer.
- Four crew stations with ejection seats. The crew hatches double as entry doors.
- Live cockpit gauges and a working standby horizon.
- Three liveries: grey, Maritime Blue and Low-Level Camo.
- Fits through the medium hangar door.

## What the plugin does

`src/` is the full source of `PB22Trident.dll`. It carries the Blueprinter bundle (the aircraft itself) and adds a few things the bundle can't do on its own. Everything game-side is reached by reflection, and all of it only touches the PB-22.

- **Takeoff:** the stock AI pushes the nose down hard late in the PB-22's long ground roll. The plugin keeps the elevator neutral on the ground until the AI rotates.
- **Landing:** the PB-22's main wheels sit well behind its centre, so the AI misreads its height on touchdown and aborts. While the AI lands, the plugin gives it the main wheel height instead.
- **Engine fans:** the intake fans spin with engine RPM.
- **Gauges:** the cockpit needles and warning lamps read the game's flight, engine, fuel, power and damage state. Read only.

Optional settings are in `BepInEx\config\nick.nuclearoption.pb22trident.cfg`. `Testing/DebugLog` writes fan diagnostics to the BepInEx log (off by default). `Testing/LandingLog` writes one line each time an AI PB-22 changes landing phase.

## Building from source

- `art/scripts` builds the model and textures in Blender (`build_pb22_detail.py`, then `export_pb22.py`; textures in `art/scripts/tex`). `art/cockpit` builds the cockpit model and atlas.
- `unity/Editor` holds the Unity editor tools that assemble the prefab in a Blueprinter project (menu PB22). Build the bundle with Blueprinter > Mod Builder.
- Copy the `.nobp` next to `src/PB22Trident.csproj` and run `dotnet build -c Release -p:GameDir="<your Nuclear Option folder>"`.

## Licence

MIT. See [LICENSE](LICENSE) and [CREDITS.txt](CREDITS.txt).
