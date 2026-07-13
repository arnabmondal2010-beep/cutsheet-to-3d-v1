"""High-quality parametric equipment geometry.
All dimensions are millimetres. Public API remains compatible with v1.
"""
import numpy as np
import trimesh

QUALITY = {
    "coordination": dict(radial=32, sphere=2, fins=7),
    "standard": dict(radial=64, sphere=3, fins=11),
    "presentation": dict(radial=96, sphere=4, fins=15),
}


def _q(level):
    return QUALITY.get(str(level).lower(), QUALITY["standard"])


def _cyl(r, h, axis="z", sections=64, pos=(0, 0, 0)):
    m = trimesh.creation.cylinder(radius=max(float(r), .5), height=max(float(h), .5), sections=sections)
    if axis == "x":
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    elif axis == "y":
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    m.apply_translation(pos)
    return m


def _box(size, pos=(0, 0, 0)):
    m = trimesh.creation.box(extents=np.maximum(np.asarray(size, dtype=float), .5))
    m.apply_translation(pos)
    return m


def _sphere(radius, scale=(1, 1, 1), pos=(0, 0, 0), subdivisions=3):
    m = trimesh.creation.icosphere(subdivisions=subdivisions, radius=max(float(radius), .5))
    m.apply_scale(scale)
    m.apply_translation(pos)
    return m


def _finish(parts, name, metadata=None):
    mesh = trimesh.util.concatenate(parts)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices(digits_vertex=5)
    try:
        mesh.update_faces(mesh.unique_faces())
    except Exception:
        pass
    try:
        mesh.fix_normals()
    except Exception:
        pass
    mesh.metadata.update({"name": name, "units": "mm", **(metadata or {})})
    return mesh


