"""
app.py — Universal Cutsheet → 3D CAD platform.

Features:
  * Auto-detects Bell & Gossett pumps or Trane CLCA AHUs from any PDF
  * Renders a parametric 3D model in-browser (Plotly)
  * Downloads: STL (mesh), IFC (BIM/Revit), DXF (AutoCAD/Civil 3D)

Built by Arnab Mondal, CDM Smith, Bangalore.
"""

import io
import streamlit as st
import plotly.graph_objects as go

from extractor import (
    detect_and_extract,
    pumps_to_df,
    ahus_to_df,
    get_section_length,
    AHU_SECTION_CATALOG,
)
from geometry import build_pump, build_ahu, mesh_to_plotly


# ============================================================
#  Page config + header
# ============================================================

st.set_page_config(
    page_title="Cutsheet → 3D CAD",
    page_icon="🔧",
    layout="wide",
)

st.title("🔧 Cutsheet → 3D CAD  •  MVP v3")
st.caption(
    "Upload any supported equipment cutsheet → extract specs → generate parametric 3D → "
    "download STL, IFC, or DXF."
)


# ============================================================
#  Sidebar
# ============================================================

with st.sidebar:
    st.header("Upload cutsheet")
    up = st.file_uploader("PDF", type=["pdf"])
    st.markdown("---")
    st.markdown(
        "**Currently supported:**\n"
        "- 🔵 Bell & Gossett Series PL (pumps)\n"
        "- 🟢 Trane CLCA Series (AHUs)\n\n"
        "**Export formats:**\n"
        "- STL — 3D print / viewers\n"
        "- IFC — Revit / BIM tools\n"
        "- DXF — AutoCAD / Civil 3D\n"
    )
    st.markdown("---")
    st.caption("Built by Arnab Mondal · CDM Smith BGA")


# ============================================================
#  Guard — need a file
# ============================================================

if not up:
    st.info("👈 Upload a PDF cutsheet in the sidebar to begin.")
    st.stop()


# ============================================================
#  Extract + detect
# ============================================================

with st.spinner("Reading PDF and detecting equipment type…"):
    pdf_stream = io.BytesIO(up.read())
    eq_type, items = detect_and_extract(pdf_stream)

if eq_type == "unknown" or not items:
    st.error(
        "❌ Could not recognize this cutsheet format. "
        "Currently supported: Bell & Gossett PL pumps, Trane CLCA AHUs."
    )
    st.stop()

badge = {"pump": "🔵 PUMP detected", "ahu": "🟢 AHU detected"}[eq_type]
st.success(f"{badge} — {len(items)} model(s) extracted.")


# ============================================================
#  PUMP flow
# ============================================================

