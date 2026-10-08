import pytest

from svtypes import ExternalStorageError, Int, SvObject, svobj
from svx import SVXInheritanceError
from svx.declarations import _PythonRootOwner
from svx.field_storage import SVXFieldStorage


@svobj
class Root(SvObject):
    count = Int()
    local = Int()
    observations = []
    fail = False

    def __init__(self, seed):
        super().__init__()
        self.observations.append((self, self.count.value))
        self.count.value = seed
        self.local.value = 7
        if self.fail:
            raise ValueError("root initialization failed")

    def check(self, delta):
        return self.count.value + delta

    def fixed(self, delta):
        return self.count.value + delta + 200

    @staticmethod
    def scale(delta):
        return delta * 3

    @staticmethod
    def wait_once():
        import svx
        svx.delay(1, "ns")


class RootCompanion(Root, _PythonRootOwner):
    __svx_root_field_ids__ = {"count": "py://root/Root.count"}


class Transport:
    def __init__(self):
        self.payload = Int().pack(19)
        self.writes = []

    def read_field(self, object_id, field_id, descriptor, path):
        assert object_id == 91
        return self.payload

    def write_field(self, object_id, field_id, descriptor, path, operation, payload):
        self.writes.append((object_id, field_id, operation))
        self.payload = payload


@pytest.fixture
def environment(monkeypatch):
    Root.observations.clear()
    transport = Transport()
    bindings = {}
    retired = []

    def bind(object_id, instance):
        if object_id in bindings:
            raise ValueError("already bound")
        bindings[object_id] = instance

    def unbind(object_id):
        retired.append(bindings.pop(object_id))

    monkeypatch.setattr("svx.inheritance.bind_instance", bind)
    monkeypatch.setattr("svx.inheritance.unbind_instance", unbind)
    monkeypatch.setattr("svx.field_storage.SVXFieldStorage", lambda: SVXFieldStorage(transport))
    return transport, bindings, retired


def test_root_companion_binds_before_user_fields_and_keeps_plain_instances_local(environment):
    transport, bindings, retired = environment
    companion = RootCompanion.__svx_create_from_sv__(91, 23)
    assert Root.observations == [(companion, 19)]
    assert bindings == {91: companion}
    assert companion.count.value == 23
    assert companion.local.value == 7
    assert transport.writes == [(91, "py://root/Root.count", "set")]
    assert companion.svtypes_auto_cov.instantiated
    identity = companion.svtypes_object_number
    backend = companion._svx_field_storage
    # Later generated portions may reach the common owner but must not reset it.
    _PythonRootOwner.__init__(companion)
    assert companion.svtypes_object_number == identity
    assert companion._svx_field_storage is backend
    assert companion.count.value == 23
    local = Root(31)
    assert local.count.value == 31
    assert Int().unpack(transport.payload)[0] == 23
    retained = companion.count
    companion._svx_release_projected_fields()
    with pytest.raises(ExternalStorageError):
        retained.value
    assert companion.local.value == 7
    assert retired == []


def test_failed_root_initializer_retires_only_its_own_binding(environment, monkeypatch):
    transport, bindings, retired = environment
    monkeypatch.setattr(Root, "fail", True)
    with pytest.raises(ValueError, match="root initialization failed"):
        RootCompanion.__svx_create_from_sv__(91, 23)
    assert bindings == {}
    assert len(retired) == 1
    with pytest.raises(ExternalStorageError):
        retired[0].count.value
    # Writes performed before failure are ordinary SV side effects, not rollback.
    assert Int().unpack(transport.payload)[0] == 23


def test_duplicate_root_id_does_not_retire_existing_owner(environment):
    _, bindings, retired = environment
    original = RootCompanion.__svx_create_from_sv__(91, 23)
    with pytest.raises(ValueError, match="already bound"):
        RootCompanion.__svx_create_from_sv__(91, 29)
    assert bindings == {91: original}
    assert original.count.value == 23
    assert retired == []


def test_missing_owner_super_is_rejected_and_unbound(environment):
    _, bindings, retired = environment

    class Broken(_PythonRootOwner):
        def __init__(self):
            pass

    with pytest.raises(SVXInheritanceError, match="did not initialize"):
        Broken.__svx_create_from_sv__(91)
    assert bindings == {}
    assert len(retired) == 1


def test_root_owner_uses_the_real_constructor_codec_entry(environment, monkeypatch):
    from svtypes import CodecSession
    import svx.inheritance as inheritance
    from svx import runtime
    from tests.integration.constructor_handles_schema import binding

    monkeypatch.setattr(inheritance, "_constructor_contracts", {})
    monkeypatch.setattr(inheritance, "_python_subclasses", {})
    monkeypatch.setattr(runtime, "_state", runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, "_codec_session", CodecSession())
    class_id = "py://root/Root"
    spec = inheritance._type_binding(binding(Int), "test.seed", allow_void=False).runtime_spec()
    inheritance.register_constructor(class_id, (("seed", spec),))
    inheritance.register_python_subclass(class_id, RootCompanion)
    payload = inheritance.encode_constructor(class_id, {"seed": 23})
    inheritance.create_python_instance(class_id, 91, payload)
    _, bindings, _ = environment
    assert bindings[91].count.value == 23
    assert Root.observations == [(bindings[91], 19)]


