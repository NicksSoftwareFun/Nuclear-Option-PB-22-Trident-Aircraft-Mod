"""Pose the PB-22 detail model by rotating its hinge empties.
apply_pose(sweep=deg 0..45, gear=0 down..1 up, flap=0..1, slat=0..1, spoiler=0..1, elev=deg, rudder=deg, bay=0..1,
           doors=0 closed..1 open; default follows the gear)
Hinge empties carry their rest orientation in ['rest_q']; every pose is rest @ rotation about local X
(local Z for the wing sweep), so poses never accumulate.
CLI: python3 pb22_pose.py <in.blend> <out.blend> key=value ..."""
import bpy, math, sys
from mathutils import Vector, Quaternion, Matrix

FLAP_DEG, SLAT_DEG, SPOILER_DEG = 25.0, 20.0, 45.0
MAIN_FOLD, NOSE_FOLD = 90.0, 95.0
BRACE_SWING = 48.9      # upper side-brace link travel (deg), linear in the fold like the game's foldAngles

def _set(name, axis, deg):
    o = bpy.data.objects.get(name)
    if o is None: return
    rest = Quaternion(o['rest_q']) if 'rest_q' in o else Quaternion()
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = rest @ Quaternion(axis, math.radians(deg))

def apply_pose(sweep=0.0, gear=0.0, flap=0.0, slat=0.0, spoiler=0.0, elev=0.0, rudder=0.0, bay=0.0, doors=None,
               roll=0.0, spoiler_l=None, spoiler_r=None, steer=0.0, bogie=0.0, ab=0.0):
    X, Z = Vector((1, 0, 0)), Vector((0, 0, 1))
    for side, s in (('R', 1), ('L', -1)):
        _set(f'wingHinge_{side}b', Z, -s * sweep)
        _set(f'flapHinge_{side}2', X, FLAP_DEG * flap)
        _set(f'slatHinge_{side}2', X, -SLAT_DEG * slat)
        _set(f'slat2Hinge_{side}2', X, -SLAT_DEG * slat)
        sp = {'L': spoiler_l, 'R': spoiler_r}[side]
        _set(f'spoilerHinge_{side}2', X, -SPOILER_DEG * (spoiler if sp is None else sp))
        _set(f'elevatorHinge_{side}2', X, elev + s * roll)     # tailerons: roll is differential
        _set(f'bogey_{side}', X, bogie)
        _set(f'gearHinge_{side}', X, -s * MAIN_FOLD * gear)                 # main gear swings outboard and up
        bu = bpy.data.objects.get(f'braceU_{side}')
        if bu is not None:
            bu.rotation_mode = 'QUATERNION'; bu.rotation_quaternion = Quaternion(Vector((0, 1, 0)), math.radians(s * BRACE_SWING * gear))
        door = (1.0 - gear) if doors is None else doors
        _set(f'gearDoorHinge_{side}O2', X, -s * 90.0 * door)               # bi-fold main door: outer panel down,
        _set(f'gearDoorHinge_{side}I2', X, s * 180.0 * door)               # inner panel folds back against it
        _set(f'gearDoorHinge_F{side}2', X, -s * 90.0 * door)
        for fr in ('F', 'R'):
            _set(f'bayDoorHinge_{fr}{side}2', X, -s * 90.0 * bay)
    _set('rudderHinge_L2', X, rudder)
    _set('gearhinge_F', X, -NOSE_FOLD * gear)
    u = bpy.data.objects.get('gear_unsprung_F')
    if u is not None and 'steer_axis' in u:
        rest = Quaternion(u['rest_q']) if 'rest_q' in u else Quaternion()
        u.rotation_mode = 'QUATERNION'; u.rotation_quaternion = Quaternion(Vector(u['steer_axis']), math.radians(steer)) @ rest
    for o in bpy.data.objects:
        if o.name.startswith('afterburner') and o.name.endswith('_proxy'): o.hide_render = ab < 0.5
    bpy.context.view_layer.update()
    # LookAt parts, as the game aims them (local +Y here = Unity +Z, world up = Blender +Z)
    for side in ('R', 'L'):
        for nm, tg in ((f'braceL_{side}', f'braceKnee_{side}'), (f'actCyl_{side}', f'actTgtRod_{side}'), (f'actRod_{side}', f'actTgtAnchor_{side}')):
            o, t = bpy.data.objects.get(nm), bpy.data.objects.get(tg)
            if o is None or t is None: continue
            P0 = o.matrix_world.translation.copy(); dv = t.matrix_world.translation - P0
            if dv.length < 1e-6: continue
            o.matrix_world = Matrix.Translation(P0) @ dv.to_track_quat('Y', 'Z').to_matrix().to_4x4()
            bpy.context.view_layer.update()
    bpy.context.view_layer.update()

if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    src, dst = args[0], args[1]
    kw = {k: float(v) for k, v in (a.split('=') for a in args[2:])}
    bpy.ops.wm.open_mainfile(filepath=src)
    apply_pose(**kw)
    bpy.ops.wm.save_as_mainfile(filepath=dst)
    print('posed', dst, kw)
