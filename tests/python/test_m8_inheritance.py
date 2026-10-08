import json
import sys
from dataclasses import make_dataclass
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest
import svtypes
import svx.inheritance as inheritance
from svtypes import Int, RemoteRef, String, encoding_descriptor, unified_type_name

from svx import Inout, Output, SVXInheritanceError
from svx import SVXRemoteError
from svx.cli import main
from svx.inheritance import (
    SCHEMA_URI,
    SCHEMA_VERSION,
    dispatch_python_call,
    emit_python_mirrors,
    emit_sv_mirrors,
    emit_sv_mirror_stages,
    encode_constructor,
    invoke_sv,
    migrate_manifest,
    parse_manifest,
    projection_plan,
    register_contract,
    register_constructor,
    register_python_subclass,
    create_python_instance,
)
from svx import runtime


def test_callback_portions_follow_python_segments_not_final_receiver():
    from types import SimpleNamespace

    def node(language, name):
        return SimpleNamespace(language=language, canonical_id=name)

    lineage = tuple(node(language, name) for language, name in (
        ("sv", "A"), ("python", "B"), ("python", "BChild"),
        ("sv", "C"), ("python", "D"),
    ))
    assert inheritance._python_callback_portions(lineage) == {
        "A": "BChild", "B": "BChild", "BChild": "BChild",
        "C": "D",
    }
    assert inheritance._python_callback_portions((node("sv", "A"),)) == {}


@pytest.fixture(autouse=True)
def inheritance_codec_session():
    runtime._state = runtime.RuntimeState.READY
    runtime._codec_session = svtypes.CodecSession()
    yield
    runtime._state = runtime.RuntimeState.UNINITIALIZED
    runtime._codec_session = None


def type_ref(factory, *, sv: str, sv_packer: str, args=(), module="svtypes", symbol=None):
    if factory is RemoteRef:
        annotation = RemoteRef[args[0]]
        codec = annotation()
        identity = svtypes.type_spec_identity(annotation)
    else:
        codec = factory(*args)
        identity = None
    return {
        "unified_type_name": unified_type_name(codec),
        **({"svtypes": identity} if identity is not None else {"python": {
            "module": module,
            "symbol": symbol or factory.__name__,
            "args": list(args),
            "kwargs": {},
        }}),
        "sv": sv,
        "sv_packer": sv_packer,
        "encoding_descriptor": encoding_descriptor(codec).to_dict(),
    }


INT = type_ref(Int, sv="int", sv_packer="int_packer")


@pytest.mark.parametrize("static", [False, True])
def test_generated_python_bridge_preserves_collision_parameter_names(monkeypatch, static):
    import inspect
    from dataclasses import replace

    original = parse_manifest(manifest_data()).classes[0].methods[0]
    names = ("self", "svx_self", "invoke_sv", "svx_invoke_sv",
             "invoke_sv_static", "svx_invoke_sv_static")
    parameters = tuple(replace(original.parameters[0], name=name) for name in names)
    method = replace(original, parameters=parameters, is_static=static)
    calls = []

    def invoke(target, method_id, values):
        calls.append((target, method_id, values))
        return 42

    monkeypatch.setattr(inheritance, "invoke_sv", invoke)
    monkeypatch.setattr(inheritance, "invoke_sv_static", invoke)
    class_id = "sv://collision/Source"
    source = "class Mirror:\n" + "\n".join(
        inheritance._emit_python_bridge_method(method, class_id)
    )
    namespace = {"invoke_sv": invoke, "invoke_sv_static": invoke}
    exec(compile(source, "collision_mirror.py", "exec"), namespace)
    mirror = namespace["Mirror"]()
    mirror._svx_remote_object_id = 73
    callback = getattr(mirror, method.name)
    assert tuple(inspect.signature(callback).parameters) == names
    assert callback(*range(len(names))) == 42
    assert calls == [(class_id if static else 73, method.canonical_id,
                      dict(zip(names, range(len(names)))))]

    data = manifest_data()
    raw_method = data["classes"][0]["methods"][0]
    raw_method["parameters"] = [{"name": name, "type": INT} for name in names]
    raw_method["static"] = static
    raw_method["virtual"] = not static
    for path, text in emit_python_mirrors(parse_manifest(data)).items():
        compile(text, str(path), "exec")


@pytest.mark.parametrize("shape", ["standalone", "projection", "reverse"])
def test_generated_constructor_preserves_collision_parameters(monkeypatch, shape):
    import inspect
    from types import ModuleType, SimpleNamespace

    names = ("self", "svx_self", "_native", "encode_constructor", "bind_instance",
             "object_id", "SVMirror", "_ForeignBaseMonitor")
    if shape == "projection":
        from tests.integration.sv_field_mirror_schema import manifest_data as source_manifest
        data = source_manifest()
    else:
        data = manifest_data()
        data["classes"] = [data["classes"][0 if shape == "standalone" else 1]]
    source = data["classes"][0]
    source["constructor"] = {"initiator": "python", "parameters": [
        {"name": name, "type": INT} for name in names
    ]}
    source["methods"] = []
    calls = []

    def encode(class_id, values):
        calls.append(("encode", class_id, values.copy()))
        return b"ctor"

    def create(class_id, payload):
        assert payload == b"ctor"
        calls.append(("create", class_id))
        return 81

    monkeypatch.setattr(inheritance, "encode_constructor", encode)
    monkeypatch.setattr(inheritance, "bind_instance", lambda oid, obj: calls.append(("bind", oid, obj)))
    monkeypatch.setattr(inheritance, "register_constructor", lambda *args, **kwargs: None)
    monkeypatch.setattr(inheritance, "register_contract", lambda *args, **kwargs: None)
    import svx
    monkeypatch.setattr(svx, "_native", SimpleNamespace(inheritance_create_sv=create))
    if shape == "reverse":
        module = ModuleType("checks")

        class BaseMonitor:
            def __init__(owner, *args):
                calls.append(("source_init", args))

        module.BaseMonitor = BaseMonitor
        monkeypatch.setitem(sys.modules, "checks", module)
    # This test isolates executable Python construction from the independently
    # failing public RecordSchema handling of underscore-prefixed wire fields.
    generated = emit_python_mirrors(parse_manifest(data))
    text = next(text for path, text in generated.items() if path.name != "__init__.py")
    namespace = {}
    exec(compile(text, "constructor_collisions.py", "exec"), namespace)
    cls = namespace[source["symbol"].split("::")[-1].split(".")[-1]]
    assert tuple(inspect.signature(cls).parameters) == names
    instance = cls(*range(len(names)))
    assert instance._svx_remote_object_id == 81
    assert ("encode", source["canonical_id"], dict(zip(names, range(len(names))))) in calls
    assert ("bind", 81, instance) in calls
    if shape == "reverse":
        assert ("source_init", tuple(range(len(names)))) in calls