@pytest.mark.parametrize("name", ["Root", "register_python_subclass", "register_constructor",
                                  "register_contract", "_PythonRootOwner"])
def test_generated_root_companion_registers_and_preserves_source_initializer(environment, monkeypatch, name):
    import inspect
    import sys
    from types import ModuleType
    from svtypes import CodecSession
    from svx import runtime
    import svx.inheritance as inheritance
    from tests.integration.python_root_proxy_schema import manifest_data

    module = ModuleType("generated_root_source")
    setattr(module, name, Root)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    data = manifest_data()
    source = data["classes"][0]
    source["canonical_id"] = "py://generated_owner/" + name
    source["symbol"] = module.__name__ + "." + name
    source["methods"] = []
    model = inheritance.parse_manifest(data)
    monkeypatch.setattr(inheritance, "_constructor_contracts", {})
    monkeypatch.setattr(inheritance, "_python_subclasses", {})
    monkeypatch.setattr(inheritance, "_method_contracts", {})
    monkeypatch.setattr(runtime, "_state", runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, "_codec_session", CodecSession())
    code = Root.__init__.__code__
    generated = inheritance._emit_python_root_companion(model, model.classes[0])
    namespace = {"__name__": "generated_owner_companion"}
    exec(compile(generated, "generated_owner_companion.py", "exec"), namespace)
    companion = namespace[name]
    assert companion.__name__ == name
    assert inspect.signature(companion) == inspect.signature(Root)
    assert Root.__init__.__code__ is code
    class_id = source["canonical_id"]
    assert inheritance._python_subclasses[class_id] is companion
    payload = inheritance.encode_constructor(class_id, {"seed": 35})
    inheritance.create_python_instance(class_id, 91, payload)
    transport, bindings, retired = environment
    owner = bindings[91]
    assert isinstance(owner, Root)
    assert Root.observations == [(owner, 19)]
    assert owner.count.value == 35
    assert owner.local.value == 7
    assert transport.writes == [(91, class_id + ".count", "set")]
    assert retired == []
    plain = Root(9)
    assert plain.count.value == 9
    assert owner.count.value == 35


def test_root_cleanup_error_does_not_hide_initializer_error(environment, monkeypatch):
    _, bindings, retired = environment
    monkeypatch.setattr(Root, "fail", True)

    def failed_release(self):
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(RootCompanion, "_svx_release_projected_fields", failed_release)
    with pytest.raises(ValueError, match="root initialization failed") as caught:
        RootCompanion.__svx_create_from_sv__(91, 23)
    assert bindings == {}
    assert len(retired) == 1
    assert any("cleanup failed" in note for note in caught.value.__notes__)


def test_constructor_entry_keeps_root_initialization_nonblocking(environment, monkeypatch):
    from svtypes import CodecSession
    import svx
    import svx.inheritance as inheritance
    from svx import runtime
    from tests.integration.constructor_handles_schema import binding

    class Waiting(RootCompanion):
        def __init__(self, seed):
            super().__init__(seed)
            svx.delay(1, "ns")

    monkeypatch.setattr(inheritance, "_constructor_contracts", {})
    monkeypatch.setattr(inheritance, "_python_subclasses", {})
    monkeypatch.setattr(runtime, "_state", runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, "_codec_session", CodecSession())
    spec = inheritance._type_binding(binding(Int), "test.seed", allow_void=False).runtime_spec()
    class_id = "py://root/Waiting"
    inheritance.register_constructor(class_id, (("seed", spec),))
    inheritance.register_python_subclass(class_id, Waiting)
    payload = inheritance.encode_constructor(class_id, {"seed": 23})
    with pytest.raises(svx.SVXContextError, match="constructor"):
        inheritance.create_python_instance(class_id, 91, payload)
    _, bindings, retired = environment
    assert bindings == {}
    with pytest.raises(ExternalStorageError):
        retired[0].count.value


@pytest.mark.parametrize("cooperative", [False, True])
@pytest.mark.parametrize("fail", [False, True])
def test_generated_plain_root_needs_no_user_owner_initialization(environment, monkeypatch, cooperative, fail):
    import inspect
    import sys
    from types import ModuleType
    import svx.inheritance as inheritance
    from tests.integration.python_root_proxy_schema import manifest_data

    observations = []

    class Plain:
        def __init__(self, seed):
            identity = getattr(self, "svtypes_object_number", None)
            if cooperative:
                super().__init__()
            assert getattr(self, "svtypes_object_number", None) == identity
            observations.append(self)
            self.seed = seed
            if fail:
                raise ValueError("plain source initialization failed")

        def check(self, delta):
            return self.seed + delta

    module = ModuleType("generated_plain_source")
    module.Plain = Plain
    monkeypatch.setitem(sys.modules, module.__name__, module)
    data = manifest_data()
    source = data["classes"][0]
    source["canonical_id"] = "py://plain/Plain"
    source["symbol"] = module.__name__ + ".Plain"
    source["fields"] = []
    source["methods"] = []
    model = inheritance.parse_manifest(data)
    monkeypatch.setattr(inheritance, "_constructor_contracts", {})
    monkeypatch.setattr(inheritance, "_python_subclasses", {})
    namespace = {"__name__": "generated_plain_companion"}
    original = Plain.__init__.__code__
    exec(inheritance._emit_python_root_companion(model, model.classes[0]), namespace)
    companion = namespace["Plain"]
    assert inspect.signature(companion) == inspect.signature(Plain)
    assert Plain.__init__.__code__ is original
    _, bindings, retired = environment
    if fail:
        with pytest.raises(ValueError, match="plain source initialization failed"):
            companion.__svx_create_from_sv__(91, 32)
        assert bindings == {}
        assert retired == observations
    else:
        owner = companion.__svx_create_from_sv__(91, 32)
        assert isinstance(owner, Plain)
        assert owner.check(3) == 35
        assert bindings == {91: owner}
        assert owner.svtypes_object_number > 0
        assert retired == []
        plain = Plain(8)
        assert plain.check(3) == 11
        assert not hasattr(plain, "_svx_remote_object_id")
        assert bindings == {91: owner}


