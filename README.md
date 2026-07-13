# Cutsheet to 3D CAD - v2 Geometry Upgrade

A browser-based Streamlit prototype that extracts equipment data from PDF cutsheets and generates conceptual 3D models for BIM coordination.

## Improvements in this version

- Rebuilt Series PL pump with layered volute casing, raised-face flanges, fasteners, casting ribs, seal pedestal, detailed motor, cooling fins, fan cover, terminal box, cable gland and nameplate.
- Rebuilt AHU with inset modular panels, readable section joints, structural frame, detailed access doors, hinges, handles, coil connections, louvres, skids and lifting points.
- Three geometry quality levels: coordination, standard and presentation.
- Automatic regeneration when any geometry input changes, avoiding stale previews and stale exports.
- Mesh cleanup, normal repair when available, millimetre metadata and compatibility with existing STL, IFC and DXF workflows.

## Deploy on Streamlit Community Cloud

1. Upload all repository files to GitHub.
2. Open Streamlit Community Cloud and create an app.
3. Select this repository, branch `main`, and entry point `app.py`.
4. Deploy and upload a supported PDF.

## Supported templates

- Bell & Gossett Series PL inline circulators
- Trane CLCA modular AHUs

## Important limitation

Generated models are conceptual BIM coordination geometry, not certified fabrication models. Check extracted dimensions against the manufacturer's certified drawing.
