"""
geometry.py - Builds a parametric inline circulator from A/B/C/D/E dimensions.
"""

import numpy as np
import trimesh


def build_pump(A, B, C, D, E, flange_nom_in=1.0):
    """
    A = overall length flange-to-flange (mm)
    B = total height incl. motor         (mm)
    C = motor length                     (mm)
    D = motor diameter                   (mm)
    E = flange OD                        (mm)
    flange_nom_in = nominal pipe size (inches)
    """
    parts = []

    # Volute (horizontal pump body)
    volute_len = A * 0.55
    volute_dia = E * 1.05
    volute = trimesh.creation.cylinder(radius=volute_dia / 2, height=volute_len, sections=64)
    volute.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    parts.append(volute)

    # Suction & discharge pipe stubs
    stub_dia = E * 0.55
    stub_len = (A - volute_len) / 2
    for sign in (-1, 1):
        stub = trimesh.creation.cylinder(radius=stub_dia / 2, height=stub_len, sections=48)
        stub.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
        stub.apply_translation([sign * (volute_len / 2 + stub_len / 2), 0, 0])
        parts.append(stub)

    # End flanges (annular discs) + bolt bosses
    for sign in (-1, 1):
        flange = trimesh.creation.annulus(
            r_min=(flange_nom_in * 25.4) / 2,
            r_max=E / 2,
            height=E * 0.12,
            sections=64,
        )
        flange.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
        flange.apply_translation([sign * (A / 2), 0, 0])
        parts.append(flange)

        for k in range(4):
            angle = np.pi / 4 + k * np.pi / 2
            boss = trimesh.creation.cylinder(radius=E * 0.06, height=E * 0.14, sections=24)
            boss.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
            boss.apply_translation([
                sign * (A / 2),
                np.cos(angle) * E * 0.38,
                np.sin(angle) * E * 0.38,
            ])
            parts.append(boss)

    # Motor (vertical cylinder on top of volute)
    motor_h = B - volute_dia / 2
    motor = trimesh.creation.cylinder(radius=D / 2, height=motor_h, sections=64)
    motor.apply_translation([0, 0, volute_dia / 2 + motor_h / 2])
    parts.append(motor)

    # Junction box on side of motor
    jbox = trimesh.creation.box(extents=[D * 0.55, D * 0.35, motor_h * 0.35])
    jbox.apply_translation([0, D * 0.55, volute_dia / 2 + motor_h * 0.55])
    parts.append(jbox)

    # Motor end cap
    cap = trimesh.creation.cylinder(radius=D / 2 * 1.02, height=D * 0.08, sections=64)
    cap.apply_translation([0, 0, volute_dia / 2 + motor_h + D * 0.04])
    parts.append(cap)

    pump = trimesh.util.concatenate(parts)
    pump.merge_vertices()
    return pump


def mesh_to_plotly(mesh, color="#C0392B"):
    """Return a plotly Mesh3d object for Streamlit rendering."""
    import plotly.graph_objects as go
    v = mesh.vertices
    f = mesh.faces
    return go.Mesh3d(
        x=v[:, 0], y=v[:, 1], z=v[:, 2],
        i=f[:, 0], j=f[:, 1], k=f[:, 2],
        color=color,
        opacity=1.0,
        flatshading=True,
        lighting=dict(ambient=0.35, diffuse=0.9, specular=0.4, roughness=0.4, fresnel=0.2),
        lightposition=dict(x=1000, y=1000, z=2000),
    )