def build_pump(A, B, C, D, E, flange_nom_in=1.0, quality="standard"):
    """Detailed conceptual vertical inline circulator.

    A-E remain mapped exactly as in the v1 UI, so existing extracted data and
    exports keep working. Geometry is intentionally non-fabrication-grade.
    """
    A, B, C, D, E = map(float, (A, B, C, D, E))
    cfg = _q(quality); sec = cfg["radial"]
    parts = []

    overall_len = max(A, 120)
    flange_od = max(E, flange_nom_in * 25.4 * 1.75)
    bore_d = max(flange_nom_in * 25.4, flange_od * .34)
    flange_t = np.clip(flange_od * .13, 9, 24)
    neck_len = max((overall_len - flange_od * .92) / 2, 16)
    casing_r = min(flange_od * .52, overall_len * .27)

    # In-line waterway, necks, raised-face flanges and bolt heads.
    parts.append(_cyl(bore_d * .58, overall_len - 2 * flange_t, "x", sec))
    for sign in (-1, 1):
        x_neck = sign * (overall_len / 2 - flange_t - neck_len / 2)
        parts.append(_cyl(max(bore_d * .66, casing_r * .46), neck_len, "x", sec, (x_neck, 0, 0)))
        x_flange = sign * (overall_len / 2 - flange_t / 2)
        parts.append(_cyl(flange_od / 2, flange_t, "x", sec, (x_flange, 0, 0)))
        parts.append(_cyl(flange_od * .39, flange_t * .18, "x", sec, (sign * overall_len / 2, 0, 0)))
        bolt_count = 4 if flange_nom_in >= 1.75 else 2
        for k in range(bolt_count):
            a = (2 * np.pi * k / bolt_count) + np.pi / 4
            y, z = np.cos(a) * flange_od * .34, np.sin(a) * flange_od * .34
            parts.append(_cyl(flange_od * .045, flange_t * 1.18, "x", 20, (x_flange, y, z)))

    # Layered volute gives a much more convincing cast housing silhouette.
    parts.append(_sphere(casing_r, (1.12, .92, .94), (0, 0, casing_r * .08), cfg["sphere"]))
    parts.append(_cyl(casing_r * .86, casing_r * .65, "z", sec, (0, 0, casing_r * .44)))
    parts.append(_cyl(casing_r * .72, casing_r * .15, "z", sec, (0, 0, casing_r * .79)))
    # Casting ribs around the upper body.
    for a in np.linspace(0, 2*np.pi, 8, endpoint=False):
        y, z = np.cos(a)*casing_r*.72, casing_r*.12 + np.sin(a)*casing_r*.58
        rib = _box((casing_r*.95, casing_r*.075, casing_r*.12), (0, y, z))
        rib.apply_transform(trimesh.transformations.rotation_matrix(a, [1, 0, 0], point=(0, 0, casing_r*.12)))
        parts.append(rib)

    # Mechanical seal bracket and motor pedestal.
    pedestal_z = casing_r * .86
    parts.append(_cyl(casing_r * .55, casing_r * .24, "z", sec, (0, 0, pedestal_z)))
    parts.append(_cyl(casing_r * .43, casing_r * .20, "z", sec, (0, 0, pedestal_z + casing_r*.20)))

    motor_d = max(D, flange_od * .72)
    motor_r = motor_d / 2
    # B is treated as target total height; C is used as the motor envelope hint.
    motor_h = max(min(C * .70, B - pedestal_z), motor_d * 1.05, 65)
    motor_bottom = pedestal_z + casing_r * .30
    motor_mid = motor_bottom + motor_h / 2
    parts.append(_cyl(motor_r * .93, motor_h, "z", sec, (0, 0, motor_mid)))
    parts.append(_cyl(motor_r, motor_d*.10, "z", sec, (0, 0, motor_bottom + motor_d*.05)))
    parts.append(_cyl(motor_r * .98, motor_d*.10, "z", sec, (0, 0, motor_bottom + motor_h - motor_d*.05)))

    # Fine cooling rings with two longitudinal strengthening bars.
    fin_start, fin_end = motor_bottom + motor_h*.14, motor_bottom + motor_h*.83
    for z in np.linspace(fin_start, fin_end, cfg["fins"]):
        parts.append(_cyl(motor_r*1.055, max(2.0, motor_h*.012), "z", sec, (0, 0, z)))
    for y in (-motor_r*.72, motor_r*.72):
        parts.append(_box((motor_r*.16, motor_r*.12, motor_h*.68), (0, y, motor_mid)))

    # Fan cover, central boss and guard ribs.
    top_z = motor_bottom + motor_h
    parts.append(_cyl(motor_r*1.02, motor_d*.16, "z", sec, (0, 0, top_z + motor_d*.08)))
    parts.append(_sphere(motor_r*.92, (1, 1, .28), (0, 0, top_z + motor_d*.16), cfg["sphere"]))
    parts.append(_cyl(motor_r*.18, motor_d*.12, "z", 32, (0, 0, top_z + motor_d*.19)))

    # Terminal box, lid, cable gland and nameplate.
    jb_w, jb_d, jb_h = motor_d*.68, motor_d*.42, motor_h*.29
    jb_y = motor_r + jb_d*.46
    jb_z = motor_mid + motor_h*.08
    parts.append(_box((jb_w, jb_d, jb_h), (0, jb_y, jb_z)))
    parts.append(_box((jb_w*1.06, jb_d*1.05, motor_d*.045), (0, jb_y, jb_z + jb_h/2)))
    parts.append(_cyl(motor_d*.065, motor_d*.18, "y", 24, (0, jb_y + jb_d*.68, jb_z)))
    parts.append(_box((motor_d*.52, motor_d*.025, motor_h*.23), (0, -motor_r*1.01, motor_mid)))

    return _finish(parts, "Series PL conceptual pump", {"quality": quality})


