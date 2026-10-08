"""Internal Python-root projection fixture; not a complete lineage generator."""

from pathlib import Path
from copy import deepcopy
import json
import sys

import svtypes
from svx.inheritance import (
    GENERATOR_ABI_VERSION, REQUIRED_RUNTIME_CAPABILITIES, SCHEMA_URI, SCHEMA_VERSION,
    EXTERNAL_FIELD_STORAGE_CAPABILITY,
    _manifest_sv_record_types, parse_manifest,
    _emit_sv_projection_factory,
    _emit_planned_python_root_sv_projection,
    _emit_python_root_artifacts, artifact_manifest,
)


ROOT_ID = "py://tests/integration/python_root/Root"
DERIVED_ID = "py://tests/integration/python_root/Derived"


def manifest_data():
    codec = svtypes.Int()
    binding = {"unified_type_name": svtypes.unified_type_name(codec),
               "svtypes": svtypes.type_spec_identity(svtypes.Int),
               "sv": "int", "sv_packer": "svtypes_pkg::int_packer",
               "encoding_descriptor": svtypes.encoding_descriptor(codec).to_dict()}
    return {"schema_uri": SCHEMA_URI, "schema_version": SCHEMA_VERSION,
            "generator_abi_version": GENERATOR_ABI_VERSION,
            "required_runtime_capabilities": [*REQUIRED_RUNTIME_CAPABILITIES, EXTERNAL_FIELD_STORAGE_CAPABILITY],
            "classes": [{"canonical_id": ROOT_ID, "language": "python",
                         "symbol": "tests.integration.python_root_proxy_test.Root",
                         "constructor": {"initiator": "sv", "parameters": [{"name": "seed", "type": binding}]},
                         "fields": [{"name": "count", "type": binding}],
                         "methods": [{"canonical_id": ROOT_ID + "#check", "name": "check",
                                      "parameters": [{"name": "delta", "type": binding}],
                                      "return_type": binding, "timing": "function", "virtual": True},
                                     {"canonical_id": ROOT_ID + "#fixed", "name": "fixed",
                                      "parameters": [{"name": "delta", "type": binding}],
                                      "return_type": binding, "timing": "function", "virtual": False},
                                     {"canonical_id": ROOT_ID + "#scale", "name": "scale",
                                      "parameters": [{"name": "delta", "type": binding}],
                                      "return_type": binding, "timing": "function", "virtual": False, "static": True},
                                     {"canonical_id": ROOT_ID + "#wait_once", "name": "wait_once",
                                      "parameters": [], "return_type": "void", "timing": "task",
                                      "virtual": False, "static": True}]}]}


def probe_manifest_data(*, include_declared_defaults=False):
    data = manifest_data()
    if include_declared_defaults:
        from svx.declarations import _declared_svtypes_fields
        from tests.integration.python_root_proxy_test import Root

        data["classes"][0]["fields"] = [field for field in _declared_svtypes_fields(Root)
                                        if field["name"] != "local"]
    plain = deepcopy(data["classes"][0])
    plain["canonical_id"] = ROOT_ID.removesuffix("Root") + "PlainRoot"
    plain["symbol"] = "tests.integration.python_root_proxy_test.PlainRoot"
    plain["fields"] = []
    plain["methods"] = plain["methods"][:1]
    plain["methods"][0]["canonical_id"] = plain["canonical_id"] + "#check"
    data["classes"].append(plain)
    child = {"canonical_id": "sv://python_root_probe_pkg/Child", "language": "sv",
             "symbol": "python_root_probe_pkg::Child",
             "constructor": {"initiator": "python", "parameters": [
                 {"name": "child_seed", "type": deepcopy(data["classes"][0]["constructor"]["parameters"][0]["type"])}]},
             "fields": [{"name": "child_value", "type": deepcopy(data["classes"][0]["constructor"]["parameters"][0]["type"])}],
             "methods": []}
    for name in ("check", "fixed"):
        method = deepcopy(next(item for item in data["classes"][0]["methods"] if item["name"] == name))
        method["canonical_id"] = child["canonical_id"] + "#" + name
        child["methods"].append(method)
    child["methods"].append({"canonical_id": child["canonical_id"] + "#observed_value",
                             "name": "observed_value", "parameters": [],
                             "return_type": deepcopy(child["constructor"]["parameters"][0]["type"]),
                             "timing": "function", "virtual": False})
    data["classes"].append(child)
    derived = {"canonical_id": DERIVED_ID, "language": "python",
               "symbol": "tests.integration.python_root_derived.Derived",
               "constructor": {"initiator": "sv", "parameters": deepcopy(child["constructor"]["parameters"])},
               "fields": [{"name": "own_value", "type": deepcopy(child["constructor"]["parameters"][0]["type"])}],
               "methods": [deepcopy(child["methods"][0])]}
    derived["methods"][0]["canonical_id"] = DERIVED_ID + "#check"
    data["classes"].append(derived)
    grandchild = deepcopy(child)
    grandchild["canonical_id"] = "sv://python_root_probe_pkg/Grandchild"
    grandchild["symbol"] = "python_root_probe_pkg::Grandchild"
    grandchild["constructor"]["parameters"][0]["name"] = "e_seed"
    grandchild["fields"][0]["name"] = "e_value"
    for method in grandchild["methods"]:
        if method["name"] == "observed_value":
            method["name"] = "observed_python"
        method["canonical_id"] = grandchild["canonical_id"] + "#" + method["name"]
    data["classes"].append(grandchild)
    final = {"canonical_id": "py://tests/integration/python_root/Final", "language": "python",
             "symbol": "tests.integration.python_root_final.Final",
             "constructor": {"initiator": "sv", "parameters": deepcopy(grandchild["constructor"]["parameters"])},
             "fields": [{"name": "f_value", "type": deepcopy(grandchild["fields"][0]["type"])}],
             "methods": [deepcopy(grandchild["methods"][0])]}
    final["constructor"]["parameters"][0]["name"] = "f_seed"
    final["methods"][0]["canonical_id"] = final["canonical_id"] + "#check"
    data["classes"].append(final)
    for index in (2, 3, 4, 5):
        ancestor_indices = [0, *range(2, index)]
        data["classes"][index]["base_lineage"] = [
            {key: deepcopy(value) for key, value in data["classes"][ancestor].items() if key != "base_lineage"}
            for ancestor in ancestor_indices
        ]
    return data


