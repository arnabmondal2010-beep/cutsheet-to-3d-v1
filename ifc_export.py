"""
ifc_export.py — Convert a trimesh 3D model into a valid IFC4 file
that Revit, ArchiCAD, Tekla, Navisworks etc. can open natively.

Uses ifcopenshell (pure Python, no admin needed).
"""

import io
import time
import uuid
import tempfile
from datetime import datetime

import numpy as np
import ifcopenshell
import ifcopenshell.api


def _guid():
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


def _mesh_to_ifc_triangulated(model, mesh, context, placement):
    """Turn a trimesh mesh into an IfcTriangulatedFaceSet -> IfcProductDefinitionShape."""
    verts_flat = [tuple(float(x) for x in v) for v in mesh.vertices.tolist()]
    coord_list = model.create_entity(
        "IfcCartesianPointList3D",
        CoordList=verts_flat,
    )
    # IFC face indices are 1-based
    faces_1based = [[int(i) + 1 for i in f] for f in mesh.faces.tolist()]
    tri_set = model.create_entity(
        "IfcTriangulatedFaceSet",
        Coordinates=coord_list,
        Closed=True,
        CoordIndex=faces_1based,
    )
    rep = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="Tessellation",
        Items=[tri_set],
    )
    return model.create_entity(
        "IfcProductDefinitionShape",
        Representations=[rep],
    )


def _add_property_set(model, product, pset_name, properties, owner_history):
    """Attach a Pset with simple string/number properties to a product."""
    props = []
    for k, v in properties.items():
        if v is None:
            continue
        if isinstance(v, (int, float)):
            val = model.create_entity("IfcReal", float(v))
        else:
            val = model.create_entity("IfcText", str(v))
        props.append(model.create_entity(
            "IfcPropertySingleValue",
            Name=str(k),
            NominalValue=val,
        ))
    if not props:
        return
    pset = model.create_entity(
        "IfcPropertySet",
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        Name=pset_name,
        HasProperties=props,
    )
    model.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        RelatedObjects=[product],
        RelatingPropertyDefinition=pset,
    )