@pytest.mark.parametrize("cleanup_failure", ["none", "before_close", "after_close"])
def test_generated_sv_mirror_preserves_initializer_error_and_retires_binding(environment, monkeypatch, cleanup_failure):
    import svx.inheritance as inheritance
    from tests.integration.sv_field_mirror_schema import manifest_data

    monkeypatch.setattr(inheritance, "_constructor_contracts", {})
    monkeypatch.setattr(inheritance, "_python_subclasses", {})
    monkeypatch.setattr(inheritance, "_method_contracts", {})
    generated = inheritance.emit_python_mirrors(inheritance.parse_manifest(manifest_data()))
    text = next(text for path, text in generated.items() if str(path) == "svx_mirror/field_owner_pkg.py")
    namespace = {"__name__": "generated_sv_owner"}
    exec(text, namespace)
    base = namespace["Base"]
    observations = []
    original = ValueError("SV mirror source initialization failed")

    class Derived(base):
        def __init__(self):
            super().__init__()
            self.count.value = 33
            observations.append(self)
            raise original

        def _svx_release_projected_fields(self):
            if cleanup_failure == "before_close":
                raise RuntimeError("storage cleanup failed before close")
            super()._svx_release_projected_fields()
            if cleanup_failure == "after_close":
                raise RuntimeError("storage cleanup failed after close")

    with pytest.raises(ValueError) as caught:
        Derived.__svx_create_from_sv__(91)
    assert caught.value is original
    transport, bindings, retired = environment
    assert bindings == {}
    assert retired == observations
    assert Int().unpack(transport.payload)[0] == 33
    if cleanup_failure != "none":
        assert any("close projected storage" in note for note in original.__notes__)
    if cleanup_failure != "before_close":
        with pytest.raises(ExternalStorageError):
            retired[0].count.value


@pytest.mark.parametrize("python_base", [False, True])
def test_root_callback_distinguishes_python_base_from_dynamic_override(environment, monkeypatch, python_base):
    import sys
    from types import ModuleType, SimpleNamespace
    from svtypes import CodecSession
    import svx
    from svx import runtime
    import svx.inheritance as inheritance
    from tests.integration.python_root_proxy_schema import manifest_data

    module = ModuleType("root_dispatch_source")
    module.Root = Root
    monkeypatch.setitem(sys.modules, module.__name__, module)
    data = manifest_data()
    data["classes"][0]["symbol"] = module.__name__ + ".Root"
    model = inheritance.parse_manifest(data)
    monkeypatch.setattr(inheritance, "_constructor_contracts", {})
    monkeypatch.setattr(inheritance, "_python_subclasses", {})
    monkeypatch.setattr(inheritance, "_method_contracts", {})
    monkeypatch.setattr(runtime, "_state", runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, "_codec_session", CodecSession())
    namespace = {"__name__": "root_dispatch_companion"}
    exec(inheritance._emit_python_root_companion(model, model.classes[0]), namespace)

    class Override(namespace["Root"]):
        def check(self, delta):
            return 999

    instance = Override.__svx_create_from_sv__(91, 23)
    _, bindings, _ = environment
    monkeypatch.setattr(svx, "_native", SimpleNamespace(inheritance_get=bindings.get))
    method = model.classes[0].methods[0]
    contract = inheritance._method_contracts[method.canonical_id]
    request_schema = inheritance._contract_schema(contract, method.canonical_id, "request")
    request = inheritance._record_value(request_schema, contract.request_fields, {"delta": 3})
    payload = inheritance._pack_call_record(request_schema, request)
    method_id = (inheritance._PYTHON_BASE_METHOD_PREFIX if python_base else "") + method.canonical_id
    response = inheritance.dispatch_python_call(91, method_id, payload, function_context=True)
    response_schema = inheritance._contract_schema(contract, method.canonical_id, "response")
    result = inheritance._unpack_call_record(response_schema, response)
    assert inheritance._record_field(result, inheritance._method_return_slot(method)) == (26 if python_base else 999)
    assert instance.count.value == 23
    if python_base:
        monkeypatch.setattr(Override, "__svx_python_base_classes__", {})
        with pytest.raises(SVXInheritanceError, match="no Python base portion"):
            inheritance.dispatch_python_call(91, method_id, payload, function_context=True)