if eq_type == "pump":
    df = pumps_to_df(items)
    st.subheader("Extracted pump specs")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Generate 3D pump")
    c1, c2 = st.columns([1, 3])

    with c1:
        model_name = st.selectbox("Model", df["model"].tolist())
        row = df[df["model"] == model_name].iloc[0]

        A = st.number_input("A – Length (mm)",   value=float(row["A_mm"] or 220))
        B = st.number_input("B – Height (mm)",   value=float(row["B_mm"] or 160))
        C = st.number_input("C – Motor L (mm)",  value=float(row["C_mm"] or 180))
        D = st.number_input("D – Motor Ø (mm)",  value=float(row["D_mm"] or 105))
        E = st.number_input("E – Flange Ø (mm)", value=float(row["E_mm"] or 110))
        flange_in = st.selectbox(
            "Flange nominal (in)", [0.75, 1.0, 1.25, 1.5, 2.0, 3.0], index=1
        )

        gen = st.button("🛠️ Generate 3D", type="primary", use_container_width=True)

    with c2:
        if gen or "pump_mesh" not in st.session_state:
            st.session_state["pump_mesh"] = build_pump(A, B, C, D, E, flange_in)

        mesh = st.session_state["pump_mesh"]
        fig = go.Figure(data=[mesh_to_plotly(mesh, color="#C0392B")])
        fig.update_layout(
            scene=dict(
                aspectmode="data",
                xaxis=dict(title="X (mm)"),
                yaxis=dict(title="Y (mm)"),
                zaxis=dict(title="Z (mm)"),
                camera=dict(eye=dict(x=1.4, y=1.4, z=0.9)),
            ),
            margin=dict(l=0, r=0, t=0, b=0),
            height=640,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---------- Downloads ----------
    st.subheader("Download")
    col_d1, col_d2, col_d3 = st.columns(3)

    with col_d1:
        stl = mesh.export(file_type="stl")
        st.download_button(
            "⬇️ STL (mesh)",
            stl,
            file_name=f"Pump_{model_name}.stl",
            mime="model/stl",
            use_container_width=True,
        )

    with col_d2:
        try:
            from ifc_export import mesh_to_ifc_bytes
            ifc_bytes = mesh_to_ifc_bytes(
                mesh,
                equipment_name=f"Pump {model_name}",
                ifc_class="IfcPump",
                predefined_type="CIRCULATOR",
                manufacturer="Bell & Gossett",
                model_number=model_name,
                properties={
                    "Nominal_HP":       float(row["hp"]) if row["hp"] else None,
                    "Voltage_V":        int(row["voltage"]) if row["voltage"] else None,
                    "RPM":              int(row["rpm"]) if row["rpm"] else None,
                    "Length_A_mm":      float(A),
                    "Height_B_mm":      float(B),
                    "MotorLen_C_mm":    float(C),
                    "MotorDia_D_mm":    float(D),
                    "FlangeOD_E_mm":    float(E),
                    "FlangeNominal_in": float(flange_in),
                },
            )
            st.download_button(
                "⬇️ IFC (BIM — Revit)",
                ifc_bytes,
                file_name=f"Pump_{model_name}.ifc",
                mime="application/x-step",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"IFC failed: {e}")

    with col_d3:
        try:
            from dxf_export import mesh_to_dxf_bytes
            dxf_bytes = mesh_to_dxf_bytes(
                mesh,
                equipment_name=f"Pump {model_name}",
                manufacturer="Bell & Gossett",
                model_number=model_name,
                properties={
                    "HP":              row["hp"],
                    "Voltage_V":       row["voltage"],
                    "RPM":             row["rpm"],
                    "Length_A_mm":     A,
                    "Height_B_mm":     B,
                    "MotorLen_C_mm":   C,
                    "MotorDia_D_mm":   D,
                    "FlangeOD_E_mm":   E,
                },
            )
            st.download_button(
                "⬇️ DXF (AutoCAD/Civil 3D)",
                dxf_bytes,
                file_name=f"Pump_{model_name}.dxf",
                mime="image/vnd.dxf",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"DXF failed: {e}")

    st.caption(
        "💡 To get a native **.dwg**: open the .dxf in AutoCAD → "
        "**File → Save As → AutoCAD Drawing (.dwg)** (3 seconds). "
        "Direct .dwg from the cloud requires Autodesk Platform Services (roadmap)."
    )


# ============================================================
#  AHU flow
# ============================================================

elif eq_type == "ahu":
    df = ahus_to_df(items)
    st.subheader("Extracted AHU specs (Trane CLCA)")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Configure AHU")
    c1, c2 = st.columns([1, 3])

    with c1:
        model_name = st.selectbox("Model size", df["model"].tolist())
        row = df[df["model"] == model_name].iloc[0]

        casing = st.radio("Casing thickness", ["25 mm", "50 mm"], horizontal=True)
        if casing == "25 mm":
            W_default = float(row["width_25mm"])
            H_default = float(row["height_25mm"])
        else:
            W_default = float(row["width_50mm"])
            H_default = float(row["height_50mm"])

        W = st.number_input("Width (mm)",  value=W_default)
        H = st.number_input("Height (mm)", value=H_default)

        st.markdown("**Sections (in air-flow order)**")
        selected_keys = []
        for key, label, default in AHU_SECTION_CATALOG:
            if st.checkbox(label, value=default, key=f"sec_{key}"):
                selected_keys.append((key, label))

        section_triples = [
            (k, lbl, get_section_length(k, model_name)) for (k, lbl) in selected_keys
        ]
        total_L = sum(s[2] for s in section_triples)
        st.info(
            f"**Total unit length:** {total_L:,.0f} mm  ({total_L/1000:.2f} m)"
        )

        gen = st.button("🛠️ Generate 3D", type="primary", use_container_width=True)

    with c2:
        if gen or "ahu_mesh" not in st.session_state:
            if not section_triples:
                st.warning("Select at least one section.")
                st.stop()
            st.session_state["ahu_mesh"] = build_ahu(W, H, section_triples)
            st.session_state["ahu_sections"] = section_triples

        mesh = st.session_state["ahu_mesh"]
        fig = go.Figure(data=[mesh_to_plotly(mesh, color="#BAC0C6")])
        fig.update_layout(
            scene=dict(
                aspectmode="data",
                xaxis=dict(title="Length (mm)"),
                yaxis=dict(title="Width (mm)"),
                zaxis=dict(title="Height (mm)"),
                camera=dict(eye=dict(x=1.6, y=-1.3, z=0.9)),
            ),
            margin=dict(l=0, r=0, t=0, b=0),
            height=640,
        )
        st.plotly_chart(fig, use_container_width=True)

        if "ahu_sections" in st.session_state:
            st.markdown("**Section breakdown**")
            secs = st.session_state["ahu_sections"]
            secs_df = [
                {"#": i + 1, "Section": s[1], "Length (mm)": s[2]}
                for i, s in enumerate(secs)
            ]
            st.dataframe(secs_df, use_container_width=True, hide_index=True)

    # ---------- Downloads ----------
    st.subheader("Download")
    col_d1, col_d2, col_d3 = st.columns(3)

    with col_d1:
        stl = mesh.export(file_type="stl")
        st.download_button(
            "⬇️ STL (mesh)",
            stl,
            file_name=f"AHU_CLCA-{model_name}.stl",
            mime="model/stl",
            use_container_width=True,
        )

    with col_d2:
        try:
            from ifc_export import mesh_to_ifc_bytes
            ifc_bytes = mesh_to_ifc_bytes(
                mesh,
                equipment_name=f"AHU CLCA-{model_name}",
                ifc_class="IfcUnitaryEquipment",
                predefined_type="AIRHANDLER",
                manufacturer="Trane",
                model_number=f"CLCA-{model_name}",
                properties={
                    "NominalAirflow_CMH": float(row["nominal_airflow_cmh"]),
                    "CoilFaceArea_m2":    float(row["coil_face_area_m2"]),
                    "Casing_mm":          25 if casing == "25 mm" else 50,
                    "Width_mm":           float(W),
                    "Height_mm":          float(H),
                    "TotalLength_mm":     float(total_L),
                    "SectionCount":       len(section_triples),
                    "Sections":           ", ".join(s[1] for s in section_triples),
                },
            )
            st.download_button(
                "⬇️ IFC (BIM — Revit)",
                ifc_bytes,
                file_name=f"AHU_CLCA-{model_name}.ifc",
                mime="application/x-step",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"IFC failed: {e}")

    with col_d3:
        try:
            from dxf_export import mesh_to_dxf_bytes
            dxf_bytes = mesh_to_dxf_bytes(
                mesh,
                equipment_name=f"AHU CLCA-{model_name}",
                manufacturer="Trane",
                model_number=f"CLCA-{model_name}",
                properties={
                    "NominalAirflow_CMH": row["nominal_airflow_cmh"],
                    "CoilFaceArea_m2":    row["coil_face_area_m2"],
                    "Casing_mm":          25 if casing == "25 mm" else 50,
                    "Width_mm":           W,
                    "Height_mm":          H,
                    "TotalLength_mm":     total_L,
                    "SectionCount":       len(section_triples),
                },
            )
            st.download_button(
                "⬇️ DXF (AutoCAD/Civil 3D)",
                dxf_bytes,
                file_name=f"AHU_CLCA-{model_name}.dxf",
                mime="image/vnd.dxf",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"DXF failed: {e}")

    st.caption(
        "💡 To get a native **.dwg**: open the .dxf in AutoCAD → "
        "**File → Save As → AutoCAD Drawing (.dwg)** (3 seconds). "
        "Direct .dwg from the cloud requires Autodesk Platform Services (roadmap)."
    )


# ============================================================
#  Footer roadmap note
# ============================================================

st.markdown("---")
st.caption(
    "**Roadmap** → STEP export (pythonocc-core) · native .rfa & .dwg via Autodesk APS Design Automation · "
    "MEP connectors in IFC · more equipment templates (chillers, packaged units, tanks) · "
    "auto-add to CDMS Revit family library."
)
`