@pytest.mark.parametrize("entry", ["sv", "python"])
def test_call_record_rejects_dependency_dropping_declared_fields(entry, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(svtypes, "schema_descriptor", lambda _value_type:
                        SimpleNamespace(to_dict=lambda: {"schema": {"fields": []}}))
    binding = inheritance._type_binding(INT, "test", allow_void=False)
    with pytest.raises(SVXInheritanceError, match="does not preserve declared fields.*_native"):
        if entry == "sv":
            inheritance._sv_record_type("sv://record/Source", "request", (("_native", binding),))
        else:
            inheritance._call_record_schema("sv://record/Source", "request", (("_native", binding.runtime_spec()),))


def test_sv_owned_fields_bind_to_inherited_storage_without_shadowing():
    from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest

    manifest = parse_manifest(field_manifest())
    python_files = emit_python_mirrors(manifest)
    mirror = next(text for path, text in python_files.items()
                  if str(path) == "svx_mirror/field_owner_pkg.py")
    assert "count = _codec_from_spec(" in mirror
    assert "'count': 'sv://field_owner_pkg/Base.count'" in mirror
    compile(mirror, "field_owner_pkg.py", "exec")
    sv_text = emit_sv_mirrors(manifest)
    assert "extends field_owner_pkg::Base" in sv_text
    assert "int count;" not in sv_text
    assert "int_packer::pack(this.count, bytes)" in sv_text
    assert "int_packer::unpack(this.count, bytes, field_offset)" in sv_text


@pytest.mark.parametrize("annotation,kind", [
    (svtypes.Queue[Int], "queue"),
    (svtypes.DynArray[Int], "dyn_array"),
    (svtypes.Array[Int, 3], "fixed_array"),
])
def test_indexed_field_codegen_resolves_child_through_public_descriptor(annotation, kind, monkeypatch):
    from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest

    data = field_manifest()
    codec = annotation()
    data["classes"][0]["fields"][0]["type"] = {
        "unified_type_name": svtypes.unified_type_name(codec),
        "svtypes": svtypes.type_spec_identity(annotation),
        "sv": svtypes.sv_type_expression(codec),
        "sv_packer": svtypes.sv_packer_expression(codec),
        "encoding_descriptor": svtypes.encoding_descriptor(codec).to_dict(),
    }
    binding = parse_manifest(data).classes[0].fields[0].type_binding
    paths = []
    resolve = svtypes.FieldDescriptor.resolve_path

    def record_resolve(self, path):
        paths.append(path)
        return resolve(self, path)

    monkeypatch.setattr(svtypes.FieldDescriptor, "resolve_path", record_resolve)
    profile = inheritance._field_operation_profile(binding)
    assert profile == (kind, "int", "svtypes_pkg::int_packer", None, None)
    assert paths == [svtypes.FieldPath().index(0)]
@pytest.mark.parametrize("key_type,value_type", [
    (Int, Int), (String, svtypes.Bit[8]), (svtypes.BitSigned[16], svtypes.Logic[4]),
])
@pytest.mark.parametrize('canonical', [True, False])
def test_associative_field_profile_uses_public_type_arguments(key_type, value_type, monkeypatch, canonical):
    from tests.integration.sv_field_mirror_schema import manifest_data as field_manifest

    annotation = svtypes.AssocArray[key_type, value_type]
    codec = annotation()
    key = svtypes.materialize_type_spec(key_type, location="test key")
    value = svtypes.materialize_type_spec(value_type, location="test value")
    expected = ("assoc_array", svtypes.sv_type_expression(value), svtypes.sv_packer_expression(value),
                svtypes.sv_type_expression(key), svtypes.sv_packer_expression(key))
    data = field_manifest()
    data["classes"][0]["fields"][0]["type"] = {
        "unified_type_name": svtypes.unified_type_name(codec),
        "svtypes": svtypes.type_spec_identity(annotation),
        "sv": svtypes.sv_type_expression(codec), "sv_packer": svtypes.sv_packer_expression(codec),
        "encoding_descriptor": svtypes.encoding_descriptor(codec).to_dict(),
    }
    binding = parse_manifest(data).classes[0].fields[0].type_binding
    if not canonical:
        from dataclasses import replace
        binding = replace(binding, svtypes_identity_json=None,
                          python_module='tests.custom_codec', python_symbol='mapping')
    monkeypatch.setattr(inheritance, "_codec_from_spec", lambda _: codec)
    access = svtypes.AssocArray.__getattribute__

    def reject_private_templates(self, name):
        if (name in {"_key_template", "_val_template"}
                and sys._getframe(1).f_globals.get('__name__', '').startswith('svx')):
            raise AssertionError("SVX must use public associative type arguments")
        return access(self, name)

    monkeypatch.setattr(svtypes.AssocArray, "__getattribute__", reject_private_templates)
    assert inheritance._field_operation_profile(binding) == expected


def test_projected_associative_fixture_has_canonical_public_identity():
    model = inheritance.load_manifest(Path("tests/integration/field_projection_inheritance_manifest.json"))
    expected = svtypes.type_spec_identity(svtypes.AssocArray[Int, Int])
    bindings = [field.type_binding for cls in inheritance._all_manifest_classes(model)
                for field in cls.fields if field.name == "mapping"]
    assert bindings
    assert all(binding.runtime_spec()["svtypes"] == expected for binding in bindings)
    assert "assoc_array_packer" in emit_sv_mirrors(model)


STRING = type_ref(String, sv="string", sv_packer="string_packer")


def manifest_data() -> dict:
    return {
        "schema_uri": SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "generator_abi_version": 2,
        "required_runtime_capabilities": [
            "svtypes.checked-encoding-descriptor.v1",
            "svtypes.codec-context.v1",
            "svtypes.record-schema.v1",
            "svtypes.remote-reference.v1",
        ],
        "classes": [
            {
                "canonical_id": "sv://tb_pkg/BaseDriver",
                "language": "sv",
                "symbol": "tb_pkg::BaseDriver",
                "methods": [
                    {
                        "canonical_id": "sv://tb_pkg/BaseDriver#drive",
                        "name": "drive",
                        "parameters": [{"name": "address", "type": INT}],
                        "return_type": "void",
                        "timing": "task",
                        "virtual": True,
                        "pure_virtual": False,
                    }
                ],
            },
            {
                "canonical_id": "py://checks/BaseMonitor",
                "language": "python",
                "symbol": "checks.BaseMonitor",
                "methods": [
                    {
                        "canonical_id": "py://checks/BaseMonitor#sample",
                        "name": "sample",
                        "parameters": [],
                        "return_type": "void",
                        "timing": "task",
                        "virtual": True,
                        "pure_virtual": True,
                    }
                ],
            },
        ],
    }


def test_manifest_emits_language_specific_mirrors():
    manifest = parse_manifest(manifest_data())

    python_files = emit_python_mirrors(manifest)
    assert {str(path) for path in python_files} == {
        "svx_py/__init__.py",
        "svx_py/checks.py",
        "svx_mirror/__init__.py",
        "svx_mirror/tb_pkg.py",
    }
    mirror_text = next(text for path, text in python_files.items() if str(path) == "svx_mirror/tb_pkg.py")
    assert "class BaseDriver" in mirror_text
    assert "def drive(self, address):" in mirror_text
    assert "'unified_type_name': 'svtypes.Int'" in mirror_text
    assert "svtypes.Int()" not in mirror_text
    assert "# Manifest: https://svx.dev/schema/inheritance-manifest/v2 v2.0.0; generator ABI 2." in mirror_text
    assert "# Role: Python mirrors for SystemVerilog-owned classes." in mirror_text
    assert "# --- SvTypes call contracts (private bridge metadata) ---" in mirror_text
    assert "register_contract(\n    {" in mirror_text

    sv_text = emit_sv_mirrors(manifest)
    assert "// Layout: SvTypes records, typed external handles, public projections, then lineage helpers." in sv_text
    assert "// Private SvTypes call records" in sv_text
    assert "// Public Python-to-SystemVerilog proxy projections" in sv_text
    assert "package svx_proxy_checks;" in sv_text
    assert "virtual class BaseMonitor implements svx_dispatchable, svx_function_dispatchable;" in sv_text
    assert "virtual task sample();" in sv_text
    assert "python_proxy" not in sv_text


@pytest.mark.parametrize(
    ("kind", "target", "sv_type"),
    [
        ("sv_class", "sv://packet_pkg/Packet", "packet_pkg::Packet"),
        ("virtual_interface", "sv-vif://bus_if/master", "virtual bus_if.master"),
    ],
)
def test_generated_external_handle_adapters_preserve_sv_formal_types(
    kind, target, sv_type
):
    data = manifest_data()
    method = data["classes"][1]["methods"][0]
    reference = type_ref(
        RemoteRef,
        sv="svtypes_pkg::remote_ref",
        sv_packer="svtypes_pkg::remote_ref_packer",
        args=(target,),
    )
    method["parameters"] = [
        {
            "name": "foreign",
            "type": reference,
            "handle": {
                "kind": kind,
                "target_type_name": target,
                "sv_type": sv_type,
            },
        }
    ]
    method["return_type"] = reference
    method["return_handle"] = {
        "kind": kind,
        "target_type_name": target,
        "sv_type": sv_type,
    }
    method["timing"] = "function"

    manifest = parse_manifest(data)
    text = emit_sv_mirrors(manifest)
    adapter = "SVXExternal_" + target.replace(":", "_").replace("/", "_").replace("-", "_")
    assert "package svx_external_handles_pkg;" in text
    assert f"class {adapter} implements svx_session_resource;" in text
    assert f"function remote_ref encode({sv_type} value);" in text
    assert f"function bit decode(input remote_ref reference, output {sv_type} value" in text
    assert f"virtual function {sv_type} sample(input {sv_type} foreign);" in text
    assert "svtypes_pkg::remote_ref foreign = new" in text
    assert f"{adapter}::encode(foreign)" in text
    assert f"{adapter}::decode(response_value.svx_return_value, result, error)" in text
    assert "// Private typed endpoints; RemoteRef is the sole encoded foreign-handle value." in text
    assert f"// {kind}: {sv_type} <-> RemoteRef[{target}]." in text
    assert "// Preserve the concrete SV handle in this session; encode only a typed RemoteRef." in text
    assert "// Resolve this session-scoped RemoteRef back to the declared static SV type." in text
    assert "// Foreign handles are resolved through typed RemoteRef endpoints." in text


def test_manifest_rejects_external_handle_without_matching_remote_ref_target():
    data = manifest_data()
    parameter = data["classes"][0]["methods"][0]["parameters"][0]
    parameter["type"] = type_ref(
        RemoteRef,
        sv="svtypes_pkg::remote_ref",
        sv_packer="svtypes_pkg::remote_ref_packer",
        args=("sv://packet_pkg/Packet",),
    )
    parameter["handle"] = {
        "kind": "sv_class",
        "target_type_name": "sv://packet_pkg/OtherPacket",
        "sv_type": "packet_pkg::Packet",
    }
    with pytest.raises(SVXInheritanceError, match="must match the SvTypes RemoteRef target"):
        parse_manifest(data)


def test_python_initiated_sv_base_without_cross_language_lineage_has_no_sv_proxy():
    data = manifest_data()
    data["classes"][0]["constructor"] = {
        "initiator": "python",
        "parameters": [{"name": "seed", "type": INT}],
    }
    manifest = parse_manifest(data)

    python_text = emit_python_mirrors(manifest)[next(
        path for path in emit_python_mirrors(manifest) if str(path) == "svx_mirror/tb_pkg.py"
    )]
    assert "def __init__(self, seed):" in python_text
    assert "_native.inheritance_create_sv('sv://tb_pkg/BaseDriver'" in python_text
    assert "encode_constructor('sv://tb_pkg/BaseDriver', {'seed': seed})" in python_text

    sv_text = emit_sv_mirrors(manifest)
    assert "BaseDriver_python_proxy" not in sv_text
    assert "svx_pyproxy_" not in sv_text
    assert "class BaseDriver_factory implements svx_factory;" in sv_text
    assert 'svx_inheritance_registry::register_factory("sv://tb_pkg/BaseDriver", this);' in sv_text
    assert "BaseDriver_factory BaseDriver_factory_instance = new();" in sv_text


def test_manifest_rejects_cross_language_contract_errors():
    invalid = manifest_data()
    invalid["classes"][0]["unknown"] = True
    with pytest.raises(SVXInheritanceError, match="contains unsupported fields: unknown"):
        parse_manifest(invalid)

    invalid = manifest_data()
    invalid["classes"][0]["methods"][0]["canonical_id"] = "sv://tb_pkg/BaseDriver#wrong"
    with pytest.raises(SVXInheritanceError, match="must be 'sv://tb_pkg/BaseDriver#drive'"):
        parse_manifest(invalid)

    invalid = manifest_data()
    invalid["classes"][0]["methods"][0]["parameters"][0]["direction"] = "const"
    with pytest.raises(SVXInheritanceError, match="must be input, output, or inout"):
        parse_manifest(invalid)

    valid = manifest_data()
    valid["classes"][0]["methods"][0]["parameters"][0]["direction"] = "output"
    parse_manifest(valid)

    invalid = manifest_data()
    invalid["classes"][0]["methods"][0]["return_type"] = INT
    with pytest.raises(SVXInheritanceError, match="task methods must have return_type 'void'"):
        parse_manifest(invalid)

    valid = manifest_data()
    method = valid["classes"][0]["methods"][0]
    method["timing"] = "function"
    method["return_type"] = INT
    method["parameters"][0]["name"] = "result"
    method["parameters"][0]["direction"] = "output"
    parse_manifest(valid)

    invalid = manifest_data()
    invalid["classes"][0]["constructor"] = {"initiator": "host", "parameters": []}
    with pytest.raises(SVXInheritanceError, match="must be 'python' or 'sv'"):
        parse_manifest(invalid)

    invalid = manifest_data()
    invalid["classes"][0]["constructor"] = {
        "initiator": "python",
        "parameters": [
            {"name": "name", "type": INT},
            {"name": "name", "type": INT},
        ],
    }
    with pytest.raises(SVXInheritanceError, match="duplicate parameter names"):
        parse_manifest(invalid)


def test_sv_generation_implements_completion_time_copy_out():
    data = manifest_data()
    method = data["classes"][0]["methods"][0]
    method["parameters"] = [
        {"name": "source", "type": INT, "direction": "input"},
        {"name": "changed", "type": INT, "direction": "inout"},
        {"name": "observed", "type": INT, "direction": "output"},
    ]
    data["classes"].append(
        {
            "canonical_id": "py://checks/PythonDriver",
            "language": "python",
            "symbol": "checks.PythonDriver",
            "methods": [],
            "base_lineage": [data["classes"][0]],
        }
    )
    manifest = parse_manifest(data)
    text = emit_sv_mirrors(manifest)

    assert "input int source, inout int changed, output int observed" in text
    assert "package svx_call_records_pkg;" in text
    outbound = text.split("virtual task drive", 1)[1].split("endtask", 1)[0]
    assert "request_value.source = source;" in outbound
    assert "request_value.changed = changed;" in outbound
    assert "request_value.observed" not in outbound
    assert outbound.count("request_value.pack(bytes);") == 1
    assert "changed = response_value.changed;" in outbound
    assert "observed = response_value.observed;" in outbound

    python_text = emit_python_mirrors(manifest)[
        next(
            path
            for path in emit_python_mirrors(manifest)
                if str(path) == "svx_mirror/tb_pkg.py"
        )
    ]
    assert "def drive(self, source, changed, observed):" in python_text
    assert "response_value" not in python_text
    compile(python_text, "generated/tb_pkg.py", "exec")


@pytest.mark.parametrize("direction", ["ref", "const ref"])
def test_manifest_rejects_ref_parameters(direction):
    data = manifest_data()
    method = data["classes"][0]["methods"][0]
    method["timing"] = "function"
    method["return_type"] = INT
    method["parameters"] = [{"name": "value", "direction": direction, "type": INT}]
    with pytest.raises(SVXInheritanceError, match="ref and const ref are not supported"):
        parse_manifest(data)


def test_static_sv_member_uses_a_class_dispatcher_not_an_instance():
    data = manifest_data()
    source = data["classes"][0]
    source["methods"].append(
        {
            "canonical_id": "sv://tb_pkg/BaseDriver#static_value",
            "name": "static_value",
            "parameters": [],
            "return_type": INT,
            "timing": "function",
            "virtual": False,
            "pure_virtual": False,
            "static": True,
        }
    )
    data["classes"].append(
        {
            "canonical_id": "py://checks/PythonDriver",
            "language": "python",
            "symbol": "checks.PythonDriver",
            "methods": [],
            "base_lineage": [source],
        }
    )

    manifest = parse_manifest(data)
    python_text = emit_python_mirrors(manifest)[
        next(path for path in emit_python_mirrors(manifest) if str(path) == "svx_mirror/tb_pkg.py")
    ]
    assert "@staticmethod" in python_text
    assert "def static_value():" in python_text
    assert "invoke_sv_static('sv://tb_pkg/BaseDriver'" in python_text
    assert "self._svx_remote_object_id" not in python_text.split("def static_value():", 1)[1].split("\n\n", 1)[0]

    sv_text = emit_sv_mirrors(manifest)
    assert "static task svx_invoke_static" in sv_text
    assert "BaseDriver::static_value()" in sv_text
    assert "class BaseDriverStaticDispatcher implements svx_static_dispatchable, svx_static_function_dispatchable;" in sv_text
    assert "register_static(\"sv://tb_pkg/BaseDriver\"" in sv_text


def test_manifest_rejects_static_virtual_method():
    data = manifest_data()
    data["classes"][0]["methods"][0]["static"] = True
    with pytest.raises(SVXInheritanceError, match="static methods cannot be virtual"):
        parse_manifest(data)


def test_standalone_sv_mirror_exposes_static_member_through_a_gateway():
    data = manifest_data()
    data["classes"] = [data["classes"][0]]
    data["classes"][0]["methods"] = [
        {
            "canonical_id": "sv://tb_pkg/BaseDriver#static_value",
            "name": "static_value",
            "parameters": [],
            "return_type": INT,
            "timing": "function",
            "virtual": False,
            "pure_virtual": False,
            "static": True,
        }
    ]
    manifest = parse_manifest(data)

    python_text = emit_python_mirrors(manifest)[
        next(path for path in emit_python_mirrors(manifest) if str(path) == "svx_mirror/tb_pkg.py")
    ]
    assert "@staticmethod" in python_text
    assert "invoke_sv_static('sv://tb_pkg/BaseDriver'" in python_text

    sv_text = emit_sv_mirrors(manifest)
    assert "package svx_static_tb_pkg_BaseDriver_pkg;" in sv_text
    assert "virtual class BaseDriverStaticGateway extends tb_pkg::BaseDriver;" in sv_text
    assert "BaseDriverStaticGateway::svx_invoke_static" in sv_text

    from svx.declarations import manifest_dict

    assert manifest_dict(manifest)["classes"][0]["methods"][0]["static"] is True


def test_manifest_rejects_generated_sv_name_collision():
    data = manifest_data()
    data["classes"].append(
        {
            "canonical_id": "py://other/BaseMonitor",
            "language": "python",
            "symbol": "checks.BaseMonitor",
            "methods": [],
        }
    )
    with pytest.raises(SVXInheritanceError, match="generated SystemVerilog name"):
        parse_manifest(data)


def test_manifest_rejects_same_leaf_python_module_collision():
    data = manifest_data()
    data["classes"] = [
        {
            "canonical_id": "py://one/agent/Driver",
            "language": "python",
            "symbol": "one.agent.Driver",
            "methods": [],
        },
        {
            "canonical_id": "py://two/agent/Driver",
            "language": "python",
            "symbol": "two.agent.Driver",
            "methods": [],
        },
    ]
    with pytest.raises(
        SVXInheritanceError,
        match=r"svx_proxy_agent.Driver collides",
    ):
        parse_manifest(data)


def test_closed_parameterized_sv_class_emits_a_specialized_mirror():
    data = manifest_data()
    base = data["classes"][0]
    base["specialization"] = {
        "arguments": [
            {"kind": "type", "type": INT},
            {"kind": "value", "sv_type": "int", "value": 16},
        ]
    }
    data["classes"].append(
        {
            "canonical_id": "py://checks/ParameterizedChild",
            "language": "python",
            "symbol": "checks.ParameterizedChild",
            "methods": [],
            "base_lineage": [base],
        }
    )
    manifest = parse_manifest(data)
    text = emit_sv_mirrors(manifest)
    assert "class BaseDriver extends tb_pkg::BaseDriver#(int, 16)" in text
    assert "extends tb_pkg::BaseDriver#(int, 16)" in text

    duplicate = manifest_data()
    duplicate["classes"][0]["specialization"] = base["specialization"]
    duplicate["classes"].append(
        {
            "canonical_id": "sv://other_pkg/BaseDriver",
            "language": "sv",
            "symbol": "tb_pkg::BaseDriver",
            "specialization": base["specialization"],
            "methods": [],
        }
    )
    with pytest.raises(SVXInheritanceError, match="collides"):
        parse_manifest(duplicate)


def test_alternating_lineage_generates_only_required_mirror_and_proxy():
    """A -> B -> C generates AMirror/BProxy, never an unrequested C helper."""

    data = {
        "schema_uri": SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "generator_abi_version": 2,
        "required_runtime_capabilities": [
            "svtypes.checked-encoding-descriptor.v1",
            "svtypes.codec-context.v1",
            "svtypes.record-schema.v1",
            "svtypes.remote-reference.v1",
            "svtypes.external-field-storage.v1",
        ],
        "classes": [
            {
                "canonical_id": "sv://drivers/A",
                "language": "sv",
                "symbol": "drivers::A",
                "methods": [
                    {
                        "canonical_id": "sv://drivers/A#check",
                        "name": "check",
                        "parameters": [],
                        "return_type": "void",
                        "timing": "task",
                        "virtual": True,
                        "pure_virtual": False,
                    }
                ],
            },
            {
                "canonical_id": "py://checks/B",
                "language": "python",
                "symbol": "checks.B",
                "fields": [{"name": "retry", "type": INT}],
                "methods": [
                    {
                        "canonical_id": "py://checks/B#check",
                        "name": "check",
                        "parameters": [],
                        "return_type": "void",
                        "timing": "task",
                        "virtual": True,
                        "pure_virtual": False,
                    }
                ],
            },
            {
                "canonical_id": "sv://drivers/C",
                "language": "sv",
                "symbol": "drivers::C",
                "methods": [],
                "base_lineage": [
                    {
                        "canonical_id": "sv://drivers/A",
                        "language": "sv",
                        "symbol": "drivers::A",
                        "methods": [
                            {
                                "canonical_id": "sv://drivers/A#check",
                                "name": "check",
                                "parameters": [],
                                "return_type": "void",
                                "timing": "task",
                                "virtual": True,
                                "pure_virtual": False,
                            }
                        ],
                    },
                    {
                        "canonical_id": "py://checks/B",
                        "language": "python",
                        "symbol": "checks.B",
                        "fields": [{"name": "retry", "type": INT}],
                        "methods": [
                            {
                                "canonical_id": "py://checks/B#check",
                                "name": "check",
                                "parameters": [],
                                "return_type": "void",
                                "timing": "task",
                                "virtual": True,
                                "pure_virtual": False,
                            }
                        ],
                    },
                ],
            },
        ],
    }
    manifest = parse_manifest(data)
    plan = projection_plan(manifest.classes[-1])
    assert [(step.kind, step.generated_name) for step in plan.steps] == [
        ("sv_mirror", "A"),
        ("sv_proxy", "B"),
    ]

    for emit in (emit_sv_mirrors, emit_python_mirrors, emit_sv_mirror_stages):
        with pytest.raises(SVXInheritanceError, match="declaration cycle.*drivers"):
            emit(manifest)
    data["classes"][2]["symbol"] = "drivers_child::C"
    manifest = parse_manifest(data)
    text = emit_sv_mirrors(manifest)
    assert "class A extends drivers::A implements svx_dispatchable, svx_function_dispatchable;" in text
    assert "class B extends A implements svx_dispatchable, svx_function_dispatchable;" in text
    assert "int retry = 32'd0;" in text
    assert '"py://checks/B.retry@svx_field_read"' in text
    # B delegates A's explicit base gateway to the generated A bridge instead
    # of calling the A virtual override and re-entering B.check().
    bproxy = text.split("class B extends A", 1)[1].split("endclass : B", 1)[0]
    assert "default: super.svx_invoke(method_id, request, ok, response, error);" in bproxy
    assert "virtual task check(" not in bproxy
    assert '"sv://drivers/A#check":' not in bproxy
    assert "longint unsigned __svx_remote_object_id;" not in bproxy
    assert "function new(input longint unsigned object_id = 0);" in bproxy
    assert "super.new(object_id);" in bproxy
    assert "class C extends C" not in text
    assert "A_python_proxy" not in text
    assert "virtual class B implements" not in text
    python_files = emit_python_mirrors(manifest)
    mirror_path = next(path for path in python_files if str(path) == "svx_mirror/drivers.py")
    python_mirror = python_files[mirror_path]
    assert "class A(SVMirror):" in python_mirror
    assert "register_python_subclass('sv://drivers/A', cls)" in python_mirror
    assert "inheritance_create_sv('sv://drivers/A'" in python_mirror
    assert "__svx_projected_fields_by_class_id__" in python_mirror
    assert "'py://checks/B': {'retry': 'py://checks/B.retry'}" in python_mirror
    assert "instance._svx_bind_active_projected_fields()" in python_mirror
    compile(python_mirror, "generated/svx_mirror/drivers.py", "exec")


def test_four_segment_lineage_binds_early_python_fields_at_final_mirror():
    """A -> B -> C -> D binds BProxy fields while constructing D via CMirror."""

    data = {
        "schema_uri": SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "generator_abi_version": 2,
        "required_runtime_capabilities": [
            "svtypes.checked-encoding-descriptor.v1",
            "svtypes.codec-context.v1",
            "svtypes.record-schema.v1",
            "svtypes.remote-reference.v1",
            "svtypes.external-field-storage.v1",
        ],
        "classes": [
            {
                "canonical_id": "py://checks/D",
                "language": "python",
                "symbol": "checks.D",
                "methods": [],
                "base_lineage": [
                    {
                        "canonical_id": "sv://drivers/A",
                        "language": "sv",
                        "symbol": "drivers::A",
                        "methods": [],
                    },
                    {
                        "canonical_id": "py://checks/B",
                        "language": "python",
                        "symbol": "checks.B",
                        "fields": [{"name": "retry", "type": INT}],
                        "methods": [],
                    },
                    {
                        "canonical_id": "sv://drivers/C",
                        "language": "sv",
                        "symbol": "drivers::C",
                        "methods": [],
                    },
                ],
            }
        ],
    }
    manifest = parse_manifest(data)
    plan = projection_plan(manifest.classes[0])
    assert [(step.kind, step.generated_name) for step in plan.steps] == [
        ("sv_mirror", "A"),
        ("sv_proxy", "B"),
        ("sv_mirror", "C"),
    ]

    for emit in (emit_sv_mirrors, emit_python_mirrors, emit_sv_mirror_stages):
        with pytest.raises(SVXInheritanceError, match="declaration cycle.*drivers"):
            emit(manifest)
    data["classes"][0]["base_lineage"][2]["symbol"] = "drivers_child::C"
    manifest = parse_manifest(data)
    sv_text = emit_sv_mirrors(manifest)
    assert "class A extends drivers::A implements svx_dispatchable, svx_function_dispatchable;" in sv_text
    assert "class B extends A implements svx_dispatchable, svx_function_dispatchable;" in sv_text
    assert "class C extends drivers_child::C implements svx_dispatchable, svx_function_dispatchable;" in sv_text
    assert "class D extends" not in sv_text

    python_files = emit_python_mirrors(manifest)
    mirror_path = next(path for path in python_files if str(path) == "svx_mirror/drivers_child.py")
    python_mirror = python_files[mirror_path]
    cmirror = python_mirror.split("class C(SVMirror):", 1)[1]
    assert "'py://checks/D': {'retry': 'py://checks/B.retry'}" in cmirror
    assert "self._svx_bind_projected_fields({'retry': 'py://checks/B.retry'})" in cmirror
    compile(python_mirror, "generated/svx_mirror/drivers_child.py", "exec")

    stages = emit_sv_mirror_stages(manifest)
    assert "common.svh" in stages
    assert "class A extends drivers::A" not in stages["common.svh"]
    assert "class B extends A" not in stages["common.svh"]
    assert "class C extends drivers_child::C" not in stages["common.svh"]
    after_a = next(name for name in stages if name.startswith("after_sv_drivers_A_"))
    before_c = next(name for name in stages if name.startswith("before_sv_drivers_C_"))
    after_c = next(name for name in stages if name.startswith("after_sv_drivers_C_"))
    assert "// Role: lineage bridge inserted after sv://drivers/A." in stages[after_a]
    assert "// Role: lineage bridge inserted before sv://drivers/C." in stages[before_c]
    assert "class A extends drivers::A" in stages[after_a]
    assert "class B extends A" in stages[before_c]
    assert "class C extends drivers_child::C" in stages[after_c]


def test_inheritance_gen_cli_writes_mirrors(tmp_path):
    manifest_path = tmp_path / "inheritance.json"
    manifest_path.write_text(json.dumps(manifest_data()))
    python_out = tmp_path / "python"
    sv_out = tmp_path / "mirrors.sv"
    artifacts_out = tmp_path / "artifacts.json"
    out = StringIO()

    assert main(
        [
            "inheritance-gen",
            "--manifest",
            str(manifest_path),
            "--python-out",
            str(python_out),
            "--sv-out",
            str(sv_out),
            "--artifact-manifest",
            str(artifacts_out),
        ],
        out=out,
    ) == 0

    assert (python_out / "svx_mirror" / "tb_pkg.py").is_file()
    assert "BaseDriver" in (python_out / "svx_mirror" / "tb_pkg.py").read_text()
    assert "package svx_proxy_checks;" in sv_out.read_text()
    artifacts = json.loads(artifacts_out.read_text())
    assert artifacts["generator_abi_version"] == 2
    assert artifacts["svx_runtime_abi_version"] == runtime.SVX_RUNTIME_ABI_VERSION
    assert artifacts["svtypes"]["required_package_major"] == 1
    drive = next(
        call
        for call in artifacts["callables"]
        if call["canonical_id"] == "sv://tb_pkg/BaseDriver#drive"
    )
    assert drive["request_fields"][0]["name"] == "address"
    assert drive["request_record"]["unified_type_name"].startswith("svx.call.")
    assert drive["request_record"]["unified_type_name"].endswith(".request")
    assert drive["request_record"]["encoding_descriptor"]["encoding_fingerprint"]
    assert drive["request_record"]["sv_class"].endswith("_Request")
    assert artifacts["generated_types"] == [
        {
            "canonical_class_id": "py://checks/BaseMonitor",
            "python_adapter_fqn": "svx_py.checks.BaseMonitor",
            "systemverilog_fqn": "svx_proxy_checks::BaseMonitor",
        },
        {
            "canonical_class_id": "sv://tb_pkg/BaseDriver",
            "python_fqn": "svx_mirror.tb_pkg.BaseDriver",
        },
    ]
    assert drive["response_record"] is None
    assert artifacts["constructors"] == []
    assert artifacts["types"][0]["encoding_descriptor"]["encoding_fingerprint"]
    assert artifacts["inheritance_manifest"]["schema_version"] == "2.0.0"
    assert {entry["language"] for entry in artifacts["artifacts"]} == {
        "python",
        "systemverilog",
    }
    assert all(len(entry["sha256"]) == 64 for entry in artifacts["artifacts"])
    assert "svx_mirror/tb_pkg.py" in out.getvalue()
    (python_out / "checks.py").write_text("class BaseMonitor:\n    pass\n")
    runtime._load_artifact_manifest(
        artifacts_out,
        runtime.SvTypesCapabilities(
            package_major_version=1,
            schema_format_version=1,
            binary_format_version=1,
            object_envelope_version=1,
            generator_runtime_abi_version=1,
            provided=frozenset({
                "svtypes.checked-encoding-descriptor.v1",
                "svtypes.codec-context.v1",
                "svtypes.record-schema.v1",
                "svtypes.remote-reference.v1",
            }),
        ),
    )
    check_args = ["inheritance-gen", "--manifest", str(manifest_path),
                  "--python-out", str(python_out), "--sv-out", str(sv_out),
                  "--artifact-manifest", str(artifacts_out), "--check"]
    assert main(check_args, out=StringIO()) == 0
    sv_out.write_text(sv_out.read_text() + "// stale\n")
    with pytest.raises(SystemExit, match="artifacts are stale"):
        main(check_args, out=StringIO())


@pytest.mark.parametrize("failure", [
    "parent_file", "artifact_directory", "user_artifact", "metadata_render",
    "overlap", "ancestor_target", "record_field_loss",
])
def test_generation_preflight_failure_preserves_all_existing_artifacts(tmp_path, monkeypatch, failure):
    import svx.cli as cli

    manifest_path = tmp_path / "source.json"
    manifest_path.write_text(json.dumps(manifest_data()))
    python_out = tmp_path / "python"
    sv_out = tmp_path / "mirrors.sv"
    artifact_out = tmp_path / "artifacts.json"

    def arguments():
        return ["inheritance-gen", "--manifest", str(manifest_path),
                "--python-out", str(python_out), "--sv-out", str(sv_out),
                "--artifact-manifest", str(artifact_out)]

    assert main(arguments(), out=StringIO()) == 0
    old_adapter = python_out / "svx_py/checks.py"
    assert old_adapter.is_file()
    changed = manifest_data()
    changed["classes"] = changed["classes"][:1]
    changed["classes"][0]["methods"][0]["parameters"][0]["name"] = "updated_address"
    manifest_path.write_text(json.dumps(changed))
    if failure == "parent_file":
        blocked = tmp_path / "blocked"
        blocked.write_text("user file")
        artifact_out = blocked / "artifacts.json"
    elif failure == "artifact_directory":
        artifact_out = tmp_path / "directory"
        artifact_out.mkdir()
    elif failure == "user_artifact":
        artifact_out.write_text('{"user": "configuration"}')
    elif failure == "metadata_render":
        def fail(*args, **kwargs):
            raise SVXInheritanceError("metadata construction failed")
        monkeypatch.setattr(cli, "_generated_artifact_text", fail)
    elif failure == "overlap":
        sv_out = python_out / "svx_mirror/tb_pkg.py"
    elif failure == "ancestor_target":
        sv_out = tmp_path / "new_target"
        artifact_out = sv_out / "artifacts.json"
    else:
        changed["classes"][0]["methods"][0]["parameters"][0]["name"] = "_native"
        manifest_path.write_text(json.dumps(changed))
        # Keep this guard regression independent of a future dependency fix.
        from types import SimpleNamespace
        original = svtypes.schema_descriptor
        def incomplete(value):
            result = original(value).to_dict()
            result["schema"]["fields"] = [field for field in result["schema"]["fields"]
                                           if field["name"] != "_native"]
            return SimpleNamespace(to_dict=lambda: result)
        monkeypatch.setattr(svtypes, "schema_descriptor", incomplete)

    def snapshot():
        return {str(path.relative_to(tmp_path)):
                (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
                for path in tmp_path.rglob("*") if path.is_file()}

    before = snapshot()
    with pytest.raises(SVXInheritanceError):
        main(arguments(), out=StringIO())
    assert snapshot() == before
    assert old_adapter.is_file(), "failed preflight deleted an obsolete generated module"

def test_inheritance_gen_cli_writes_source_order_stages(tmp_path):
    manifest_path = tmp_path / "inheritance.json"
    manifest_path.write_text(json.dumps(manifest_data()))
    python_out = tmp_path / "python"
    stage_out = tmp_path / "stages"
    artifacts_out = tmp_path / "artifacts.json"

    assert main(
        [
            "inheritance-gen",
            "--manifest",
            str(manifest_path),
            "--python-out",
            str(python_out),
            "--sv-stage-dir",
            str(stage_out),
            "--artifact-manifest",
            str(artifacts_out),
        ],
        out=StringIO(),
    ) == 0
    assert (stage_out / "common.svh").is_file()
    artifacts = json.loads(artifacts_out.read_text())
    assert any(
        item["language"] == "systemverilog" and item["path"].endswith("stages/common.svh")
        for item in artifacts["artifacts"]
    )
    assert main(
        [
            "inheritance-gen",
            "--manifest",
            str(manifest_path),
            "--python-out",
            str(python_out),
            "--sv-stage-dir",
            str(stage_out),
            "--artifact-manifest",
            str(artifacts_out),
            "--check",
        ],
        out=StringIO(),
    ) == 0


@pytest.mark.parametrize("stage", [False, True])
@pytest.mark.parametrize("damage", ["missing", "empty", "incomplete", "reordered"])
def test_inheritance_check_rejects_damaged_inventory_without_writes(tmp_path, stage, damage):
    import copy

    manifest_path = tmp_path / "source.json"
    data = manifest_data()
    if stage:
        data["classes"][1]["base_lineage"] = [copy.deepcopy(data["classes"][0])]
    manifest_path.write_text(json.dumps(data))
    python_out = tmp_path / "python"
    sv_out = tmp_path / ("stages" if stage else "mirrors.sv")
    artifact_out = tmp_path / "artifacts.json"
    arguments = ["inheritance-gen", "--manifest", str(manifest_path),
                 "--python-out", str(python_out),
                 "--sv-stage-dir" if stage else "--sv-out", str(sv_out),
                 "--artifact-manifest", str(artifact_out)]
    assert main(arguments, out=StringIO()) == 0
    inventory = (sv_out / ".svx-generated-sv.json" if stage
                 else python_out / ".svx-generated-python.json")
    original = json.loads(inventory.read_text())
    assert len(original) > 1
    if damage == "missing":
        inventory.unlink()
    else:
        entries = [] if damage == "empty" else original[:-1] if damage == "incomplete" else original[::-1]
        inventory.write_text(json.dumps(entries, indent=2) + "\n")
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
              for path in tmp_path.rglob("*") if path.is_file()}
    with pytest.raises(SystemExit, match="artifacts are stale") as error:
        main([*arguments, "--check"], out=StringIO())
    assert str(inventory) in str(error.value)
    after = {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
             for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before


@pytest.mark.parametrize("stage", [False, True])
@pytest.mark.parametrize("state", ["clean", "modified", "wrong_hash", "outside", "symlink", "missing_metadata"])
def test_missing_inventory_recovers_only_verified_obsolete_artifacts(tmp_path, stage, state):
    import copy
    import hashlib

    data = manifest_data()
    if stage:
        data["classes"][1]["base_lineage"] = [copy.deepcopy(data["classes"][0])]
    manifest = tmp_path / "source.json"
    manifest.write_text(json.dumps(data))
    python = tmp_path / "python"
    sv = tmp_path / ("stages" if stage else "mirrors.sv")
    artifact = tmp_path / "artifacts.json"
    arguments = ["inheritance-gen", "--manifest", str(manifest), "--python-out", str(python),
                 "--sv-stage-dir" if stage else "--sv-out", str(sv),
                 "--artifact-manifest", str(artifact)]
    assert main(arguments, out=StringIO()) == 0
    output = sv if stage else python
    inventory = output / (".svx-generated-sv.json" if stage else ".svx-generated-python.json")
    old_paths = [output / relative for relative in json.loads(inventory.read_text())]
    changed = copy.deepcopy(data)
    changed["classes"] = changed["classes"][:1]
    manifest.write_text(json.dumps(changed))
    model = parse_manifest(changed)
    sources = emit_sv_mirror_stages(model) if stage else emit_python_mirrors(model)
    current = {output / path for path in sources}
    obsolete = [path for path in old_paths if path not in current]
    assert obsolete
    victim = obsolete[0]
    original = victim.read_bytes()
    inventory.unlink()
    unknown = output / "unrecorded_file.txt"
    unknown.write_bytes(original)
    metadata = json.loads(artifact.read_text())
    if state == "modified":
        victim.write_bytes(original + b"\n// user edit\n")
    elif state == "wrong_hash":
        entry = next(entry for entry in metadata["artifacts"]
                     if (artifact.parent / entry["path"]).resolve() == victim.resolve())
        entry["sha256"] = "0" * 64
    elif state == "outside":
        outside = tmp_path / "outside.txt"
        outside.write_bytes(original)
        metadata["artifacts"].append({"language": "systemverilog" if stage else "python",
                                      "path": "outside.txt", "sha256": hashlib.sha256(original).hexdigest()})
    elif state == "symlink":
        victim.unlink()
        victim.symlink_to(unknown)
    elif state == "missing_metadata":
        metadata.pop("artifacts")
    artifact.write_text(json.dumps(metadata, indent=2) + "\n")

    def snapshot():
        return {path: (path.read_bytes(), path.stat().st_mtime_ns, path.lstat().st_ino)
                for path in tmp_path.rglob("*") if path.is_file()}

    before = snapshot()
    if state in {"modified", "wrong_hash", "symlink", "missing_metadata"}:
        with pytest.raises(SVXInheritanceError, match="recover|recovered|artifact"):
            main(arguments, out=StringIO())
        assert snapshot() == before
        assert not inventory.exists()
    else:
        assert main(arguments, out=StringIO()) == 0
        assert all(not path.exists() for path in obsolete)
        assert unknown.read_bytes() == original
        if state == "outside":
            assert outside.read_bytes() == original
        assert main([*arguments, "--check"], out=StringIO()) == 0


def test_recovered_old_python_path_can_be_reassigned_to_sv_output(tmp_path):
    manifest = tmp_path / "source.json"
    data = manifest_data()
    manifest.write_text(json.dumps(data))
    python = tmp_path / "python"
    artifact = tmp_path / "artifacts.json"
    arguments = ["inheritance-gen", "--manifest", str(manifest), "--python-out", str(python),
                 "--artifact-manifest", str(artifact), "--sv-out"]
    assert main([*arguments, str(tmp_path / "mirrors.sv")], out=StringIO()) == 0
    reassigned = python / "svx_py/checks.py"
    assert reassigned.is_file()
    (python / ".svx-generated-python.json").unlink()
    data["classes"] = data["classes"][:1]
    manifest.write_text(json.dumps(data))
    assert main([*arguments, str(reassigned)], out=StringIO()) == 0
    assert reassigned.read_text().startswith("// Generated by svx inheritance-gen.")
    assert main([*arguments, str(reassigned), "--check"], out=StringIO()) == 0


def test_interrupted_recovered_retirement_can_be_retried_without_lost_ownership(tmp_path, monkeypatch):
    data = manifest_data()
    manifest = tmp_path / "source.json"
    manifest.write_text(json.dumps(data))
    python = tmp_path / "python"
    artifact = tmp_path / "artifacts.json"
    arguments = ["inheritance-gen", "--manifest", str(manifest), "--python-out", str(python),
                 "--sv-out", str(tmp_path / "mirrors.sv"), "--artifact-manifest", str(artifact)]
    assert main(arguments, out=StringIO()) == 0
    victim = python / "svx_py/checks.py"
    (python / ".svx-generated-python.json").unlink()
    data["classes"] = data["classes"][:1]
    manifest.write_text(json.dumps(data))
    previous_metadata = artifact.read_bytes()
    unlink = Path.unlink

    def fail_retirement(path, *args, **kwargs):
        if path == victim:
            raise OSError("injected obsolete retirement failure")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_retirement)
        with pytest.raises(OSError, match="injected obsolete retirement"):
            main(arguments, out=StringIO())
    assert (python / ".svx-generated-python.json").is_file()
    assert victim.is_file()
    assert artifact.read_bytes() == previous_metadata
    assert main(arguments, out=StringIO()) == 0
    assert not victim.exists()
    assert main([*arguments, "--check"], out=StringIO()) == 0


def test_internal_python_root_proxy_has_no_fabricated_sv_ancestor():
    from tests.integration.python_root_proxy_schema import emit_probe, manifest_data as root_manifest

    text = emit_probe()
    assert "class Root implements svx_dispatchable, svx_function_dispatchable;" in text
    assert "class Root extends" not in text
    assert "super.new(" not in text.split('  `include "tests/integration/python_root_child.svh"')[0]
    assert "svx_inheritance_registry::register_object" in text
    assert "svx_inheritance_create_python_function" in text
    assert "virtual function int check(input int delta)" in text
    root = parse_manifest(root_manifest()).classes[0]
    with pytest.raises(SVXInheritanceError, match="no fabricated SV ancestor"):
        inheritance._emit_sv_projection_class("Root", "invented::Base", root,
                                             base_methods=(), dispatch_virtuals=(),
                                             is_root_python_proxy=True)
    with pytest.raises(SVXInheritanceError, match="requires a Python-root constructor"):
        inheritance._emit_sv_projection_class("Root", None, root,
                                             base_methods=(), dispatch_virtuals=())


def test_internal_root_constructor_does_not_enable_unimplemented_public_chain():
    import copy
    from tests.integration.python_root_proxy_schema import manifest_data as root_manifest

    data = root_manifest()
    data["classes"].append({"canonical_id": "sv://root_child_pkg/C", "language": "sv",
                            "symbol": "root_child_pkg::C", "methods": [],
                            "base_lineage": [copy.deepcopy(data["classes"][0])]})
    model = parse_manifest(data)
    for emitter in (emit_sv_mirrors, emit_python_mirrors):
        with pytest.raises(SVXInheritanceError, match="construction/companion bridge integration"):
            emitter(model)


def test_multiple_targets_keep_ancestry_as_context_not_class_declaration_identity():
    from tests.integration.python_root_proxy_schema import probe_manifest_data

    model = parse_manifest(probe_manifest_data())
    declarations = inheritance._all_manifest_classes(model)
    assert len(declarations) == len(model.classes) == 6
    assert len({source.canonical_id for source in declarations}) == 6
    assert all(not source.base_lineage for source in declarations)
    assert len(model.classes[4].base_lineage) == 3


@pytest.mark.parametrize("conflict", ["member", "prefix"])
def test_multiple_targets_still_reject_real_declaration_or_prefix_conflicts(conflict):
    from tests.integration.python_root_proxy_schema import probe_manifest_data

    data = probe_manifest_data()
    if conflict == "member":
        data["classes"][3]["base_lineage"][1]["fields"][0]["name"] = "different_field"
        expected = "description.*differs"
    else:
        data["classes"][3]["base_lineage"] = data["classes"][3]["base_lineage"][:1]
        expected = "ancestry prefix.*differs"
    with pytest.raises(SVXInheritanceError, match=expected):
        parse_manifest(data)


def test_target_only_context_plans_each_source_without_emitting_ancestor_classes():
    from tests.integration.python_root_proxy_schema import probe_manifest_data, ROOT_ID, DERIVED_ID

    data = probe_manifest_data()
    data["classes"] = [data["classes"][4]]
    model = parse_manifest(data)
    target = model.classes[0]
    root, child, derived = target.base_lineage
    child_plan = inheritance._python_root_construction_plan(child, manifest=model)
    target_plan = inheritance._python_root_construction_plan(target, manifest=model)
    assert child_plan.root.canonical_id == ROOT_ID and child_plan.python_portions == ()
    assert tuple(source.canonical_id for source in target_plan.python_portions) == (DERIVED_ID,)
    assert target_plan.preceding_python.canonical_id == DERIVED_ID
    source = inheritance._emit_planned_python_root_sv_view(model, target,
                                                         companion_modules={DERIVED_ID: "generated_derived"})
    assert source.count("class Grandchild(") == 1
    assert f"{child.canonical_id!r}: {DERIVED_ID!r}" in source
    assert "def __svx_dispatch_foreign__" not in source
    assert "class Root(" not in source and "class Derived(" not in source and "class Child(" not in source
    lines = inheritance._emit_planned_python_root_sv_projection(model, target,
                                                              generated_name="GrandchildMirror", base_type="Grandchild")
    text = "\n".join(lines)
    assert text.count("class GrandchildMirror ") == 1
    assert "class Root " not in text and "class DerivedProxy " not in text
    companion = inheritance._emit_planned_python_root_companion(model, derived)
    assert companion.count("class Derived(") == 1 and "class Root(" not in companion
    assert len(model.classes) == 1 and model.classes[0] is target


def test_python_root_proxy_reuses_inherited_virtual_bridge_but_emits_new_method():
    from copy import deepcopy
    from tests.integration.python_root_proxy_schema import probe_manifest_data

    data = probe_manifest_data()
    new_method = deepcopy(data["classes"][3]["methods"][0])
    new_method["name"] = "new_check"
    new_method["canonical_id"] = data["classes"][3]["canonical_id"] + "#new_check"
    data["classes"][3]["methods"].append(new_method)
    # Keep repeated declarations complete and consistent in all descendants.
    for target in data["classes"][4:]:
        for ancestor in target["base_lineage"]:
            if ancestor["canonical_id"] == data["classes"][3]["canonical_id"]:
                ancestor["methods"].append(deepcopy(new_method))
    model = parse_manifest(data)
    derived = model.classes[3]
    text = "\n".join(inheritance._emit_planned_python_root_sv_projection(
        model, derived, generated_name="DerivedProxy", base_type="ChildMirror"))
    assert "virtual function int check(" not in text
    assert "virtual function int new_check(" in text
    assert 'py://tests/integration/python_root/Derived#new_check' in text
    assert 'py://tests/integration/python_root/Derived#check' not in text


def test_planned_view_requires_predictable_preceding_companion_location():
    from tests.integration.python_root_proxy_schema import probe_manifest_data

    model = parse_manifest(probe_manifest_data())
    with pytest.raises(SVXInheritanceError, match="missing generated Python companion module"):
        inheritance._emit_planned_python_root_sv_view(model, model.classes[4], companion_modules={})


def test_python_root_artifact_layout_is_derived_without_user_module_mapping():
    import ast
    from pathlib import PurePosixPath
    from tests.integration.python_root_proxy_schema import probe_manifest_data

    model = parse_manifest(probe_manifest_data())
    sources = inheritance._emit_python_root_artifacts(model)
    root_path = PurePosixPath("svx_py/tests/integration/python_root_proxy_test.py")
    derived_path = PurePosixPath("svx_py/tests/integration/python_root_derived.py")
    mirror_path = PurePosixPath("svx_mirror/python_root_probe_pkg.py")
    assert "class Root(" in sources[root_path] and "class PlainRoot(" in sources[root_path]
    assert "class Derived(" in sources[derived_path]
    assert "class Child(" in sources[mirror_path] and "class Grandchild(" in sources[mirror_path]
    assert "from svx_py.tests.integration.python_root_proxy_test import Root" in sources[mirror_path]
    assert "from svx_py.tests.integration.python_root_derived import Derived" in sources[mirror_path]
    assert PurePosixPath("svx_py/tests/integration/python_root_final.py") not in sources
    for path, text in sources.items():
        compile(ast.parse(text), str(path), "exec")
    metadata = inheritance.artifact_manifest(model, sources, "// internal SV fixture\n")
    types = {entry["canonical_class_id"]: entry for entry in metadata["generated_types"]}
    assert types[model.classes[0].canonical_id]["python_adapter_fqn"] == "svx_py.tests.integration.python_root_proxy_test.Root"
    assert types[model.classes[3].canonical_id]["python_adapter_fqn"] == "svx_py.tests.integration.python_root_derived.Derived"
    assert model.classes[5].canonical_id not in types


@pytest.mark.parametrize("kind", ["member", "prefix", "root"])
def test_global_ancestor_conflict_is_rejected_even_without_ancestor_targets(kind):
    from tests.integration.lineage_context_probe import conflicting_branch

    expected = "conflicting lineage declarations" if kind == "member" else "conflicting lineage ancestry"
    with pytest.raises(SVXInheritanceError, match=expected):
        parse_manifest(conflicting_branch(kind))


def test_global_declaration_conflict_names_targets_and_changed_members():
    from tests.integration.lineage_context_probe import conflicting_branch

    data = conflicting_branch("member")
    with pytest.raises(SVXInheritanceError) as error:
        parse_manifest(data)
    message = str(error.value)
    assert all(target["canonical_id"] in message for target in data["classes"])
    assert "differing declaration fields: fields" in message


def test_global_context_failure_preserves_real_generated_artifacts():
    from tests.integration.lineage_context_probe import run_probe

    run_probe()


def test_planned_emitter_cannot_materialize_a_source_outside_manifest_context():
    from dataclasses import replace
    from tests.integration.python_root_proxy_schema import probe_manifest_data

    model = parse_manifest(probe_manifest_data())
    outside = replace(model.classes[2], canonical_id="sv://outside/Unrequested")
    with pytest.raises(SVXInheritanceError, match="construction source is missing or differs"):
        inheritance._emit_planned_python_root_sv_projection(model, outside,
                                                           generated_name="Unrequested", base_type="Child")


def test_remote_error_preserves_dispatch_identity(monkeypatch):
    from svx.inheritance import call_sv

    def fail(*_args):
        raise RuntimeError("SVX1|unknown_object|41|sv://pkg/Base#run|unknown object")

    monkeypatch.setattr("svx._native.inheritance_call_sv", fail)
    with pytest.raises(SVXRemoteError) as raised:
        call_sv(41, "sv://pkg/Base#run")
    assert raised.value.object_id == 41
    assert raised.value.method_id == "sv://pkg/Base#run"
    assert raised.value.remote_message == "unknown object"
    assert raised.value.code == "unknown_object"


def test_custom_svtypes_object_null_uses_generated_record():
    from tests.fixtures.object_types import Packet

    packet = type_ref(
        Packet,
        module="tests.fixtures.object_types",
        symbol="Packet",
        sv="Packet",
        sv_packer="svtypes_pkg::object_packer#(Packet)",
    )
    class_id = "sv://codec/NullablePacketConstructor"
    register_constructor(class_id, (("packet", packet),))
    payload = encode_constructor(class_id, {"packet": None})
    assert payload.startswith(b"\x01")


def test_manifest_migration_upgrades_legacy_scalar_types():
    data = manifest_data()
    parameter = data["classes"][0]["methods"][0]["parameters"][0]
    parameter["type"] = "bit"
    migrated = migrate_manifest(data)
    migrated_parameter = migrated["classes"][0]["methods"][0]["parameters"][0]
    assert migrated_parameter["type"]["svtypes"] == {
        "kind": "specialization",
        "base": {"kind": "packed", "name": "Bit"},
        "args": [1, {"kind": "signedness", "value": "unsigned"}],
    }
    assert migrated["schema_version"] == "2.0.0"


def test_manifest_migration_upgrades_legacy_python_factory_types():
    data = manifest_data()
    migrated = migrate_manifest(data)
    parameter = migrated["classes"][0]["methods"][0]["parameters"][0]
    assert parameter["type"]["svtypes"] == {"kind": "scalar", "name": "Int"}
    assert "python" not in parameter["type"]


def test_remote_ref_is_resolved_and_type_checked_by_svx(monkeypatch):
    from svtypes import RemoteRef, RemoteRefValue

    reference = type_ref(
        RemoteRef,
        args=("sv://tb_pkg/BaseDriver",),
        sv="svtypes_pkg::remote_ref_value",
        sv_packer="svtypes_pkg::remote_ref_packer",
    )

    class Driver:
        __svx_foreign_class_ids__ = ("sv://tb_pkg/BaseDriver",)

    monkeypatch.setattr(
        "svx._native.inheritance_get",
        lambda object_id: Driver() if object_id == 17 else None,
    )
    class_id = "sv://codec/RemoteRefConstructor"
    register_constructor(class_id, (("reference", reference),))
    payload = encode_constructor(
        class_id,
        {"reference": RemoteRefValue("sv://tb_pkg/BaseDriver", 17)},
    )
    assert payload.startswith(b"\x01")

    with pytest.raises(SVXInheritanceError, match="unknown or stale"):
        encode_constructor(
            class_id,
            {"reference": RemoteRefValue("sv://tb_pkg/BaseDriver", 18)},
        )


def test_nested_remote_ref_is_resolved_from_public_schema(monkeypatch):
    from svtypes import RemoteRef, RemoteRefValue, SvObject

    class RefEnvelope(SvObject):
        reference = RemoteRef["sv://tb_pkg/BaseDriver"]()

    monkeypatch.setattr(sys.modules[__name__], "RefEnvelope", RefEnvelope, raising=False)

    envelope_type = type_ref(
        RefEnvelope,
        module=__name__,
        symbol="RefEnvelope",
        sv="RefEnvelope",
        sv_packer="svtypes_pkg::object_packer#(RefEnvelope)",
    )

    class Driver:
        __svx_foreign_class_ids__ = ("sv://tb_pkg/BaseDriver",)

    monkeypatch.setattr(
        "svx._native.inheritance_get",
        lambda object_id: Driver() if object_id == 27 else None,
    )
    class_id = "sv://codec/NestedRemoteRefConstructor"
    register_constructor(class_id, (("envelope", envelope_type),))
    envelope = RefEnvelope(session=runtime.codec_session())
    envelope.reference.value = RemoteRefValue("sv://tb_pkg/BaseDriver", 27)
    assert encode_constructor(class_id, {"envelope": envelope}).startswith(b"\x01")

    envelope.reference.value = RemoteRefValue("sv://tb_pkg/BaseDriver", 28)
    with pytest.raises(SVXInheritanceError, match="unknown or stale"):
        encode_constructor(class_id, {"envelope": envelope})


class _FakeRecordSchema:
    def __init__(self, *, unified_type_name, fields):
        self.unified_type_name = unified_type_name
        self.fields = fields
        self.value_type = make_dataclass(
            unified_type_name.rsplit(".", 1)[-1].title() + "Value",
            [(name, object) for name, _ in fields],
            frozen=True,
        )

    def pack(self, value, _context=None):
        return b"".join(codec.pack(getattr(value, name)) for name, codec in self.fields)

    def unpack(self, payload, _context=None):
        values = {}
        offset = 0
        for name, codec in self.fields:
            value, consumed = codec.unpack(payload[offset:])
            values[name] = value
            offset += consumed
        return self.value_type(**values), offset


def _install_fake_record_schema(monkeypatch):
    from types import SimpleNamespace

    original_descriptor = svtypes.schema_descriptor

    def descriptor(value_type):
        fields = getattr(value_type, "__dataclass_fields__", None)
        if fields is None:
            return original_descriptor(value_type)
        return SimpleNamespace(to_dict=lambda: {
            "schema": {"fields": [{"name": name} for name in fields]}
        })

    monkeypatch.setattr(svtypes, "RecordSchema", _FakeRecordSchema, raising=False)
    monkeypatch.setattr(svtypes, "schema_descriptor", descriptor)


def test_generated_call_records_cover_result_and_copyout(monkeypatch):
    _install_fake_record_schema(monkeypatch)
    result_method = "sv://codec/Target#add_one"
    copyout_method = "sv://codec/Target#exchange"
    register_contract(
        {
            result_method: {
                "parameters": (("value", "input", INT),),
                "request": (("value", INT),),
                "response": (("result", INT),),
            },
            copyout_method: {
                "parameters": (("changed", "inout", INT), ("observed", "output", INT)),
                "request": (("changed", INT),),
                "response": (("changed", INT), ("observed", INT)),
            },
        }
    )

    def remote_call(_object_id, method_id, payload):
        if method_id == result_method:
            value = int.from_bytes(payload, "little")
            return (value + 1).to_bytes(4, "little")
        assert payload == (7).to_bytes(4, "little")
        return (8).to_bytes(4, "little") + (19).to_bytes(4, "little")

    monkeypatch.setattr("svx._native.inheritance_call_sv", remote_call)
    assert invoke_sv(4, result_method, {"value": 9}) == 10
    changed = Inout(7)
    observed = Output()
    assert invoke_sv(4, copyout_method, {"changed": changed, "observed": observed}) is None
    assert (changed.value, observed.value) == (8, 19)


def test_runtime_rejects_legacy_ref_call_contracts():
    with pytest.raises(SVXInheritanceError, match="must contain parameters"):
        register_contract(
            {
                "sv://codec/Target#legacy_ref": {
                    "request": (("value", INT),),
                    "response": (("value", INT),),
                    "refs": (("value", "readwrite"),),
                }
            }
        )


def test_python_callback_uses_copyout_carriers_and_a_normal_return(monkeypatch):
    _install_fake_record_schema(monkeypatch)
    method_id = "sv://codec/Target#exchange_callback"
    register_contract(
        {
            method_id: {
                "parameters": (("changed", "inout", INT), ("observed", "output", INT)),
                "request": (("changed", INT),),
                "response": (("changed", INT), ("observed", INT)),
            }
        }
    )
    class Target:
        def exchange_callback(self, changed, observed):
            changed.value += 1
            observed.value = 23
            return None

    monkeypatch.setattr("svx._native.inheritance_get", lambda _object_id: Target())
    payload = (4).to_bytes(4, "little")
    assert dispatch_python_call(2, method_id, payload) == (
        (5).to_bytes(4, "little") + (23).to_bytes(4, "little")
    )


def test_real_svtypes_record_schema_round_trip(monkeypatch):
    method_id = "sv://codec/Target#real_record_add"
    register_contract(
        {
            method_id: {
                "parameters": (("value", "input", INT),),
                "request": (("value", INT),),
                "response": (("result", INT),),
            }
        }
    )

    class Target:
        def real_record_add(self, value):
            return value + 3

    monkeypatch.setattr("svx._native.inheritance_get", lambda _object_id: Target())
    monkeypatch.setattr(
        "svx._native.inheritance_call_sv",
        lambda object_id, incoming_method_id, payload: dispatch_python_call(
            object_id, incoming_method_id, payload
        ),
    )
    assert invoke_sv(7, method_id, {"value": 11}) == 14


def test_real_svtypes_copyout_record_round_trip(monkeypatch):
    method_id = "sv://codec/Target#real_record_exchange"
    register_contract(
        {
            method_id: {
                "parameters": (("changed", "inout", INT), ("observed", "output", INT)),
                "request": (("changed", INT),),
                "response": (("changed", INT), ("observed", INT)),
            }
        }
    )
    class Target:
        def real_record_exchange(self, changed, observed):
            changed.value += 1
            observed.value = 31
            return None

    monkeypatch.setattr("svx._native.inheritance_get", lambda _object_id: Target())
    monkeypatch.setattr(
        "svx._native.inheritance_call_sv",
        lambda object_id, incoming_method_id, payload: dispatch_python_call(
            object_id, incoming_method_id, payload
        ),
    )
    changed = Inout(4)
    observed = Output()
    assert invoke_sv(9, method_id, {"changed": changed, "observed": observed}) is None
    assert changed.value == 5
    assert observed.value == 31


def test_real_svtypes_constructor_record_round_trip():
    class_id = "sv://codec/Constructed"
    register_constructor(class_id, (("seed", INT), ("name", STRING)))
    observed = []

    class Constructed:
        @classmethod
        def __svx_create_from_sv__(cls, object_id, seed, name):
            observed.append((object_id, seed, name))

    register_python_subclass(class_id, Constructed)
    payload = encode_constructor(class_id, {"seed": 13, "name": "counter"})
    create_python_instance(class_id, 22, payload)
    assert observed == [(22, 13, "counter")]


def test_generated_python_root_factory_encapsulates_typed_constructor():
    data = manifest_data()
    root = data["classes"][1]
    root["constructor"] = {
        "initiator": "python", "parameters": [{"name": "seed", "type": INT}]
    }
    source = emit_sv_mirrors(parse_manifest(data))
    assert "class BaseMonitorFactory #(type Implementation = BaseMonitor)" in source
    assert "constructor_request = BaseMonitor::svx_decode_constructor_request(request);" in source
    assert "Implementation svx_instance;" in source
    assert "svx_instance = new(object_id, constructor_request.seed);" in source
    assert 'svx_inheritance_registry::register_factory("py://checks/BaseMonitor", this);' in source


def test_generated_python_root_factory_is_standard_sv_syntax():
    from pyslang.syntax import SyntaxTree

    data = manifest_data()
    data["classes"][1]["constructor"] = {"initiator": "python", "parameters": []}
    cls = parse_manifest(data).classes[1]
    factory = "\n".join(inheritance._emit_sv_implementation_factory(cls))
    assert not list(SyntaxTree.fromText(factory).diagnostics)


def test_projection_constructor_locals_and_bridge_id_avoid_user_formals():
    data = manifest_data()
    source = data["classes"][0]
    names = ("object_id", "svx_object_id", "ok", "request", "error", "bytes",
             "request_value", "__svx_remote_object_id")
    source["constructor"] = {
        "initiator": "python", "parameters": [{"name": name, "type": INT} for name in names]
    }
    cls = parse_manifest(data).classes[0]
    generated = "\n".join(inheritance._emit_sv_projection_class(
        "BaseDriver", cls.symbol, cls, base_methods=(), dispatch_virtuals=(),
        is_root_sv_mirror=True,
    ))
    assert f"super.new({', '.join(names)});" in generated
    assert "input int object_id" in generated
    assert "input longint unsigned svx_object_id_1 = 0" in generated
    assert "bit svx_ok;" in generated
    assert "chandle svx_request;" in generated
    assert "byte unsigned svx_bytes[$];" in generated
    assert "svx_request_value.request_value = request_value;" in generated
    assert "this.__svx_remote_object_id = svx_object_id_1;" in generated


def test_constructor_handle_generation_preserves_native_types_and_decodes_both_factories():
    from tests.integration.constructor_handles_schema import manifest_data as handle_manifest

    model = parse_manifest(handle_manifest())
    sv = emit_sv_mirrors(model)
    assert "input external_handle_test_pkg::Packet packet, input virtual external_bus_if.master vif" in sv
    packet_adapter = "SVXExternal_sv___external_handle_test_pkg_Packet"
    vif_adapter = "SVXExternal_sv_vif___external_bus_if_master"
    assert f"request_value.packet = {packet_adapter}::encode(packet);" in sv
    assert f"request_value.vif = {vif_adapter}::encode(vif);" in sv
    assert sv.count(f"if (!{packet_adapter}::decode(constructor_request.packet, packet, error))") == 2
    assert sv.count(f"if (!{vif_adapter}::decode(constructor_request.vif, vif, error))") == 2
    assert "instance = new(packet, vif, object_id);" in sv
    assert "instance = new(object_id, packet, vif);" in sv
    python = emit_python_mirrors(model)
    assert "svx_mirror/external_handle_test_pkg.py" not in {str(path) for path in python}
    for module in ("svx_mirror/constructor_handle_pkg.py", "svx_py/tests/integration/constructor_handles_user.py"):
        text = python[Path(module)]
        assert "external_targets=('sv://external_handle_test_pkg/Packet', 'sv-vif://external_bus_if/master')" in text
        compile(text, module, "exec")


def test_real_constructor_external_vif_reference_is_decoded_before_python_init(monkeypatch):
    import svx.inheritance as implementation

    target = "sv-vif://constructor_unit_if/master"
    reference = type_ref(RemoteRef, sv="svtypes_pkg::remote_ref",
                         sv_packer="svtypes_pkg::remote_ref_packer", args=(target,))
    class_id = "sv://constructor_unit/Holder"
    monkeypatch.setattr(implementation, "_constructor_contracts", {})
    monkeypatch.setattr(implementation, "_external_handle_targets", set())
    monkeypatch.setattr(implementation, "_vif_views", {})
    monkeypatch.setattr(implementation, "_python_subclasses", {})
    implementation.register_constructor(class_id, (("vif", reference),), external_targets=(target,))
    observed = []

    class View:
        _svx_vif_target_type_name = target

        def __init__(self, value):
            self._svx_remote_reference = value

    class Target:
        @classmethod
        def __svx_create_from_sv__(cls, object_id, vif):
            observed.append((object_id, vif))

    implementation.register_vif_view(target, View)
    register_python_subclass(class_id, Target)
    raw = svtypes.RemoteRefValue(target, 731)
    payload = encode_constructor(class_id, {"vif": View(raw)})
    create_python_instance(class_id, 22, payload)
    assert observed[0][0] == 22
    assert isinstance(observed[0][1], View)
    assert observed[0][1]._svx_remote_reference == raw
    with pytest.raises(SVXInheritanceError, match="tuple of strings"):
        implementation.register_constructor(class_id, (("vif", reference),), external_targets=[target])


def test_constructor_vif_without_operations_still_has_a_transport_view(monkeypatch):
    from tests.integration.constructor_handles_schema import manifest_data as handle_manifest

    data = handle_manifest()
    data["classes"][0]["constructor"]["parameters"][1]["handle"]["operations"] = []
    model = parse_manifest(data)
    sources = emit_python_mirrors(model)
    source = sources[Path("svx_vif/external_bus_if/master.py")]
    monkeypatch.setattr(inheritance, "_vif_views", {})
    namespace = {}
    exec(compile(source, "empty_vif_view.py", "exec"), namespace)
    raw = svtypes.RemoteRefValue("sv-vif://external_bus_if/master", 731)
    view = inheritance._decode_vif_view(raw)
    assert isinstance(view, namespace["Master"])
    assert not hasattr(view, "read")
    assert inheritance._encode_vif_view(view) == raw


def test_generated_python_root_factory_rejects_class_name_collision():
    data = manifest_data()
    data["classes"][1]["constructor"] = {"initiator": "python", "parameters": []}
    data["classes"].append({
        "canonical_id": "py://checks/BaseMonitorFactory",
        "language": "python", "symbol": "checks.BaseMonitorFactory", "methods": [],
    })
    with pytest.raises(SVXInheritanceError, match="factory name collision"):
        emit_sv_mirrors(parse_manifest(data))


def test_alternating_artifact_manifest_covers_generated_ancestor_contracts():
    from pathlib import Path

    model = parse_manifest(json.loads(Path("tests/integration/alternating_chain_manifest.json").read_text()))
    metadata = inheritance.artifact_manifest(model, emit_python_mirrors(model), emit_sv_mirrors(model))
    assert metadata["classes"] == ["py://tests/integration/alternating_chain/D"]
    names = {item["canonical_class_id"]: item for item in metadata["generated_types"]}
    assert names["sv://chain_pkg/A"]["python_fqn"] == "svx_mirror.chain_pkg.A"
    assert names["sv://chain_user_pkg/C"]["python_fqn"] == "svx_mirror.chain_user_pkg.C"
    assert names["py://tests/integration/alternating_chain/B"]["systemverilog_fqn"] == "svx_proxy_alternating_chain_test::B"
    assert set(names) == {"sv://chain_pkg/A", "sv://chain_user_pkg/C", "py://tests/integration/alternating_chain/B"}
    assert {item["canonical_id"] for item in metadata["callables"]} == {
        "py://tests/integration/alternating_chain/B#base_check",
        "py://tests/integration/alternating_chain/B#b_check",
        "sv://chain_pkg/A#base_check", "sv://chain_user_pkg/C#c_check",
        "sv://chain_user_pkg/C#trigger_base_check",
    }
    assert {item["canonical_class_id"] for item in metadata["constructors"]} == {
        "sv://chain_pkg/A", "sv://chain_user_pkg/C", "py://tests/integration/alternating_chain/D",
    }
    assert {item["unified_type_name"] for item in metadata["types"]} == {"svtypes.Int"}

    python_files = emit_python_mirrors(model)
    base_module = python_files[next(path for path in python_files if str(path) == "svx_mirror/chain_pkg.py")]
    assert "'py://tests/integration/alternating_chain/B#b_check':" in base_module
    assert "class B(" not in base_module
    bproxy = emit_sv_mirrors(model).split("class B extends A", 1)[1].split("endclass : B", 1)[0]
    assert "virtual task b_check(" in bproxy
    assert "virtual task base_check(" not in bproxy
    assert '"sv://chain_pkg/A#base_check":' not in bproxy


def test_native_handle_fields_preserve_metadata_and_use_typed_endpoints():
    from tests.integration.constructor_handles_schema import manifest_data as handles_manifest
    from svx.declarations import _class_declaration

    data = handles_manifest()
    # Endpoint generation must not depend on a second use in a method/constructor.
    data["classes"] = [data["classes"][0]]
    data["classes"][0]["constructor"] = {"initiator": "python", "parameters": []}
    model = parse_manifest(data)
    cls = model.classes[0]
    assert len(inheritance._manifest_handle_bindings(model)) == 2
    assert tuple(inheritance._parse_field(raw, "roundtrip.field")
                 for raw in _class_declaration(cls)["fields"]) == cls.fields
    source = emit_sv_mirrors(model)
    for field in cls.fields:
        adapter = inheritance._handle_adapter_name(field.handle)
        assert f"{adapter}::encode(this.{field.name})" in source
        assert f"{adapter}::decode(field_wire, field_native, error)" in source
        assert f'field_wire = new("{field.handle.target_type_name}");' in source
        assert f"this.{field.name} = field_native;" in source
        assert f"::unpack({field.name}," not in source
        assert inheritance._sv_field_declaration(field) == f"{field.handle.sv_type} {field.name}"
    invalid = handles_manifest()
    invalid["classes"][0]["fields"][0]["handle"]["target_type_name"] = "sv://wrong/Packet"
    with pytest.raises(SVXInheritanceError):
        parse_manifest(invalid)


@pytest.mark.parametrize("static", [False, True])
def test_inheritance_cancellation_is_not_remote_error_or_copyout(monkeypatch, static):
    from svx.errors import SVXCancellationError
    from tests.integration.inheritance_disable_schema import manifest_data as disable_manifest

    model = parse_manifest(disable_manifest())
    method = model.classes[0].methods[1 if static else 0]
    monkeypatch.setattr(inheritance, "_method_contracts", {})
    register_contract({method.canonical_id: inheritance._contract_data(method)})
    cancelled = SVXCancellationError("disabled task")

    def interrupted(*args, **kwargs):
        raise cancelled

    monkeypatch.setattr("svx._native.inheritance_call_sv_static" if static else
                        "svx._native.inheritance_call_sv", interrupted)
    changed, observed = Inout(10), Output()
    with pytest.raises(SVXCancellationError) as caught:
        if static:
            inheritance.invoke_sv_static(model.classes[0].canonical_id, method.canonical_id,
                                         {"changed": changed, "observed": observed})
        else:
            invoke_sv(1, method.canonical_id, {"changed": changed, "observed": observed})
    assert caught.value is cancelled
    assert changed.value == 10
    with pytest.raises(SVXInheritanceError, match="not available"):
        observed.value


def test_void_function_with_output_named_result_preserves_prototype(monkeypatch):
    method_id = "sv://codec/ResultOutput#observe"
    register_contract({method_id: {
        "timing": "function", "parameters": (("result", "output", INT),),
        "request": (), "response": (("result", INT),),
    }})

    class Target:
        def observe(self, result):
            result.value = 29

    monkeypatch.setattr("svx._native.inheritance_get", lambda _object_id: Target())
    monkeypatch.setattr("svx._native.inheritance_call_sv", lambda object_id, name, payload, **_: dispatch_python_call(object_id, name, payload))
    output = Output()
    assert invoke_sv(7, method_id, {"result": output}) is None
    assert output.value == 29


def test_generated_void_function_callback_has_function_termination():
    from tests.integration.parameterized_mirror_schema import manifest_data as parameterized_manifest

    source = emit_sv_mirrors(parse_manifest(parameterized_manifest()))
    method = source.split("virtual function void observe(output int result);", 1)[1].split("    endfunction", 1)[0]
    assert "svx_inheritance_call_python_function" in method
    assert "endtask" not in method


def test_generated_method_locals_avoid_formals_without_changing_signature():
    from tests.integration.parameterized_mirror_schema import manifest_data as parameterized_manifest

    model = parse_manifest(parameterized_manifest())
    method = next(m for m in model.classes[0].methods if m.name == "collisions")
    source = "\n".join(inheritance._emit_sv_outbound_method(method))
    assert "input int ok, input int request, input int response" in source
    assert "output int result" in source
    assert "bit svx_ok_1;" in source
    assert "chandle svx_request;" in source
    assert "int svx_result;" in source
    case = "\n".join(inheritance._emit_sv_dispatch_case(method, "super."))
    assert "int svx_ok;" in case
    assert "int svx_svx_ok;" in case
    assert "ok = 1;" in case
    assert "response_value.result = result;" in case or "svx_response_value.result = result;" in case


@pytest.mark.parametrize("slot_formals", [(), ("svx_return_value",),
                                        ("svx_return_value", "svx_return_value_1")])
def test_generated_function_return_artifact_passes_startup_validation(tmp_path, monkeypatch, slot_formals):
    data = manifest_data()
    data["classes"] = [data["classes"][0]]
    data["classes"][0]["methods"][0]["return_type"] = INT
    data["classes"][0]["methods"][0]["timing"] = "function"
    data["classes"][0]["methods"][0]["parameters"] = [
        {"name": name, "type": INT, "direction": "output"} for name in slot_formals
    ]
    model = parse_manifest(data)
    python = emit_python_mirrors(model)
    sv = emit_sv_mirrors(model)
    for relative, content in python.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    (tmp_path / "mirrors.sv").write_text(sv)
    metadata = inheritance.artifact_manifest(model, python, sv)
    path = tmp_path / "artifacts.json"
    path.write_text(json.dumps(metadata))
    original_import = runtime.importlib.import_module
    monkeypatch.setattr(runtime.importlib, "import_module", lambda name: (
        ModuleType(name) if name.startswith("svx_mirror") else original_import(name)
    ))
    runtime._load_artifact_manifest(path, runtime._read_svtypes_capabilities())
    call = metadata["callables"][0]
    slot = inheritance._return_slot_name(slot_formals)
    assert call["response_fields"][-1]["name"] == slot
    method = model.classes[0].methods[0]
    assert f".{slot} = " in "\n".join(inheritance._emit_sv_dispatch_case(method))
    contract = inheritance._contract_data(method)
    monkeypatch.setattr(inheritance, "_method_contracts", {})
    register_contract({method.canonical_id: contract})
    holders = {name: Output() for name in slot_formals}
    response = {name: Int(index + 4) for index, name in enumerate(slot_formals)}
    response[slot] = Int(29)
    normalized = inheritance._method_contracts[method.canonical_id]
    schema = inheritance._contract_schema(normalized, method.canonical_id, "response")
    record = inheritance._record_value(schema, normalized.response_fields, response)
    record = inheritance._unpack_call_record(schema, inheritance._pack_call_record(schema, record))
    result = inheritance._consume_call_response(
        normalized, method.canonical_id, record, holders
    )
    assert int(result) == 29
    assert [int(holder.value) for holder in holders.values()] == list(range(4, 4 + len(slot_formals)))
    call["response_fields"].append({"name": "result", "direction": "return", "unified_type_name": "svtypes.Int"})
    path.write_text(json.dumps(metadata))
    with pytest.raises(runtime.SVXError, match="multiple return fields"):
        runtime._load_artifact_manifest(path, runtime._read_svtypes_capabilities())