def test_inherited_callback_boundary_is_independent_of_contract_owner(environment, staged_root, monkeypatch):
    from types import SimpleNamespace
    import json
    import svx
    import svx.inheritance as inheritance
    from tests.integration.python_root_proxy_schema import manifest_data

    root, root_id, _ = staged_root
    method = inheritance.parse_manifest(manifest_data()).classes[0].methods[0]
    child_id, derived_id = 'sv://probe/InheritedChild', 'py://probe/InheritedDerived'

    class Derived(root):
        __svx_foreign_class_id__ = child_id
        __svx_python_callback_portions__ = {}

        def check(self, delta):
            return self.count.value + delta + 1000

    class Final(Derived):
        __svx_foreign_class_id__ = 'sv://probe/InheritedFinal'
        __svx_python_callback_portions__ = {child_id: derived_id}
        __svx_python_base_classes__ = {derived_id: Derived, root_id: Root}

        def check(self, delta):
            return self.count.value + delta + 2000

    contract = inheritance._method_contracts[method.canonical_id]
    schema = inheritance._contract_schema(contract, method.canonical_id, 'request')
    request = inheritance._record_value(schema, contract.request_fields, {'delta': 3})
    payload = inheritance._pack_call_record(schema, request)
    response_schema = inheritance._contract_schema(contract, method.canonical_id, 'response')

    def call(boundary):
        route = inheritance._PYTHON_CALLBACK_METHOD_PREFIX + json.dumps(
            {'boundary': boundary, 'method': method.canonical_id})
        response = inheritance.dispatch_python_call(91, route, payload, function_context=True)
        record = inheritance._unpack_call_record(response_schema, response)
        return inheritance._record_field(record, inheritance._method_return_slot(method))

    instance = Derived.__svx_create_from_sv__(91, 23)
    monkeypatch.setattr(svx, '_native', SimpleNamespace(inheritance_get=lambda object_id: instance))
    assert call(child_id) == 1026
    instance._svx_release_projected_fields()
    environment[1].pop(91)
    instance = Final.__svx_create_from_sv__(91, 23)
    assert call(child_id) == 1026
    assert call(Final.__svx_foreign_class_id__) == 2026
    with pytest.raises(SVXInheritanceError, match='no Python callback boundary'):
        call('sv://probe/Unrelated')


@pytest.fixture
def staged_root(environment, monkeypatch):
    import sys
    from types import ModuleType
    from svtypes import CodecSession
    from svx import runtime
    import svx.inheritance as inheritance
    from tests.integration.python_root_proxy_schema import manifest_data, ROOT_ID

    module = ModuleType("staged_root_source")
    module.Root = Root
    monkeypatch.setitem(sys.modules, module.__name__, module)
    data = manifest_data()
    data["classes"][0]["symbol"] = module.__name__ + ".Root"
    model = inheritance.parse_manifest(data)
    for name in ("_constructor_contracts", "_python_subclasses", "_method_contracts", "_python_static_methods"):
        monkeypatch.setattr(inheritance, name, {})
    monkeypatch.setattr(runtime, "_state", runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, "_codec_session", CodecSession())
    namespace = {"__name__": "staged_root_companion"}
    exec(inheritance._emit_python_root_companion(model, model.classes[0]), namespace)
    payload = inheritance.encode_constructor(ROOT_ID, {"seed": 23})
    return namespace["Root"], ROOT_ID, payload


def test_shared_root_module_preserves_all_public_types_and_original_initializers(environment, staged_root, monkeypatch):
    import ast
    import inspect
    import sys
    from copy import deepcopy
    from types import ModuleType
    import svx.inheritance as inheritance
    from tests.integration.python_root_proxy_schema import manifest_data

    module = ModuleType("shared_root_source")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    names = ("Root", "_ForeignRoot", "register_contract", "_PythonRootOwner", "_source_signature")

    def initializer(label):
        def init(self, seed):
            self.source_label = label
            self.seed = seed
        return init

    data = manifest_data()
    template = deepcopy(data["classes"][0])
    data["classes"] = []
    for name in names:
        setattr(module, name, type(name, (), {"__init__": initializer(name)}))
        declaration = deepcopy(template)
        declaration.update(canonical_id="py://shared_root/" + name,
                           symbol=module.__name__ + "." + name, fields=[], methods=[])
        data["classes"].append(declaration)
    model = inheritance.parse_manifest(data)
    generated = inheritance._emit_python_root_module(model, model.classes, companion_modules={})
    tree = ast.parse(generated)
    assert sum(isinstance(node, ast.ImportFrom) and node.module == "__future__" for node in tree.body) == 1
    namespace = {"__name__": "shared_root_companion"}
    exec(compile(tree, "shared_root_companion.py", "exec"), namespace)
    for declaration in model.classes:
        companion = namespace[declaration.name]
        original = getattr(module, declaration.name)
        assert isinstance(companion, type) and issubclass(companion, original)
        assert inspect.signature(companion) == inspect.signature(original)
        payload = inheritance.encode_constructor(declaration.canonical_id, {"seed": 45})
        inheritance.create_python_instance(declaration.canonical_id, 91, payload)
        owner = environment[1].pop(91)
        assert type(owner) is companion
        assert owner.source_label == declaration.name and owner.seed == 45
        assert original(7).seed == 7


