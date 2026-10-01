# Car credits — INK DRIFT: TOKYO

## Procedural fallback cars (original work)

The 5 playable cars (`hachi`, `kaiju`, `zenkai`, `raijin`, `tsubame`) and the 4 traffic vehicles
(`traffic_kei`, `traffic_taxi`, `traffic_van`, `traffic_truck`) in `Game/Assets/InkDrift/Models/Cars/` are
**original procedural models made for this project**. This applies to every model whose `<id>_dims.json`
contains `"source": "original procedural model (Tools/cars/procedural), no third-party assets"`.
Blender Python scripts in `Tools/cars/procedural/` generate them. Each body is a parametric signed-distance
field built from hand-written profile curves. Surface nets turn it into a mesh, and the wheels are built
from lathe and loft geometry. No third-party models, meshes, textures, photos, scans or blueprints are
part of these assets.

The cars are fictional look-alikes. They borrow the overall proportions and silhouettes of real 2010s/2020s
Japanese cars, using public dimensions such as length, width, height and wheelbase. They carry **no
manufacturer names, badges, logos or brand text**. The roof sign on the taxi says only the generic word "TAXI".

| ID | Display name | Proportions inspired by |
|----|--------------|-------------------------|
| hachi | HACHI GR8 | 2020s 2+2 boxer coupe (GR86 / BRZ class) |
| kaiju | KAIJU SPR-X | 2020s straight-six FR coupe (GR Supra A90 class) |
| zenkai | ZENKAI Z | 2020s V6 fastback coupe (Z RZ34 class) |
| raijin | RAIJIN BX-R | 2020s AWD sports sedan (WRX VB class) |
| tsubame | TSUBAME RS | 2010s/20s roadster with soft top (MX-5 ND class) |
| traffic_kei / taxi / van / truck | traffic | kei pickup, tall Tokyo taxi MPV, one-box delivery van, 2 t cab-over box truck |

Number plates, livery decals and the windshield and taxi banners come from the repo's own generators and
artwork (`Tools/cars/cartex.py`, `Game/Assets/InkDrift/Art/Decals/`). Their text uses the repo's OFL fonts
(Noto Sans JP, Dela Gothic One; SIL Open Font License 1.1).

### Generators

| Script | Purpose |
|--------|---------|
| `Tools/cars/procedural/build.py` | entry point: `blender -b -P build.py -- <id>`. Body, wheels, kit, plates, decals, FBX, dims JSON, previews |
| `Tools/cars/procedural/specs/<id>.py` | per-vehicle parameters: profiles, plan and sections, greenhouse, stamps (lights, grilles, seams, vents) |
| `Tools/cars/procedural/body.py`, `sdf.py` | parametric SDF car body: hull, greenhouse, arches, stamps and solids, material regions |
| `Tools/cars/procedural/mesher.py`, `sdfmesh.py`, `cutmesh.py` | narrow-band sampling, surface nets, projection, exact material-border cuts |
| `Tools/cars/procedural/wheels.py` | tyres, multi-spoke rims (5 designs plus a steel wheel), brake discs, calipers |
| `Tools/cars/procedural/build_all.sh` | rebuilds everything, the contact sheet and runs `Tools/cars/verify_cars.py` |

Reference photos from Wikimedia Commons were only looked at locally to judge proportions while the
parameters were tuned. They are not stored in the repo or used in any asset.