def emit_probe():
    manifest = parse_manifest(probe_manifest_data(include_declared_defaults=True))
    records = ["package svx_call_records_pkg;", "  import svtypes_pkg::*;"]
    from tests.integration.python_root_proxy_test import RootPolicyMode

    records.append(RootPolicyMode.to_sv_enum(1))
    for record in _manifest_sv_record_types(manifest):
        records.append(record.to_sv_obj(1))
    records.extend(["endpackage", "package python_root_probe_pkg;", "  import svtypes_pkg::*;",
                    "  import svx_pkg::*;", "  import svx_call_records_pkg::*;"])
    for root in manifest.classes[:2]:
        records.extend(_emit_planned_python_root_sv_projection(manifest, root, generated_name=root.name, base_type=None))
    records.append('  `include "tests/integration/python_root_child.svh"')
    child = manifest.classes[2]
    records.extend(_emit_planned_python_root_sv_projection(manifest, child,
                                                         generated_name="ChildMirror", base_type="Child"))
    records.extend(_emit_sv_projection_factory(child, "ChildMirror"))
    records.extend(_emit_planned_python_root_sv_projection(manifest, manifest.classes[3],
                                                         generated_name="DerivedProxy", base_type="ChildMirror"))
    records.append('  `include "tests/integration/python_root_grandchild.svh"')
    grandchild = manifest.classes[4]
    records.extend(_emit_planned_python_root_sv_projection(manifest, grandchild,
                                                         generated_name="GrandchildMirror", base_type="Grandchild"))
    records.extend(_emit_sv_projection_factory(grandchild, "GrandchildMirror"))
    records.append("endpackage")
    return "\n".join(records) + "\n"


if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    sv_source = emit_probe()
    target.write_text(sv_source)
    model = parse_manifest(probe_manifest_data())
    python_sources = _emit_python_root_artifacts(model)
    for path, source in python_sources.items():
        output = target.parent / "python" / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(source)
    metadata = artifact_manifest(model, python_sources, sv_source,
                                 python_path_prefix="python", sv_path=target.name)
    declarations = {source.canonical_id: source for source in model.classes}
    # SV helpers still use the fixture's single package, not the public layout.
    for generated_type in metadata["generated_types"]:
        if "systemverilog_fqn" in generated_type:
            source = declarations[generated_type["canonical_class_id"]]
            physical_name = source.name + ("Proxy" if source.canonical_id == DERIVED_ID else "")
            generated_type["systemverilog_fqn"] = "python_root_probe_pkg::" + physical_name
    (target.parent / "artifacts.json").write_text(json.dumps(metadata, indent=2) + "\n")