def test_shared_root_module_rejects_duplicate_public_names(staged_root):
    import svx.inheritance as inheritance
    from tests.integration.python_root_proxy_schema import manifest_data

    model = inheritance.parse_manifest(manifest_data())
    with pytest.raises(SVXInheritanceError, match="duplicate public class names"):
        inheritance._emit_python_root_module(model, (model.classes[0], model.classes[0]), companion_modules={})


def test_shared_sv_views_do_not_overwrite_public_classes_with_helper_imports(staged_root, monkeypatch):
    import inspect
    import sys
    from types import ModuleType
    import svx.inheritance as inheritance
    from tests.integration.python_root_proxy_schema import probe_manifest_data, ROOT_ID, DERIVED_ID

    root = staged_root[0]
    root_module = ModuleType("shared_view_root")
    root_module.Root = root
    derived_module = ModuleType("shared_view_derived")
    derived_module.Derived = type("Derived", (root,), {})
    for module in (root_module, derived_module):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    data = probe_manifest_data()
    renamed = {data["classes"][2]["canonical_id"]: "_RootCompanion",
               data["classes"][4]["canonical_id"]: "register_contract"}
    for target in data["classes"]:
        for declaration in (*target.get("base_lineage", []), target):
            if declaration["canonical_id"] in renamed:
                declaration["symbol"] = "shared_view_pkg::" + renamed[declaration["canonical_id"]]
    model = inheritance.parse_manifest(data)
    generated = inheritance._emit_python_root_module(
        model, (model.classes[4], model.classes[2]),
        companion_modules={ROOT_ID: root_module.__name__, DERIVED_ID: derived_module.__name__})
    namespace = {"__name__": "svx_mirror.shared_view_pkg"}
    exec(generated, namespace)
    for declaration in (model.classes[2], model.classes[4]):
        mirror = namespace[declaration.name]
        assert isinstance(mirror, type)
        assert mirror.__svx_foreign_class_id__ == declaration.canonical_id
        assert mirror.__name__ == declaration.name
        assert tuple(inspect.signature(mirror).parameters) == tuple(parameter.name for parameter in declaration.constructor.parameters)
    assert generated.count("from __future__ import annotations") == 1


@pytest.mark.parametrize("legacy_dispatch", [False, True])
def test_callback_routes_by_sv_method_owner(environment, staged_root, monkeypatch, legacy_dispatch):
    from dataclasses import replace
    from types import SimpleNamespace
    import svx
    import svx.inheritance as inheritance
    from tests.integration.python_root_proxy_schema import manifest_data

    root, root_id, _ = staged_root
    root_method = inheritance.parse_manifest(manifest_data()).classes[0].methods[0]
    child_id, derived_id, grandchild_id = "sv://probe/Child", "py://probe/Derived", "sv://probe/Grandchild"
    methods = [replace(root_method, canonical_id=owner + "#check") for owner in (child_id, grandchild_id)]
    exec("\n".join(inheritance._register_contract_lines(methods)), {"register_contract": inheritance.register_contract})

    class Derived(root):
        def check(self, delta):
            return self.count.value + delta + 1000

    class Grandchild(Derived):
        __svx_python_callback_portions__ = {child_id: derived_id}
        __svx_python_base_classes__ = {derived_id: Derived, root_id: Root}

    class Final(Grandchild):
        def check(self, delta):
            return self.count.value + delta + 2000

    if legacy_dispatch:
        monkeypatch.setattr(Final, "__svx_dispatch_foreign__", lambda self, name, *args: getattr(self, name)(*args), raising=False)
    instance = Final.__svx_create_from_sv__(91, 23)
    monkeypatch.setattr(svx, "_native", SimpleNamespace(inheritance_get=environment[1].get))

    def call(method_id, contract_id):
        contract = inheritance._method_contracts[contract_id]
        request_schema = inheritance._contract_schema(contract, contract_id, "request")
        request = inheritance._record_value(request_schema, contract.request_fields, {"delta": 3})
        payload = inheritance._pack_call_record(request_schema, request)
        response = inheritance.dispatch_python_call(91, method_id, payload, function_context=True)
        schema = inheritance._contract_schema(contract, contract_id, "response")
        record = inheritance._unpack_call_record(schema, response)
        return inheritance._record_field(record, inheritance._method_return_slot(root_method))

    assert call(child_id + "#check", child_id + "#check") == 1026
    assert call(grandchild_id + "#check", grandchild_id + "#check") == 2026
    assert call(inheritance._PYTHON_BASE_METHOD_PREFIX + root_id + "#check", root_id + "#check") == 26
    assert instance.count.value == 23
    for invalid in ({}, {derived_id: int}):
        monkeypatch.setattr(Final, "__svx_python_base_classes__", invalid)
        with pytest.raises(SVXInheritanceError, match="no Python callback portion"):
            call(child_id + "#check", child_id + "#check")


