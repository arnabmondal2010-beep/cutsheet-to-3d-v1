"""
geometry.py — Parametric 3D builders for equipment.
Currently supports:
  * build_pump(...)   Bell & Gossett Series PL inline circulator
  * build_ahu(...)    Trane CLCA-style flexible AHU
"""

import numpy as np
import trimesh

SEC_FINE = 96
SEC_MED  = 64
SEC_LOW  = 32


# ============================================================
#  PUMP  (improved smoothness + detail)
# ============================================================

def build_pump(A, B, C, D, E, flange_nom_in=1.0):
    parts = []

    # Volute body (main horizontal cylinder)
    volute_len = A * 0.50
    volute_dia = E * 1.15
    volute = trimesh.creation.cylinder(radius=volute_dia / 2, height=volute_len, sections=SEC_FINE)
    volute.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    parts.append(volute)

    # Impeller housing dome on top of volute
    dome_r = volute_dia * 0.55
    dome = trimesh.creation.icosphere(subdivisions=4, radius=dome_r)
    dome.apply_scale([1.0, 1.0, 0.55])
    dome.apply_translation([0, 0, volute_dia / 2 * 0.35])
    parts.append(dome)

    # Suction + discharge stubs
    stub_dia = E * 0.62
    stub_len = (A - volute_len) / 2
    for sign in (-1, 1):
        stub = trimesh.creation.cylinder(radius=stub_dia / 2, height=stub_len, sections=SEC_MED)
        stub.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
        stub.apply_translation([sign * (volute_len / 2 + stub_len / 2), 0, 0])
        parts.append(stub)

    # End flanges (annular) + bolt bosses
    for sign in (-1, 1):
        flange = trimesh.creation.annulus(
            r_min=(flange_nom_in * 25.4) / 2,
            r_max=E / 2,
            height=E * 0.14,
            sections=SEC_FINE,
        )
        flange.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
        flange.apply_translation([sign * (A / 2), 0, 0])
        parts.append(flange)

        for k in range(4):
            angle = np.pi / 4 + k * np.pi / 2
            boss = trimesh.creation.cylinder(radius=E * 0.06, height=E * 0.18, sections=SEC_LOW)
            boss.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
            boss.apply_translation([
                sign * (A / 2),
                np.cos(angle) * E * 0.36,
                np.sin(angle) * E * 0.36,
            ])
            parts.append(boss)

    # Motor housing (vertical)
    motor_h = B - volute_dia / 2 - dome_r * 0.3
    motor_r = D / 2
    motor_body_h = motor_h * 0.82
    motor_z_start = volute_dia / 2 + dome_r * 0.2
    motor = trimesh.creation.cylinder(radius=motor_r, height=motor_body_h, sections=SEC_FINE)
    motor.apply_translation([0, 0, motor_z_start + motor_body_h / 2])
    parts.append(motor)

    # Motor cooling fins (annular rings)
    n_fins = 9
    fin_zone_start = motor_z_start + motor_body_h * 0.1
    fin_zone_h = motor_body_h * 0.75
    fin_thk = fin_zone_h / n_fins * 0.45
    for i in range(n_fins):
        z = fin_zone_start + fin_zone_h * (i + 0.5) / n_fins
        fin = trimesh.creation.annulus(
            r_min=motor_r * 0.98,
            r_max=motor_r * 1.09,
            height=fin_thk,
            sections=SEC_FINE,
        )
        fin.apply_translation([0, 0, z])
        parts.append(fin)

    # Motor top end cap
    cap_z = motor_z_start + motor_body_h + D * 0.05
    cap = trimesh.creation.cylinder(radius=motor_r * 1.04, height=D * 0.10, sections=SEC_FINE)
    cap.apply_translation([0, 0, cap_z])
    parts.append(cap)

    # Small dome on top of cap
    top_dome = trimesh.creation.icosphere(subdivisions=3, radius=motor_r * 0.45)
    top_dome.apply_scale([1, 1, 0.5])
    top_dome.apply_translation([0, 0, cap_z + D * 0.05])
    parts.append(top_dome)

    # Nameplate (front of motor)
    nameplate = trimesh.creation.box(extents=[D * 0.55, D * 0.02, motor_h * 0.28])
    nameplate.apply_translation([0, -motor_r - D * 0.01, motor_z_start + motor_body_h * 0.55])
    parts.append(nameplate)

    # Junction box (electrical, back of motor)
    jbox_z = motor_z_start + motor_body_h * 0.55
    jbox = trimesh.creation.box(extents=[D * 0.50, D * 0.45, motor_h * 0.30])
    jbox.apply_translation([0, motor_r + D * 0.22, jbox_z])
    parts.append(jbox)

    # Conduit fitting from jbox
    conduit = trimesh.creation.cylinder(radius=D * 0.05, height=D * 0.18, sections=SEC_LOW)
    conduit.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    conduit.apply_translation([0, motor_r + D * 0.55, jbox_z + motor_h * 0.05])
    parts.append(conduit)

    pump = trimesh.util.concatenate(parts)
    pump.merge_vertices()
    return pump


