st.subheader("Download")
    col_d1, col_d2, col_d3 = st.columns(3)

    with col_d1:
        stl = mesh.export(file_type="stl")
        st.download_button("⬇️ STL (mesh)", stl,
                           file_name=f"{model_name}.stl",
                           mime="model/stl",
                           use_container_width=True)

    with col_d2:
        try:
            from ifc_export import mesh_to_ifc_bytes
            ifc_bytes = mesh_to_ifc_bytes(
                mesh,
                equipment_name=f"Pump {model_name}",
                ifc_class="IfcPump",
                predefined_type="CIRCULATOR",
                model_number=model_name,
                properties={
                    "Nominal_HP": float(row["hp"]) if row["hp"] else None,
                    "Voltage_V":  int(row["voltage"]) if row["voltage"] else None,
                    "RPM":        int(row["rpm"]) if row["rpm"] else None,
                    "Length_A_mm":  float(A),
                    "Height_B_mm":  float(B),
                    "MotorLen_C_mm": float(C),
                    "MotorDia_D_mm": float(D),
                    "FlangeOD_E_mm": float(E),
                    "FlangeNominal_in": float(flange_in),
                },
            )
            st.download_button("⬇️ IFC (BIM — Revit)", ifc_bytes,
                               file_name=f"Pump_{model_name}.ifc",
                               mime="application/x-step",
                               use_container_width=True)
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
                    "HP": row["hp"],
                    "Voltage_V": row["voltage"],
                    "RPM": row["rpm"],
                    "Length_A_mm": A,
                    "Height_B_mm": B,
                    "MotorLen_C_mm": C,
                    "MotorDia_D_mm": D,
                    "FlangeOD_E_mm": E,
                },
            )
            st.download_button("⬇️ DXF (AutoCAD/Civil 3D)", dxf_bytes,
                               file_name=f"Pump_{model_name}.dxf",
                               mime="image/vnd.dxf",
                               use_container_width=True)
        except Exception as e:
            st.error(f"DXF failed: {e}")

    st.caption(
        "💡 To get a native **.dwg**: open the .dxf in AutoCAD → **File → Save As → AutoCAD Drawing (.dwg)**. "
        "Takes 3 seconds. True binary .dwg export from cloud requires Autodesk Platform Services (roadmap)."
    )