def mesh_to_ifc_bytes(
    mesh,
    equipment_name="Equipment",
    ifc_class="IfcFlowTerminal",
    predefined_type=None,
    manufacturer="CDM Smith Cutsheet-to-3D",
    model_number="",
    properties=None,
):
    """
    Convert a trimesh.Trimesh into an in-memory IFC4 file (bytes).

    ifc_class examples:
        Pumps  -> "IfcPump"
        AHUs   -> "IfcAirToAirHeatRecovery"  or  "IfcUnitaryEquipment"
        Chillers -> "IfcChiller"
    """
    properties = properties or {}
    model = ifcopenshell.api.run("project.create_file", version="IFC4")

    # --- Project / units / owner ---
    person = model.create_entity("IfcPerson", FamilyName="Arnab", GivenName="Mondal")
    org = model.create_entity("IfcOrganization", Name="CDM Smith")
    p_and_o = model.create_entity("IfcPersonAndOrganization",
                                  ThePerson=person, TheOrganization=org)
    app = model.create_entity("IfcApplication",
                              ApplicationDeveloper=org,
                              Version="1.0",
                              ApplicationFullName="Cutsheet-to-3D",
                              ApplicationIdentifier="C23D")
    owner_history = model.create_entity(
        "IfcOwnerHistory",
        OwningUser=p_and_o,
        OwningApplication=app,
        ChangeAction="ADDED",
        CreationDate=int(time.time()),
    )

    # Units (millimetres)
    length_unit = model.create_entity(
        "IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE",
    )
    area_unit = model.create_entity(
        "IfcSIUnit", UnitType="AREAUNIT", Prefix="MILLI", Name="SQUARE_METRE",
    )
    volume_unit = model.create_entity(
        "IfcSIUnit", UnitType="VOLUMEUNIT", Prefix="MILLI", Name="CUBIC_METRE",
    )
    plane_angle = model.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN")
    unit_assign = model.create_entity(
        "IfcUnitAssignment",
        Units=[length_unit, area_unit, volume_unit, plane_angle],
    )

    # World coordinate system
    origin = model.create_entity(
        "IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0)
    )
    zdir = model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    xdir = model.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
    world_placement = model.create_entity(
        "IfcAxis2Placement3D", Location=origin, Axis=zdir, RefDirection=xdir,
    )
    geom_context = model.create_entity(
        "IfcGeometricRepresentationContext",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=world_placement,
    )
    body_ctx = model.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=geom_context,
        TargetView="MODEL_VIEW",
    )

    project = model.create_entity(
        "IfcProject",
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        Name="Cutsheet-to-3D Export",
        RepresentationContexts=[geom_context],
        UnitsInContext=unit_assign,
    )

    # --- Spatial structure: Site -> Building -> Storey ---
    site_pl = model.create_entity("IfcLocalPlacement", RelativePlacement=world_placement)
    site = model.create_entity(
        "IfcSite", GlobalId=_guid(), OwnerHistory=owner_history,
        Name="Default Site", ObjectPlacement=site_pl, CompositionType="ELEMENT",
    )
    bldg_pl = model.create_entity("IfcLocalPlacement",
                                  PlacementRelTo=site_pl,
                                  RelativePlacement=world_placement)
    building = model.create_entity(
        "IfcBuilding", GlobalId=_guid(), OwnerHistory=owner_history,
        Name="Default Building", ObjectPlacement=bldg_pl, CompositionType="ELEMENT",
    )
    storey_pl = model.create_entity("IfcLocalPlacement",
                                    PlacementRelTo=bldg_pl,
                                    RelativePlacement=world_placement)
    storey = model.create_entity(
        "IfcBuildingStorey", GlobalId=_guid(), OwnerHistory=owner_history,
        Name="Level 1", ObjectPlacement=storey_pl, CompositionType="ELEMENT",
    )

    model.create_entity("IfcRelAggregates", GlobalId=_guid(),
                        OwnerHistory=owner_history,
                        RelatingObject=project, RelatedObjects=[site])
    model.create_entity("IfcRelAggregates", GlobalId=_guid(),
                        OwnerHistory=owner_history,
                        RelatingObject=site, RelatedObjects=[building])
    model.create_entity("IfcRelAggregates", GlobalId=_guid(),
                        OwnerHistory=owner_history,
                        RelatingObject=building, RelatedObjects=[storey])

    # --- The actual equipment product ---
    prod_pl = model.create_entity("IfcLocalPlacement",
                                  PlacementRelTo=storey_pl,
                                  RelativePlacement=world_placement)
    shape = _mesh_to_ifc_triangulated(model, mesh, body_ctx, prod_pl)

    product = model.create_entity(
        ifc_class,
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        Name=equipment_name,
        Description=f"Auto-generated from cutsheet by Cutsheet-to-3D",
        ObjectPlacement=prod_pl,
        Representation=shape,
    )
    if predefined_type and hasattr(product, "PredefinedType"):
        try:
            product.PredefinedType = predefined_type
        except Exception:
            pass

    # Contain product in storey
    model.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=_guid(), OwnerHistory=owner_history,
        RelatedElements=[product], RelatingStructure=storey,
    )

    # Identity Pset (Revit reads these as Type Parameters)
    identity_props = {
        "Manufacturer": manufacturer,
        "ModelReference": model_number or equipment_name,
        "GeneratedBy": "Cutsheet-to-3D (Arnab Mondal, CDM Smith)",
        "GeneratedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    _add_property_set(model, product, "Pset_ManufacturerTypeInformation",
                      identity_props, owner_history)

    # Custom Pset with any extracted specs
    if properties:
        _add_property_set(model, product, "Pset_CDMSmith_Cutsheet",
                          properties, owner_history)

    # Write to bytes via a temp file (ifcopenshell writes to disk)
    with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
        model.write(tmp.name)
        tmp.seek(0)
        with open(tmp.name, "rb") as fh:
            data = fh.read()
    return data