def test_python_origin_root_is_initialized_before_sv_child_body(environment, staged_root, monkeypatch):
    from types import SimpleNamespace
    import svx
    import svx.inheritance as inheritance

    root, root_id, root_payload = staged_root
    events = []
    unpack = inheritance._unpack_call_record

    def decode(schema, payload):
        assert 91 in environment[1], "constructor decoding preceded receiver registration"
        return unpack(schema, payload)

    monkeypatch.setattr(inheritance, "_unpack_call_record", decode)

    def create(class_id, payload):
        assert class_id == "sv://stage/Child" and payload == b"child"
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, root_payload)
        instance = environment[1][91]
        events.append(("child_body", instance.count.value, instance.local.value))
        return 91

    monkeypatch.setattr(svx, "_native", SimpleNamespace(inheritance_create_sv=create))

    class ChildMirror(root):
        def __init__(self):
            inheritance._create_sv_with_python_root(self, root_id, "sv://stage/Child", b"child")

    owner = ChildMirror()
    assert events == [("child_body", 23, 7)]
    assert Root.observations == [(owner, 19)]
    assert environment[1] == {91: owner}
    assert owner._svx_remote_object_id == 91
    assert inheritance._pending_python_root.get() is None


@pytest.mark.parametrize("failure", ["root", "child", "missing", "repeated", "wrong_id"])
def test_failed_staged_root_closes_owned_target_and_restores_context(environment, staged_root, monkeypatch, failure):
    from types import SimpleNamespace
    import svx
    import svx.inheritance as inheritance

    root, root_id, root_payload = staged_root
    closed = []
    owner = root.__new__(root)
    previous = inheritance._PendingPythonRoot(object(), "py://previous/Root")
    token = inheritance._pending_python_root.set(previous)
    if failure == "root":
        monkeypatch.setattr(Root, "fail", True)

    def create(_class_id, _payload):
        if failure == "missing":
            return 91
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, root_payload)
        if failure == "repeated":
            inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, root_payload)
        if failure == "wrong_id":
            return 92
        raise ValueError("child constructor failed")

    def close(object_id):
        closed.append(object_id)
        instance = environment[1].pop(object_id, None)
        if instance is not None:
            environment[2].append(instance)

    monkeypatch.setattr(svx, "_native", SimpleNamespace(inheritance_create_sv=create, inheritance_close=close))
    try:
        with pytest.raises((ValueError, SVXInheritanceError)):
            inheritance._create_sv_with_python_root(owner, root_id, "sv://stage/Child", b"child")
        # Root failures close inside the callback before the native fatal policy;
        # the enclosing factory retains its idempotent cleanup on return.
        expected_closed = [91, 92] if failure == "wrong_id" else [91, 91] if failure == "root" else [91]
        assert closed == expected_closed
        assert environment[1] == {}
        assert inheritance._pending_python_root.get() is previous
        if failure != "missing":
            with pytest.raises(ExternalStorageError):
                owner.count.value
    finally:
        inheritance._pending_python_root.reset(token)


def test_supplied_id_without_pending_root_does_not_create_companion(environment, staged_root):
    import svx.inheritance as inheritance

    _, root_id, root_payload = staged_root
    assert inheritance._pending_python_root.get() is None
    inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, root_payload)
    assert environment[1] == {}
    assert Root.observations == []


@pytest.fixture
def sv_origin_stages(environment, staged_root, monkeypatch):
    import json
    from svx import _native
    import svx.inheritance as inheritance

    root, root_id, payload = staged_root
    _, bindings, _ = environment
    target_id = "py://staged/Derived"

    class Derived(root):
        calls = []
        fail = False
        reenter = False

        def __init__(self, increment):
            self.calls.append((self, self.count.value))
            if self.reenter:
                with pytest.raises(SVXInheritanceError, match="repeated Python constructor portion"):
                    inheritance.create_python_instance(inheritance._PYTHON_PORTION_INIT_PREFIX + target_id,
                                                       91, later_payload)
            self.count.value += increment
            if self.fail:
                raise ValueError("later initializer failed")

    inheritance.register_python_subclass(target_id, Derived)
    spec = inheritance._constructor_contracts[root_id].request_fields[0][1]
    inheritance.register_constructor(target_id, (("increment", spec),))
    later_payload = inheritance.encode_constructor(target_id, {"increment": 5})
    selector = inheritance._PYTHON_ROOT_ALLOC_PREFIX + json.dumps({"root": root_id, "target": target_id})
    monkeypatch.setattr(_native, "inheritance_get", bindings.get)
    return root, root_id, Derived, target_id, selector, payload, later_payload


def test_sv_origin_allocates_final_receiver_but_initializes_portions_in_order(environment, sv_origin_stages):
    import svx.inheritance as inheritance

    _, bindings, _ = environment
    root, root_id, target, target_id, selector, payload, later_payload = sv_origin_stages
    inheritance.create_python_instance(selector, 91, payload)
    receiver = bindings[91]
    assert type(receiver) is target and isinstance(receiver, root)
    assert Root.observations == [(receiver, 19)] and target.calls == []
    assert receiver.count.value == 23
    backend = receiver._svx_field_storage
    target.reenter = True
    inheritance.create_python_instance(inheritance._PYTHON_PORTION_INIT_PREFIX + target_id, 91, later_payload)
    assert target.calls == [(receiver, 23)] and receiver.count.value == 28
    assert bindings == {91: receiver} and receiver._svx_field_storage is backend
    assert receiver._svx_initialized_python_portions == {root_id, target_id}
    with pytest.raises(SVXInheritanceError, match="repeated Python constructor portion"):
        inheritance.create_python_instance(inheritance._PYTHON_PORTION_INIT_PREFIX + target_id, 91, later_payload)
    assert bindings == {91: receiver} and target.calls == [(receiver, 23)]