# ============================================================
#  AHU  (Trane CLCA-style modular box)
# ============================================================

def build_ahu(width, height, sections):
    """
    width, height : external casing dimensions in mm
    sections      : list of tuples (key, friendly_name, length_mm)
    """
    parts = []
    total_length = sum(s[2] for s in sections)
    W, H, L = float(width), float(height), float(total_length)

    # ---------- Base frame (extended footprint) ----------
    base_h = 100.0
    base_extend = 30.0
    base = trimesh.creation.box(extents=[L + 2 * base_extend, W + 2 * base_extend, base_h])
    base.apply_translation([0, 0, -H / 2 - base_h / 2])
    parts.append(base)

    # Skids under base
    skid_h = 45.0
    skid_w = 70.0
    for ys in [-W / 2 + 120, W / 2 - 120]:
        skid = trimesh.creation.box(extents=[L + 2 * base_extend + 50, skid_w, skid_h])
        skid.apply_translation([0, ys, -H / 2 - base_h - skid_h / 2])
        parts.append(skid)

    # ---------- Main casing (single solid box) ----------
    casing = trimesh.creation.box(extents=[L, W, H])
    parts.append(casing)

    # ---------- Corner posts (aluminum extrusions, proud) ----------
    post = 55.0
    for xs in [-L / 2, L / 2]:
        for ys in [-W / 2, W / 2]:
            p = trimesh.creation.box(extents=[post, post, H + 20])
            p.apply_translation([xs, ys, 0])
            parts.append(p)

    # ---------- Horizontal top & bottom rails (front + back) ----------
    rail = 30.0
    for zs in [-H / 2 + rail / 2, H / 2 - rail / 2]:
        for ys in [-W / 2, W / 2]:
            r = trimesh.creation.box(extents=[L, rail * 1.3, rail])
            r.apply_translation([0, ys, zs])
            parts.append(r)

    # ---------- Section-joint ribs ----------
    rib = 18.0
    cursor = -L / 2
    section_x_ranges = []
    for i, (key, name, length) in enumerate(sections):
        section_x_ranges.append((cursor, cursor + float(length), key, name))
        cursor += float(length)
        if i < len(sections) - 1:
            for ys in [-W / 2, W / 2]:
                rb = trimesh.creation.box(extents=[rib, rib * 1.4, H])
                rb.apply_translation([cursor, ys, 0])
                parts.append(rb)
            top_rib = trimesh.creation.box(extents=[rib, W, rib * 1.4])
            top_rib.apply_translation([cursor, 0, H / 2])
            parts.append(top_rib)
            bot_rib = trimesh.creation.box(extents=[rib, W, rib * 1.4])
            bot_rib.apply_translation([cursor, 0, -H / 2])
            parts.append(bot_rib)

    # ---------- Access doors (front face) ----------
    door_keys = {
        "fan", "access", "cool_coil_6row", "cool_coil_4row",
        "cool_coil_8_12row", "hot_coil_1_2row", "hot_coil_4row",
        "electric_heater", "heat_wheel",
    }
    for (x0, x1, key, name) in section_x_ranges:
        if key not in door_keys:
            continue
        seg_L = x1 - x0
        if seg_L < 260:
            continue
        door_w = seg_L * 0.78
        door_h = H * 0.78
        door_cx = (x0 + x1) / 2
        door = trimesh.creation.box(extents=[door_w, 20, door_h])
        door.apply_translation([door_cx, -W / 2 - 10, 0])
        parts.append(door)

        # Door frame ribs (thin outline)
        for edge_off in [-door_h / 2 + 12, door_h / 2 - 12]:
            e = trimesh.creation.box(extents=[door_w + 20, 8, 12])
            e.apply_translation([door_cx, -W / 2 - 14, edge_off])
            parts.append(e)

        # Handle
        handle_x = door_cx + door_w * 0.35
        handle = trimesh.creation.cylinder(radius=14, height=45, sections=SEC_LOW)
        handle.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
        handle.apply_translation([handle_x, -W / 2 - 30, 0])
        parts.append(handle)

        # Hinges
        for hz in [-door_h * 0.35, door_h * 0.35]:
            hinge = trimesh.creation.cylinder(radius=10, height=35, sections=SEC_LOW)
            hinge.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
            hinge.apply_translation([door_cx - door_w * 0.45, -W / 2 - 22, hz])
            parts.append(hinge)

    # ---------- Damper louvers on end faces ----------
    louver_faces = []
    if sections:
        if sections[0][0] in ("mixing", "prefilter", "heat_wheel"):
            louver_faces.append(-1)
        if sections[-1][0] in ("supply", "fan", "access"):
            louver_faces.append(1)

    for direction in louver_faces:
        x_face = direction * L / 2
        n_slats = 9
        opening_h = H * 0.72
        opening_w = W * 0.72
        slat_h = opening_h / (n_slats * 1.6)
        for i in range(n_slats):
            z = -opening_h / 2 + (i + 0.5) * (opening_h / n_slats)
            slat = trimesh.creation.box(extents=[15, opening_w, slat_h])
            slat.apply_translation([x_face + direction * 8, 0, z])
            R = trimesh.transformations.rotation_matrix(
                np.deg2rad(20), [0, 1, 0],
                point=[x_face + direction * 8, 0, z],
            )
            slat.apply_transform(R)
            parts.append(slat)

    # ---------- Coil connection pipes ----------
    coil_keys = {"cool_coil_6row", "cool_coil_4row", "cool_coil_8_12row", "hot_coil_1_2row", "hot_coil_4row"}
    for (x0, x1, key, name) in section_x_ranges:
        if key not in coil_keys:
            continue
        pipe_r = 42.0
        pipe_len = 220.0
        pipe_x = (x0 + x1) / 2
        for z_off in [-H * 0.25, H * 0.25]:
            pipe = trimesh.creation.cylinder(radius=pipe_r, height=pipe_len, sections=SEC_MED)
            pipe.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
            pipe.apply_translation([pipe_x, W / 2 + pipe_len / 2, z_off])
            parts.append(pipe)
            flg = trimesh.creation.cylinder(radius=pipe_r * 1.6, height=18, sections=SEC_MED)
            flg.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
            flg.apply_translation([pipe_x, W / 2 + pipe_len, z_off])
            parts.append(flg)

    # ---------- Fan section extras ----------
    for (x0, x1, key, name) in section_x_ranges:
        if key != "fan":
            continue
        # Inspection lamp on top
        lamp = trimesh.creation.cylinder(radius=28, height=32, sections=SEC_LOW)
        lamp.apply_translation([(x0 + x1) / 2 + (x1 - x0) * 0.3, 0, H / 2 + 16])
        parts.append(lamp)
        # Control panel on side
        panel = trimesh.creation.box(extents=[(x1 - x0) * 0.35, 22, H * 0.35])
        panel.apply_translation([(x0 + x1) / 2 - (x1 - x0) * 0.2, W / 2 + 12, -H * 0.10])
        parts.append(panel)

    # ---------- Drain pan outlet (bottom near coil) ----------
    for (x0, x1, key, name) in section_x_ranges:
        if key not in coil_keys:
            continue
        drain = trimesh.creation.cylinder(radius=22, height=120, sections=SEC_LOW)
        drain.apply_translation([(x0 + x1) / 2 - 100, -W / 2 + 100, -H / 2 - 60])
        parts.append(drain)

    ahu = trimesh.util.concatenate(parts)
    ahu.merge_vertices()
    return ahu


# ============================================================
#  Plotly rendering (smooth shading!)
# ============================================================

def mesh_to_plotly(mesh, color="#B4B8BC"):
    import plotly.graph_objects as go
    v = mesh.vertices
    f = mesh.faces
    return go.Mesh3d(
        x=v[:, 0], y=v[:, 1], z=v[:, 2],
        i=f[:, 0], j=f[:, 1], k=f[:, 2],
        color=color,
        opacity=1.0,
        flatshading=False,   # smooth shading — the big visual upgrade!
        lighting=dict(ambient=0.45, diffuse=0.85, specular=0.55,
                      roughness=0.30, fresnel=0.30),
        lightposition=dict(x=2500, y=2500, z=3500),
    )
