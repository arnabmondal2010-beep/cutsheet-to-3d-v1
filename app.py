"""
app.py — Streamlit front-end for the Cutsheet → 3D CAD prototype.
Run locally:   streamlit run app.py
Deploy:        push to GitHub, connect to https://streamlit.io/cloud
"""

import io
import streamlit as st
import plotly.graph_objects as go

from extractor import extract_pumps, as_dataframe
from geometry import build_pump, mesh_to_plotly


st.set_page_config(page_title="Cutsheet → 3D CAD", page_icon="🔧", layout="wide")

st.title("🔧 Cutsheet → 3D CAD  •  MVP")
st.caption("Upload an equipment cutsheet (PDF). Extract specs → generate parametric 3D → download STL.")

# ---------- Sidebar ----------
with st.sidebar:
    st.header("1. Upload cutsheet")
    up = st.file_uploader("PDF", type=["pdf"])
    st.markdown("---")
    st.markdown(
        "**Supported today:** Bell & Gossett Series PL (inline circulators). "
        "Add more equipment templates in `geometry.py`."
    )

if not up:
    st.info("👈 Upload a PDF to begin. Try the sample **a-142g-series-pl.pdf**.")
    st.stop()

# ---------- Extraction ----------
with st.spinner("Reading tables from PDF…"):
    pumps = extract_pumps(io.BytesIO(up.read()))

if not pumps:
    st.error("No pump rows detected. This MVP is tuned for B&G PL-series tables.")
    st.stop()

df = as_dataframe(pumps)
st.subheader("2. Extracted specifications")
st.dataframe(df, use_container_width=True, hide_index=True)

# ---------- Model picker ----------
st.subheader("3. Generate 3D model")
c1, c2 = st.columns([1, 3])
with c1:
    model_name = st.selectbox("Choose a model", df["model"].tolist())
    row = df[df["model"] == model_name].iloc[0]

    # Allow live-tuning of dimensions
    A = st.number_input("A – Length (mm)",   value=float(row["A_mm"] or 220))
    B = st.number_input("B – Height (mm)",   value=float(row["B_mm"] or 160))
    C = st.number_input("C – Motor L (mm)",  value=float(row["C_mm"] or 180))
    D = st.number_input("D – Motor Ø (mm)",  value=float(row["D_mm"] or 105))
    E = st.number_input("E – Flange Ø (mm)", value=float(row["E_mm"] or 110))

    flange_in = st.selectbox("Flange nominal (in)", [0.75, 1.0, 1.25, 1.5, 2.0, 3.0],
                              index=1)

    generate = st.button("🛠️  Generate 3D", type="primary", use_container_width=True)

with c2:
    if generate or "mesh" not in st.session_state:
        st.session_state["mesh"] = build_pump(A, B, C, D, E, flange_in)

    mesh = st.session_state["mesh"]
    fig = go.Figure(data=[mesh_to_plotly(mesh)])
    fig.update_layout(
        scene=dict(
            aspectmode="data",
            xaxis=dict(title="X (mm)"), yaxis=dict(title="Y (mm)"),
            zaxis=dict(title="Z (mm)"),
            camera=dict(eye=dict(x=1.4, y=1.4, z=0.9)),
        ),
        margin=dict(l=0, r=0, t=0, b=0), height=600,
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- Download ----------
st.subheader("4. Download")
stl_bytes = mesh.export(file_type="stl")
st.download_button(
    "⬇️  Download STL",
    data=stl_bytes,
    file_name=f"{model_name}.stl",
    mime="model/stl",
    use_container_width=True,
)
obj_bytes = mesh.export(file_type="obj")
st.download_button(
    "⬇️  Download OBJ",
    data=obj_bytes.encode() if isinstance(obj_bytes, str) else obj_bytes,
    file_name=f"{model_name}.obj",
    mime="model/obj",
    use_container_width=True,
)

st.caption(
    "Roadmap → STEP export (pythonocc-core), Revit `.rfa` via Autodesk Design "
    "Automation API, MEP connectors, category auto-assign, community library."
)