@pytest.mark.parametrize("stage", ["root", "later", "decode"])
def test_failed_sv_origin_stage_retires_binding_and_fields(environment, sv_origin_stages, monkeypatch, stage):
    import svx.inheritance as inheritance

    _, bindings, retired = environment
    _, _, target, target_id, selector, payload, later_payload = sv_origin_stages
    if stage == "root":
        monkeypatch.setattr(target, "fail", True)
        with pytest.raises(ValueError, match="root initialization failed"):
            inheritance.create_python_instance(selector, 91, payload)
    else:
        inheritance.create_python_instance(selector, 91, payload)
        if stage == "later":
            target.fail = True
            expected = "later initializer failed"
            failure_type = ValueError
        else:
            later_payload += b"unexpected trailing byte"
            expected = "trailing bytes"
            failure_type = SVXInheritanceError
        with pytest.raises(failure_type, match=expected):
            inheritance.create_python_instance(inheritance._PYTHON_PORTION_INIT_PREFIX + target_id, 91, later_payload)
    assert bindings == {} and len(retired) == 1
    with pytest.raises(ExternalStorageError):
        _ = retired[0].count.value
    assert inheritance._pending_python_root.get() is None


@pytest.mark.parametrize("selection", [{}, {"root": "missing", "target": "missing"},
                                      {"root": 3, "target": "missing"},
                                      {"root": "ROOT", "target": "unrelated"}])
def test_invalid_sv_origin_target_does_not_allocate_or_retire(environment, staged_root, selection):
    import json
    import svx.inheritance as inheritance

    _, root_id, payload = staged_root
    selection = {name: root_id if value == "ROOT" else value for name, value in selection.items()}
    inheritance._python_subclasses["unrelated"] = object
    with pytest.raises(SVXInheritanceError):
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_ALLOC_PREFIX + json.dumps(selection), 91, payload)
    _, bindings, retired = environment
    assert bindings == {} and retired == [] and Root.observations == []


def test_duplicate_sv_origin_stage_preserves_existing_receiver(environment, sv_origin_stages):
    import svx.inheritance as inheritance

    _, bindings, retired = environment
    _, _, _, _, selector, payload, _ = sv_origin_stages
    inheritance.create_python_instance(selector, 91, payload)
    receiver = bindings[91]
    with pytest.raises(ValueError, match="already bound"):
        inheritance.create_python_instance(selector, 91, payload)
    assert bindings == {91: receiver} and receiver.count.value == 23
    assert retired == [] and len(Root.observations) == 1


@pytest.fixture
def ordered_stages(environment, sv_origin_stages):
    import svx.inheritance as inheritance

    root, root_id, derived, derived_id, _, root_payload, derived_payload = sv_origin_stages
    later_id = "py://staged/Later"
    view_id = "sv://staged/FinalView"

    class Later(derived):
        later_calls = []

        def __init__(self, factor):
            self.later_calls.append((self, self.count.value))
            self.count.value += factor

    class FinalView(Later):
        __svx_constructor_python_portions__ = (derived_id, later_id)

        def __init__(self):
            raise AssertionError("final SV view must not replace a Python portion initializer")

    inheritance.register_python_subclass(later_id, Later)
    inheritance.register_python_subclass(view_id, FinalView)
    spec = inheritance._constructor_contracts[root_id].request_fields[0][1]
    inheritance.register_constructor(later_id, (("factor", spec),))
    later_payload = inheritance.encode_constructor(later_id, {"factor": 7})
    return root_id, derived_id, later_id, view_id, FinalView, root_payload, derived_payload, later_payload


def test_ordered_stages_keep_final_view_and_do_not_skip_or_reenter(environment, ordered_stages):
    import json
    import svx.inheritance as inheritance

    root_id, derived_id, later_id, view_id, view, root_payload, derived_payload, later_payload = ordered_stages
    _, bindings, _ = environment
    selector = {"root": root_id, "target": view_id, "portions": [derived_id, later_id]}
    inheritance.create_python_instance(inheritance._PYTHON_ROOT_ALLOC_PREFIX + json.dumps(selector), 91, root_payload)
    receiver = bindings[91]
    assert type(receiver) is view and receiver.count.value == 23
    with pytest.raises(SVXInheritanceError, match="repeated Python constructor portion"):
        inheritance.create_python_instance(inheritance._PYTHON_PORTION_INIT_PREFIX + later_id, 91, later_payload)
    assert receiver._svx_pending_python_portions == (derived_id, later_id)
    inheritance.create_python_instance(inheritance._PYTHON_PORTION_INIT_PREFIX + derived_id, 91, derived_payload)
    assert receiver.count.value == 28 and receiver._svx_pending_python_target_id == later_id
    with pytest.raises(SVXInheritanceError, match="repeated Python constructor portion"):
        inheritance.create_python_instance(inheritance._PYTHON_PORTION_INIT_PREFIX + derived_id, 91, derived_payload)
    inheritance.create_python_instance(inheritance._PYTHON_PORTION_INIT_PREFIX + later_id, 91, later_payload)
    assert receiver.count.value == 35 and receiver.later_calls == [(receiver, 28)]
    assert receiver._svx_pending_python_portions == ()
    assert receiver._svx_initialized_python_portions == {root_id, derived_id, later_id}
    assert bindings == {91: receiver}


