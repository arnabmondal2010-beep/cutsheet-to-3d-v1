"""
app.py — Universal Cutsheet → 3D CAD platform.
Auto-detects equipment type from the uploaded PDF.
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


st.set_page_config(page_title="Cutsheet → 3D CAD", page_icon="🔧", layout="wide")

st.title("🔧 Cutsheet → 3D CAD  •  MVP v2")
st.caption("Upload any supported equipment cutsheet → extract specs → generate parametric 3D → download STL.")

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Upload cutsheet")
    up = st.file_uploader("PDF", type=["pdf"])
    st.markdown("---")
    st.markdown(
        "**Supported now:**\n"
        "- 🔵 Bell & Gossett Series PL (pumps)\n"
        "- 🟢 Trane CLCA Series (AHUs)\n\n"
        "More equipment templates coming soon."
    )

if not up:
    st.info("👈 Upload a PDF cutsheet to begin.")
    st.stop()

# ---------- Detect + extract ----------
with st.spinner("Reading PDF and detecting equipment type…"):
    pdf_stream = io.BytesIO(up.read())
    eq_type, items = detect_and_extract(pdf_stream)

if eq_type == "unknown" or not items:
    st.error("❌ Could not recognize this cutsheet format. Currently supported: Bell & Gossett PL pumps, Trane CLCA AHUs.")
    st.stop()

badge = {"pump": "🔵 PUMP detected", "ahu": "🟢 AHU detected"}[eq_type]
st.success(f"{badge} — {len(items)} model(s) extracted.")

# ============================================================
#  PUMP FLOW
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
        flange_in = st.selectbox("Flange nominal (in)", [0.75, 1.0, 1.25, 1.5, 2.0, 3.0], index=1)
        gen = st.button("🛠️ Generate 3D", type="primary", use_container_width=True)
    with c2:
        if gen or "pump_mesh" not in st.session_state:
            st.session_state["pump_mesh"] = build_pump(A, B, C, D, E, flange_in)
        mesh = st.session_state["pump_mesh"]
        fig = go.Figure(data=[mesh_to_plotly(mesh, color="#C0392B")])
        fig.update_layout(
            scene=dict(aspectmode="data",
                       xaxis=dict(title="X (mm)"),
                       yaxis=dict(title="Y (mm)"),
                       zaxis=dict(title="Z (mm)"),
                       camera=dict(eye=dict(x=1.4, y=1.4, z=0.9))),
            margin=dict(l=0, r=0, t=0, b=0), height=640,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Download")
    stl = mesh.export(file_type="stl")
    st.download_button("⬇️ Download STL", stl,
                       file_name=f"{model_name}.stl", mime="model/stl",
                       use_container_width=True)

# ============================================================
#  AHU FLOW
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

        # Build section triples with lengths
        section_triples = [
            (k, lbl, get_section_length(k, model_name)) for (k, lbl) in selected_keys
        ]
        total_L = sum(s[2] for s in section_triples)
        st.info(f"**Total unit length:** {total_L:,.0f} mm  ({total_L/1000:.2f} m)")

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
            scene=dict(aspectmode="data",
                       xaxis=dict(title="Length (mm)"),
                       yaxis=dict(title="Width (mm)"),
                       zaxis=dict(title="Height (mm)"),
                       camera=dict(eye=dict(x=1.6, y=-1.3, z=0.9))),
            margin=dict(l=0, r=0, t=0, b=0), height=640,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Section breakdown table
        if "ahu_sections" in st.session_state:
            st.markdown("**Section breakdown**")
            secs = st.session_state["ahu_sections"]
            secs_df = [{"#": i+1, "Section": s[1], "Length (mm)": s[2]}
                       for i, s in enumerate(secs)]
            st.dataframe(secs_df, use_container_width=True, hide_index=True)

    st.subheader("Download")
    stl = mesh.export(file_type="stl")
    st.download_button("⬇️ Download STL", stl,
                       file_name=f"AHU_{model_name}.stl", mime="model/stl",
                       use_container_width=True)

st.caption(
    "Roadmap → STEP export via pythonocc-core • Revit `.rfa` via Autodesk Design Automation • "
    "IFC export • more equipment templates (chillers, pumps, tanks, packaged units)."
)
