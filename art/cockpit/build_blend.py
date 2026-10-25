"""Build the PB-22 cockpit model in Blender (from pb22_cockpit_model), optionally render previews and export FBX.
usage: python3 build_blend.py [render_eye|render_cut|render_rear|export] ..."""
import os
CK = os.path.dirname(os.path.abspath(__file__))  # scripts, ctx.obj and tex/ output live next to this file
import sys, os, math
sys.path.insert(0, CK)
import bpy, bmesh
from mathutils import Vector
import cklib
from cklib import U2B, reset, setup_render, cam, render, load_obj, clip
import pb22_cockpit_model as M

TEXDIR = os.path.join(CK, 'tex')

def material(name):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    if name == 'PB22_cockpit' and os.path.exists(TEXDIR + '/PB22_cockpit_b.png'):
        tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(TEXDIR + '/PB22_cockpit_b.png')
        nt.links.new(tx.outputs['Color'], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = 0.55
        if os.path.exists(TEXDIR + '/PB22_cockpit_n.png'):
            tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(TEXDIR + '/PB22_cockpit_n.png')
            tn.image.colorspace_settings.name = 'Non-Color'
            nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
        if os.path.exists(TEXDIR + '/PB22_cockpit_e.png'):
            te = nt.nodes.new('ShaderNodeTexImage'); te.image = bpy.data.images.load(TEXDIR + '/PB22_cockpit_e.png')
            nt.links.new(te.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 1.5
    elif name == 'PB22_cabin' and os.path.exists(TEXDIR + '/PB22_cabinwall_b.png'):
        uv = nt.nodes.new('ShaderNodeUVMap'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (4.1667, 4.1667, 1)
        nt.links.new(uv.outputs['UV'], mp.inputs['Vector'])
        tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(TEXDIR + '/PB22_cabinwall_b.png')
        nt.links.new(mp.outputs['Vector'], tx.inputs['Vector']); nt.links.new(tx.outputs['Color'], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = 0.75
    else:
        col = {'PB22_cockpit': (0.25, 0.27, 0.30, 1), 'PB22_screen': (0.02, 0.03, 0.04, 1), 'tacScreenDisplay': (0.03, 0.06, 0.05, 1),
               'CockpitWarningLight': (0.25, 0.02, 0.02, 1), 'aircraft_structure': (0.72, 0.73, 0.72, 1), 'Matte_black': (0.02, 0.02, 0.02, 1),
               'PB22_red': (0.6, 0.03, 0.02, 1)}.get(name, (0.5, 0.5, 0.5, 1))
        b.inputs['Base Color'].default_value = col; b.inputs['Roughness'].default_value = 0.5
        if name in ('PB22_screen', 'tacScreenDisplay'):
            b.inputs['Roughness'].default_value = 0.15
            if os.path.exists(TEXDIR + '/screen_%s.png' % name):
                tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(TEXDIR + '/screen_%s.png' % name)
                nt.links.new(tx.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 1.0
    return m

PIVOTS = {}
def build(parts=None, skip_simple=True, pivots=None):
    parts = parts or M.build_all()
    out = {}
    for name, P in parts.items():
        if skip_simple and 'simple' in name: continue
        me = bpy.data.meshes.new(name)
        V = [U2B(v) for v in P['v']]
        F = [list(reversed(f[0])) for f in P['f']]     # unity->blender flips handedness
        me.from_pydata(V, [], F)
        uvl = me.uv_layers.new(name='UVMap')
        mats = []
        for pi, f in enumerate(P['f']):
            if f[2] not in mats: mats.append(f[2])
        for mn in mats: me.materials.append(material(mn))
        li = 0
        for pi, poly in enumerate(me.polygons):
            f = P['f'][pi]
            poly.material_index = mats.index(f[2])
            uvs = list(reversed(f[1]))
            for k, loop in enumerate(poly.loop_indices):
                uvl.data[loop].uv = uvs[k]
        me.validate(); me.update()
        ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
        if pivots and name in pivots:      # object origin at its animation pivot
            pv = Vector(U2B(pivots[name]))
            for v in me.vertices: v.co -= pv
            ob.location = pv
        out[name] = ob
    return out

def context(raise_front=True, mock_windscreen=True):
    if os.environ.get('CTX045'):     # 0.4.5 cabin (new windscreen), no pilots
        ctx = load_obj(os.path.join(CK, 'ctx045.obj'))
        if os.environ.get('CABINWALL'):   # preview the wall liner box-projected at 1 tile = 0.60 m
            m = bpy.data.materials.new('cabinwall_preview'); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes['Principled BSDF']
            tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1/0.6, 1/0.6, 1/0.6)
            tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(TEXDIR + '/PB22_cabinwall_b.png'); tx.projection = 'BOX'; tx.projection_blend = 0.15
            nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], tx.inputs['Vector'])
            nt.links.new(tx.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = 0.6
            for o in ctx:
                if 'glass' not in o.name: o.data.materials.clear(); o.data.materials.append(m)
        return ctx
    ctx = load_obj(os.path.join(CK, 'ctx.obj'))
    for ob in ctx:
        if ob.name.startswith('pilot'):
            ys = [v.co.y for v in ob.data.vertices]; cy = sum(ys)/len(ys)
            if cy < 9.5:
                for v in ob.data.vertices:
                    x = v.co.x; sx = 0.34 if x > 0 else -0.34
                    v.co.x = sx - (x - sx); v.co.y = 8.75 - (v.co.y - 8.75)
            elif raise_front:
                for v in ob.data.vertices: v.co.z += M.RAISE
    if mock_windscreen:
        T = math.tan(math.radians(7.5))
        def below_arch(c):
            line = M.EYE[1] - (c.y - 10.301)*T
            if c.y > 11.85 and abs(c.x) < 0.82 and c.z > line - 0.01:
                return c.z < 0.355 if c.y < 12.12 else True
            return False
        clip([o for o in ctx if o.name.startswith(('cockpit__', 'nose__', 'fuselage_FF__')) and 'glass' not in o.name], lambda c: not below_arch(c))
    return ctx

def seats():
    # Medusa ejection seat proxies (bounds of the stock seat: centre (0,0.31,-0.03) extents (0.27,0.65,0.5) about the seat origin)
    import pb22_cockpit_model as MM
    MM.PARTS.clear()
    for x, z, face, dy in ((-0.34, 10.457, 1, M.RAISE), (0.34, 10.457, 1, M.RAISE), (-0.34, 8.708, -1, 0), (0.34, 8.708, -1, 0)):
        y0 = -0.323 + dy
        MM.boxw('seats', (x, y0 + 0.02, z + 0.02*face), (0.50, 0.12, 0.50), 'Matte_black')
        MM.boxw('seats', (x, y0 + 0.55, z - 0.27*face), (0.48, 1.0, 0.12), 'Matte_black')
    p = dict(MM.PARTS); return build(p)

def export(outdir):
    import json
    reset()
    parts = M.build_all()
    obs = build(parts, skip_simple=False, pivots=M.PIVOTS)
    for ob in obs.values():
        bm = bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.triangulate(bm, faces=bm.faces[:]); bm.to_mesh(ob.data); bm.free()
    os.makedirs(outdir, exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(outdir, 'PB22_cockpit.fbx'), use_selection=False, apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS', axis_forward='Z', axis_up='Y', bake_space_transform=True, object_types={'MESH'},
        mesh_smooth_type='FACE', use_mesh_modifiers=False, add_leaf_bones=False, use_tspace=True)
    t = math.radians(M.COL_TILT)
    info = {'pivots': {k: list(v) for k, v in M.PIVOTS.items()},
            'wheel_axis': [0.0, -math.sin(t), math.cos(t)],     # wheel turns about this (forward, along the wheel normal)
            'raise': M.RAISE, 'eye': list(M.EYE), 'tris': M.tri_count(),
            # gauge needles: pivot at the hub, turned about 'axis' (into the panel; + = clockwise seen by the pilot), 0 deg along 'up'
            'needles': {k: {'pivot': list(f.o), 'axis': [-f.n[0], -f.n[1], -f.n[2]], 'up': list(f.v)} for k, f in M.NEEDLES.items()}}
    json.dump(info, open(os.path.join(outdir, 'PB22_cockpit_layout.json'), 'w'), indent=1)
    with open(os.path.join(outdir, 'PB22_cockpit_needles.txt'), 'w') as f:   # read by PB22Cockpit.Build: name, pivot, axis, up
        for k, v in sorted(info['needles'].items()):
            f.write(' '.join([k] + ['%.6f' % x for x in v['pivot'] + v['axis'] + v['up']]) + '\n')
        for k, pv in sorted(M.MOVERS.items()):          # attitude balls and rudder pedals keep aircraft axes
            f.write(' '.join([k] + ['%.6f' % x for x in list(pv) + [0, 0, 1, 0, 1, 0]]) + '\n')
    print('exported', list(obs))

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'render_eye'
    if mode == 'export':
        export(sys.argv[2]); sys.exit(0)
    reset(); setup_render(1400, 900)
    ctx = context()
    obs = build(M.build_all())
    seats()
    skin = [o for o in ctx if not o.name.startswith('pilot')]
    if mode == 'render_eye':
        for o in ctx:
            if 'glass' in o.name: o.hide_render = True
            if o.name.startswith('pilot'):
                xs = [v.co.x for v in o.data.vertices]; ys = [v.co.y for v in o.data.vertices]
                if abs(sum(ys)/len(ys) - 10.3) < 0.6 and min(xs) < -0.05 and max(xs) < 0.05: o.hide_render = True
        e = M.EYE
        cam(U2B((e[0], e[1] + 0.02, e[2] - 0.02)), U2B((e[0] + 0.05, e[1] - 0.30, 11.3)), fov=78)
        render(sys.argv[2] if len(sys.argv) > 2 else os.path.join(CK, 'm_eye.png'))
    elif mode in ('render_cut', 'render_rear'):
        clip(skin, lambda c: c.z < 0.62)
        for o in ctx:
            if 'glass' in o.name or o.name.startswith('canopy') or o.name.startswith('hatch'): o.hide_render = True
        clip([o for o in skin if o.name.startswith(('cockpit__', 'fuselage_FF__', 'nose__'))], lambda c: c.x < 0.2 or c.z < -0.2)
        if mode == 'render_cut':
            cam(U2B((1.9, 1.5, 12.3)), U2B((0, -0.1, 10.6)), fov=55)
            render(sys.argv[2] if len(sys.argv) > 2 else os.path.join(CK, 'm_cut.png'))
        else:
            for o in ctx:
                if o.name.startswith('pilot'): o.hide_render = True
            for o in bpy.data.objects:
                if o.name.startswith('seats'): o.hide_render = True
            cam(U2B((0.0, 0.45, 9.45)), U2B((0.0, -0.05, 7.66)), fov=62)
            render(sys.argv[2] if len(sys.argv) > 2 else os.path.join(CK, 'm_rear.png'))
    elif mode in ('render_deck', 'render_ext'):
        if mode == 'render_deck':
            for o in ctx:
                if 'glass' in o.name or o.name.startswith('pilot'): o.hide_render = True
            cam(U2B((-0.25, 0.72, 10.6)), U2B((0.0, 0.12, 12.6)), fov=60) if not os.environ.get('DECKCAM') else cam(U2B((0.45, 0.55, 11.0)), U2B((0.55, 0.22, 11.6)), fov=55)
        else:
            cam(U2B((1.9, 1.0, 13.9)), U2B((0.0, 0.25, 11.8)), fov=40)
        render(sys.argv[2])
    elif mode == 'render_side':          # outside view through the side glass, like the in-game check (2026-10-25)
        if os.environ.get('NOGLASS'):
            for o in ctx:
                if 'glass' in o.name: o.hide_render = True
        cam(*( (U2B((3.4, 0.30, 11.4)), U2B((0.0, 0.0, 11.6))) if not os.environ.get('SIDECAM2') else (U2B((2.4, 1.3, 12.6)), U2B((0.0, 0.0, 12.0))) ), fov=45)
        render(sys.argv[2])
    elif mode == 'render_pedals':        # close look at the pedal channels from above the seat, seats and pilots hidden
        for o in ctx:
            if 'glass' in o.name or o.name.startswith('pilot'): o.hide_render = True
        for o in bpy.data.objects:
            if o.name.startswith('seats'): o.hide_render = True
        cam(U2B((-0.62, -0.22, 10.80)), U2B((-0.30, -0.62, 11.33)), fov=48); bpy.context.scene.view_settings.exposure = 1.6
        render(sys.argv[2])
    elif mode == 'render_legs':
        for o in ctx:
            if 'glass' in o.name or o.name.startswith('pilot'): o.hide_render = True
        cam(U2B((-0.10, 0.10, 10.30)), U2B((-0.32, -0.36, 11.15)), fov=75)
        render(sys.argv[2])
    elif mode == 'render_yoke':
        for o in ctx:
            if 'glass' in o.name or o.name.startswith('pilot'): o.hide_render = True
        cam(U2B((-0.12, 0.06, 10.62)), U2B((-0.34, -0.10, 10.98)), fov=55)
        render(sys.argv[2])
    elif mode == 'render_floor':
        for o in ctx:
            if 'glass' in o.name or o.name.startswith('pilot'): o.hide_render = True
        for o in bpy.data.objects:
            if o.name.startswith('seats'): o.hide_render = True
        cam(U2B((0.25, 0.25, 10.05)), U2B((-0.30, -0.72, 11.15)), fov=70)
        render(sys.argv[2])
    elif mode == 'render_panel':
        for o in ctx: o.hide_render = True
        cam(U2B((0.0, 0.35, 10.35)), U2B((0.0, 0.0, 11.25)), fov=62)
        render(sys.argv[2] if len(sys.argv) > 2 else os.path.join(CK, 'm_panel.png'))