@pytest.mark.parametrize("mode", ["skip", "reverse", "duplicate", "root"])
def test_invalid_ordered_plan_rejected_before_binding(environment, ordered_stages, mode):
    import json
    import svx.inheritance as inheritance

    root_id, derived_id, later_id, view_id, _, payload, _, _ = ordered_stages
    portions = {"skip": [later_id], "reverse": [later_id, derived_id],
                "duplicate": [derived_id, derived_id], "root": [root_id, derived_id, later_id]}[mode]
    with pytest.raises(SVXInheritanceError):
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_ALLOC_PREFIX + json.dumps(
            {"root": root_id, "target": view_id, "portions": portions}), 91, payload)
    _, bindings, retired = environment
    assert bindings == {} and retired == [] and Root.observations == []


@pytest.mark.parametrize("complete", [False, True])
def test_python_origin_factory_requires_all_ordered_portions(environment, ordered_stages, monkeypatch, complete):
    import svx.inheritance as inheritance
    from svx import _native

    root_id, derived_id, later_id, view_id, view, root_payload, derived_payload, later_payload = ordered_stages
    _, bindings, _ = environment
    receiver = view.__new__(view)

    def factory(class_id, payload):
        assert class_id == view_id and payload == b"SV target record"
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, root_payload)
        inheritance.create_python_instance(inheritance._PYTHON_PORTION_INIT_PREFIX + derived_id, 91, derived_payload)
        if complete:
            inheritance.create_python_instance(inheritance._PYTHON_PORTION_INIT_PREFIX + later_id, 91, later_payload)
        return 91

    monkeypatch.setattr(_native, "inheritance_create_sv", factory)
    monkeypatch.setattr(_native, "inheritance_close", lambda object_id: bindings.pop(object_id))
    if complete:
        assert inheritance._create_sv_with_python_root(receiver, root_id, view_id, b"SV target record",
                                                     python_portions=(derived_id, later_id)) == 91
        assert bindings == {91: receiver} and receiver.count.value == 35
    else:
        with pytest.raises(SVXInheritanceError, match="all Python constructor portions"):
            inheritance._create_sv_with_python_root(receiver, root_id, view_id, b"SV target record",
                                                   python_portions=(derived_id, later_id))
        assert bindings == {}
        with pytest.raises(ExternalStorageError):
            _ = receiver.count.value
    assert inheritance._pending_python_root.get() is None


@pytest.mark.parametrize("name", ["Child", "invoke_sv", "register_contract"])
def test_generated_root_sv_view_preserves_constructor_and_bridge_names(environment, staged_root, monkeypatch, name):
    from copy import deepcopy
    import inspect
    import sys
    from types import ModuleType, SimpleNamespace
    import svx
    import svx.inheritance as inheritance
    from tests.integration.python_root_proxy_schema import probe_manifest_data

    root, root_id, root_payload = staged_root
    module = ModuleType("root_view_parent")
    module.Root = root
    monkeypatch.setitem(sys.modules, module.__name__, module)
    data = probe_manifest_data()
    source = data["classes"][2]
    source["symbol"] = "python_root_probe_pkg::" + name
    source["constructor"]["parameters"][0]["name"] = "self"
    for declaration in data["classes"]:
        for ancestor in declaration.get("base_lineage", []):
            if ancestor["canonical_id"] == source["canonical_id"]:
                ancestor.clear()
                ancestor.update({key: deepcopy(value) for key, value in source.items() if key != "base_lineage"})
    model = inheritance.parse_manifest(data)
    generated = inheritance._emit_python_root_sv_view(model, model.classes[2], model.classes[0], root_module=module.__name__)
    namespace = {"__name__": "generated_root_view"}
    exec(generated, namespace)
    view = namespace[name]
    assert tuple(inspect.signature(view).parameters) == ("self",)
    seen = []

    def encode(class_id, values):
        assert class_id == source["canonical_id"]
        seen.append(values.copy())
        return b"child"

    def create(class_id, payload):
        assert class_id == source["canonical_id"] and payload == b"child"
        inheritance.create_python_instance(inheritance._PYTHON_ROOT_INIT_PREFIX + root_id, 91, root_payload)
        return 91

    monkeypatch.setattr(inheritance, "encode_constructor", encode)
    monkeypatch.setattr(inheritance, "invoke_sv", lambda object_id, method_id, values: (object_id, method_id, values))
    monkeypatch.setattr(svx, "_native", SimpleNamespace(inheritance_create_sv=create))
    owner = view(23)
    assert seen == [{"self": 23}]
    assert environment[1] == {91: owner}
    assert owner.__svx_foreign_class_id__ == source["canonical_id"]
    assert owner.check(3) == (91, source["canonical_id"] + "#check", {"delta": 3})