def build_ahu(width, height, sections, quality="standard"):
    """Detailed modular AHU suitable for BIM coordination and presentation."""
    W, H = float(width), float(height)
    lengths = [float(s[2]) for s in sections]
    L = sum(lengths)
    sec = _q(quality)["radial"]
    parts = []
    panel_gap = max(8.0, min(W, H) * .007)
    frame = max(35.0, min(W, H) * .035)

    # Slightly inset panels produce readable joints instead of one plain box.
    cursor = -L/2
    ranges = []
    for key, label, length in sections:
        length = float(length); cx = cursor + length/2
        ranges.append((cursor, cursor+length, key, label))
        parts.append(_box((max(length-panel_gap, 1), W-frame*.55, H-frame*.55), (cx, 0, 0)))
        cursor += length

    # Base rail and skids.
    base_h = max(90.0, H*.055)
    parts.append(_box((L+80, W+50, base_h), (0, 0, -H/2-base_h/2)))
    for y in (-W*.34, W*.34):
        parts.append(_box((L+140, max(65, W*.045), max(40, base_h*.42)), (0, y, -H/2-base_h-max(20,base_h*.21))))

    # Continuous structural frame.
    for y in (-W/2, W/2):
        for z in (-H/2, H/2):
            parts.append(_box((L+frame, frame, frame), (0, y, z)))
    cursor = -L/2
    boundaries = [cursor]
    for n in lengths: cursor += n; boundaries.append(cursor)
    for x in boundaries:
        for y in (-W/2, W/2): parts.append(_box((frame, frame, H), (x, y, 0)))
        for z in (-H/2, H/2): parts.append(_box((frame, W, frame), (x, 0, z)))

    door_keys = {"fan","access","cool_coil_6row","cool_coil_4row","cool_coil_8_12row","hot_coil_1_2row","hot_coil_4row","electric_heater","heat_wheel"}
    coil_keys = {"cool_coil_6row","cool_coil_4row","cool_coil_8_12row","hot_coil_1_2row","hot_coil_4row"}
    for x0, x1, key, label in ranges:
        cx, seg = (x0+x1)/2, x1-x0
        if key in door_keys and seg > 260:
            dw, dh = seg*.76, H*.72
            parts.append(_box((dw, 16, dh), (cx, -W/2-9, 0)))
            # Four-piece door frame, hinges and pull handle.
            for z in (-dh/2, dh/2): parts.append(_box((dw+24, 12, 18), (cx, -W/2-20, z)))
            for x in (cx-dw/2, cx+dw/2): parts.append(_box((18, 12, dh), (x, -W/2-20, 0)))
            for z in (-dh*.30, dh*.30): parts.append(_cyl(10, 42, "y", 20, (cx-dw*.46, -W/2-27, z)))
            parts.append(_box((16, 35, dh*.22), (cx+dw*.38, -W/2-33, 0)))
        if key in coil_keys:
            pipe_r = max(20, min(W,H)*.022)
            for z in (-H*.18, H*.18):
                parts.append(_cyl(pipe_r, max(120,W*.11), "y", sec, (cx, W/2+max(60,W*.055), z)))
                parts.append(_cyl(pipe_r*1.35, 18, "y", sec, (cx, W/2+max(120,W*.11), z)))

    # Intake/discharge louvres.
    for direction, key in ((-1, sections[0][0]), (1, sections[-1][0])):
        if key in {"mixing","prefilter","heat_wheel","supply","fan","access"}:
            x = direction*(L/2+9)
            for z in np.linspace(-H*.32, H*.32, 11):
                slat = _box((18, W*.70, max(12,H*.026)), (x, 0, z))
                slat.apply_transform(trimesh.transformations.rotation_matrix(np.deg2rad(direction*18), [0,1,0], point=(x,0,z)))
                parts.append(slat)

    # Roof lifting eyes.
    eye_r = max(14, frame*.30)
    for x in (-L*.43, L*.43):
        for y in (-W*.43, W*.43):
            parts.append(_cyl(eye_r, frame*.55, "z", 24, (x,y,H/2+frame*.28)))

    return _finish(parts, "Modular AHU", {"quality": quality, "sections": len(sections)})


def mesh_to_plotly(mesh, color="#B4B8BC"):
    import plotly.graph_objects as go
    v, f = mesh.vertices, mesh.faces
    return go.Mesh3d(x=v[:,0], y=v[:,1], z=v[:,2], i=f[:,0], j=f[:,1], k=f[:,2],
        color=color, opacity=1.0, flatshading=False,
        lighting=dict(ambient=.38, diffuse=.88, specular=.42, roughness=.36, fresnel=.18),
        lightposition=dict(x=2600, y=-2200, z=3200), hoverinfo="skip")
