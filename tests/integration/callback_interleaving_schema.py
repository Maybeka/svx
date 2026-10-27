import copy
import svtypes


def manifest_data():
    codec = svtypes.Int()
    integer = dict(unified_type_name=svtypes.unified_type_name(codec),
                   svtypes=svtypes.type_spec_identity(svtypes.Int),
                   sv=svtypes.sv_type_expression(codec), sv_packer=svtypes.sv_packer_expression(codec),
                   encoding_descriptor=svtypes.encoding_descriptor(codec).to_dict())
    cid = "sv://callback_interleaving_pkg/Base"
    methods = [dict(canonical_id=cid + "#" + name, name=name,
                    parameters=[dict(name="tag", type=integer)], return_type=returned,
                    timing=timing, virtual=True, pure_virtual=False)
               for name, returned, timing in (("work", "void", "task"), ("check", integer, "function"))]
    base = dict(canonical_id=cid, language="sv", symbol="callback_interleaving_pkg::Base",
                constructor=dict(initiator="python", parameters=[]), methods=methods)
    return dict(schema_uri="https://svx.dev/schema/inheritance-manifest/v2", schema_version="2.0.0",
                generator_abi_version=2, required_runtime_capabilities=[
                    "svtypes.checked-encoding-descriptor.v1", "svtypes.codec-context.v1",
                    "svtypes.record-schema.v1", "svtypes.remote-reference.v1"], classes=[base, dict(
                        canonical_id="py://callback_interleaving_test/Derived", language="python",
                        symbol="tests.integration.callback_interleaving_test.Derived",
                        base_lineage=[copy.deepcopy(base)], methods=[dict(method,
                            canonical_id="py://callback_interleaving_test/Derived#" + method["name"])
                            for method in methods])])


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    Path(sys.argv[1]).write_text(json.dumps(manifest_data(), indent=2) + "\n")
