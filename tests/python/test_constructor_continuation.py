import traceback

import pytest

from svx._constructor_continuation import ConstructorContinuations
from svx.errors import SVXInheritanceError


def test_constructor_two_boundaries_share_receiver_without_replay():
    manager = ConstructorContinuations()
    events = []

    def outer():
        events.append("D-before")
        manager.suspend(1, "C", b"C-args")
        events.append("D-after")

    def inner():
        events.append("B-before")
        manager.suspend(1, "A", b"A-args")
        events.append("B-after")

    assert manager.prepare(1, "C", outer) == b"C-args"
    assert manager.prepare(1, "A", inner) == b"A-args"
    assert manager.pending_count == 2
    manager.resume(1, "A")
    manager.resume(1, "C")
    assert events == ["D-before", "B-before", "B-after", "D-after"]
    assert manager.pending_count == 0


def test_constructor_abort_unwinds_every_boundary_and_preserves_other_receiver():
    manager = ConstructorContinuations()
    finalized = []

    def initializer(receiver, boundary):
        try:
            manager.suspend(receiver, boundary, b"args")
        finally:
            finalized.append((receiver, boundary))

    for receiver, boundary in [(1, "C"), (1, "A"), (2, "A")]:
        manager.prepare(receiver, boundary, lambda r=receiver, b=boundary: initializer(r, b))
    manager.abort(1, SVXInheritanceError("SV constructor failed"))
    assert finalized == [(1, "A"), (1, "C")]
    assert manager.pending_count == 1
    manager.resume(2, "A")
    assert manager.pending_count == 0


def test_constructor_original_exception_location_is_preserved():
    manager = ConstructorContinuations()

    def initializer():
        manager.suspend(1, "A", b"args")
        raise ValueError("original initializer failed")

    manager.prepare(1, "A", initializer)
    with pytest.raises(ValueError, match="original initializer failed") as captured:
        manager.resume(1, "A")
    assert "raise ValueError" in "".join(traceback.format_exception(captured.value))
    assert manager.pending_count == 0


def test_constructor_missing_boundary_is_rejected_and_removed():
    manager = ConstructorContinuations()
    with pytest.raises(SVXInheritanceError, match="did not reach"):
        manager.prepare(1, "A", lambda: None)
    assert manager.pending_count == 0


def test_inner_constructor_failure_can_unwind_waiting_outer_constructor():
    manager = ConstructorContinuations()
    finalized = []

    def outer():
        try:
            manager.suspend(1, "C", b"C")
        finally:
            finalized.append("D")

    def inner():
        manager.suspend(1, "A", b"A")
        raise RuntimeError("B initialization failed")

    manager.prepare(1, "C", outer)
    manager.prepare(1, "A", inner)
    with pytest.raises(RuntimeError, match="B initialization failed") as captured:
        manager.resume(1, "A")
    assert manager.pending_count == 1
    manager.abort(1, captured.value)
    assert finalized == ["D"]
    assert manager.pending_count == 0


@pytest.mark.parametrize("failure_stage", [None, "before", "after"])
@pytest.mark.parametrize("preallocated", [False, True])
def test_generated_mirror_captures_typed_arguments_and_resumes_original_initializer(monkeypatch, failure_stage, preallocated):
    from types import SimpleNamespace
    import svtypes
    import svx
    from svx import declarations, inheritance, runtime
    from tests.integration.sv_field_mirror_schema import manifest_data

    monkeypatch.setattr(runtime, "_state", runtime.RuntimeState.READY)
    monkeypatch.setattr(runtime, "_codec_session", svtypes.CodecSession())
    monkeypatch.setattr(declarations, "_source_mirror_declarations", {})
    monkeypatch.setattr(declarations, "_source_mirror_implementations", {})
    monkeypatch.setattr(inheritance, "_constructor_contracts", {})
    monkeypatch.setattr(inheritance, "_method_contracts", {})
    monkeypatch.setattr(inheritance, "_python_subclasses", {})
    manager = ConstructorContinuations()
    monkeypatch.setattr(inheritance, "_natural_constructor_segments", manager)

    def unexpected_allocation(*args):
        raise AssertionError("prepared Mirror allocated a second SV receiver")

    receivers = {}
    closed = []
    def close_receiver(object_id):
        closed.append(object_id)
        instance = receivers.pop(object_id, None)
        if instance is not None:
            instance._svx_release_projected_fields()

    monkeypatch.setattr(svx, "_native", SimpleNamespace(
        inheritance_create_sv=unexpected_allocation, inheritance_get=receivers.get,
        inheritance_bind=lambda object_id, instance: receivers.__setitem__(object_id, instance),
        inheritance_unbind=lambda object_id: receivers.pop(object_id, None),
        inheritance_close=close_receiver))
    data = manifest_data()
    source = data["classes"][0]
    parameters = [declarations.inheritance_parameter("seed", svtypes.Int),
                  declarations.inheritance_parameter("label", svtypes.String)]
    source["constructor"]["parameters"] = parameters
    generated = inheritance.emit_python_mirrors(inheritance.parse_manifest(data))
    namespace = {}
    text = next(text for path, text in generated.items() if path.name != "__init__.py")
    exec(compile(text, "natural_constructor_mirror.py", "exec"), namespace)
    Mirror = namespace["Base"]
    events = []

    class B(Mirror):
        def __init__(self, seed, label):
            events.append(("before", seed, label))
            if failure_stage == "before":
                raise ValueError("original B preparation failed")
            super().__init__(label=label + "-B", seed=seed + 1)
            events.append(("after", self._svx_remote_object_id))
            if failure_stage == "after":
                raise ValueError("original B initialization failed")

    class_id = "py://natural_constructor/B"
    inheritance.register_python_subclass(class_id, B)
    inheritance.register_constructor(class_id, tuple(
        (parameter.name, parameter.type_binding.runtime_spec())
        for parameter in inheritance.parse_manifest(data).classes[0].constructor.parameters))
    if preallocated:
        instance = B.__new__(B)
        svx.SVMirror.__init__(instance)
        receivers[71] = instance
    payload = inheritance.encode_constructor(class_id, {"seed": 7, "label": "alpha"})
    import json
    def route(phase):
        return inheritance._NATURAL_CONSTRUCTOR_PREFIX + json.dumps({
            "phase": phase, "python": class_id, "sv": source["canonical_id"]})
    if failure_stage == "before":
        with pytest.raises(ValueError, match="original B preparation failed"):
            inheritance.dispatch_python_call(71, route("prepare"), payload, True)
        assert manager.pending_count == 0
        assert events == [("before", 7, "alpha")]
        assert 71 not in receivers
        assert closed == [71]
        return
    captured = inheritance.dispatch_python_call(71, route("prepare"), payload, True)
    instance = receivers[71]
    assert inheritance._decode_constructor_arguments(source["canonical_id"], captured) == (8, "alpha-B")
    assert events == [("before", 7, "alpha")]
    assert manager.pending_count == 1
    if preallocated:
        with pytest.raises(SVXInheritanceError, match="not bound"):
            inheritance.dispatch_python_call(71, route("resume"), b"", True)
        assert manager.pending_count == 1
        instance._svx_bind_remote_object(71)
    else:
        assert instance._svx_remote_object_id == 71
    if failure_stage == "after":
        with pytest.raises(ValueError, match="original B initialization failed"):
            inheritance.dispatch_python_call(71, route("resume"), b"", True)
        assert 71 not in receivers
        assert closed == [71]
        with pytest.raises(svtypes.ExternalStorageError) as closed_field:
            _ = instance.count.value
        assert "closed" in str(closed_field.value.__cause__)
    else:
        assert inheritance.dispatch_python_call(71, route("resume"), b"", True) == b""
    assert events == [("before", 7, "alpha"), ("after", 71)]
    assert manager.pending_count == 0


def test_constructor_continuation_preserves_function_context_after_suspension():
    from svx.callback_context import blocking_operations_disallowed, require_blocking_operations_allowed
    from svx.errors import SVXContextError

    manager = ConstructorContinuations()
    def initializer():
        manager.suspend(1, "A", b"args")
        require_blocking_operations_allowed("delay")

    with blocking_operations_disallowed("SV constructor callback"):
        assert manager.prepare(1, "A", initializer) == b"args"
    with pytest.raises(SVXContextError, match="delay.*SV constructor callback"):
        manager.resume(1, "A")
    assert manager.pending_count == 0


def test_natural_constructor_completion_retires_reservation_in_lineage_order(monkeypatch):
    from types import SimpleNamespace
    from svx import inheritance
    from svx.errors import SVXInheritanceError

    instance = SimpleNamespace()
    pending = SimpleNamespace(instance=instance, object_id=71, root_class_id="py://B",
                              python_portions=("py://D",), initialized=False, retired=False)
    reservations = {71: pending}
    monkeypatch.setattr(inheritance, "_reserved_python_receivers", reservations)
    token = inheritance._pending_python_root.set(None)
    try:
        instance._svx_reserved_python_receiver = {"root": "py://B"}
        with pytest.raises(SVXInheritanceError, match="out of order"):
            inheritance._complete_natural_constructor_portion(instance, 71, "py://D")
        inheritance._complete_natural_constructor_portion(instance, 71, "py://B")
        assert pending.initialized
        assert instance._svx_pending_python_portions == ("py://D",)
        assert not hasattr(instance, "_svx_reserved_python_receiver")
        assert reservations[71] is pending
        inheritance._complete_natural_constructor_portion(instance, 71, "py://D")
        assert instance._svx_initialized_python_portions == {"py://B", "py://D"}
        assert instance._svx_pending_python_portions == ()
        assert instance._svx_pending_python_target_id is None
        assert reservations == {}
    finally:
        inheritance._pending_python_root.reset(token)


def test_natural_completion_uses_root_initialized_receiver_state(monkeypatch):
    from types import SimpleNamespace
    from svx import inheritance

    instance = SimpleNamespace(_svx_initialized_python_portions={"py://Root"},
                               _svx_pending_python_portions=("py://Derived",))
    monkeypatch.setattr(inheritance, "_reserved_python_receivers", {})
    token = inheritance._pending_python_root.set(None)
    try:
        inheritance._complete_natural_constructor_portion(instance, 71, "py://Derived")
        assert instance._svx_initialized_python_portions == {"py://Root", "py://Derived"}
        assert instance._svx_pending_python_portions == ()
        assert instance._svx_pending_python_target_id is None
    finally:
        inheritance._pending_python_root.reset(token)


def test_manifest_planning_selects_independent_python_constructor_formals():
    from svx import inheritance
    from tests.integration.natural_constructor_planned_schema import manifest_data

    manifest = inheritance.parse_manifest(manifest_data())
    target = manifest.classes[0]
    root, python = target.base_lineage
    assert len(root.constructor.parameters) == 3
    assert len(python.constructor.parameters) == 4
    packages = inheritance._emit_sv_root_sv_packages(
        manifest, has_call_records=True, has_external_handles=True)
    proxy = packages["svx_proxy_natural_constructor_bridge"]
    assert "input int bias" in proxy
    assert ".bias = bias;" in proxy
    assert "svx-natural-constructor:" in proxy
    assert "svx-python-portion-init:" not in proxy
    assert "B_constructor_arguments::resume(this.__svx_remote_object_id)" in proxy


@pytest.mark.parametrize("empty_base", [False, True])
def test_generated_sv_constructor_wrappers_preserve_formals_and_zero_argument_boundary(empty_base):
    from dataclasses import replace
    import svtypes
    from svx import declarations, inheritance
    from tests.integration.natural_constructor_bridge_schema import manifest_data, PY_ID

    data = manifest_data()
    formals = ("object_id", "request", "result", "bytes", "prepared", "argument_result")
    data["classes"][0]["constructor"]["parameters"] = [
        declarations.inheritance_parameter(name, svtypes.Int) for name in formals]
    source = inheritance.parse_manifest(data).classes[0]
    python = replace(source, canonical_id=PY_ID, language="python",
                     symbol="tests.integration.natural_constructor_bridge.B")
    base = replace(source, constructor=replace(source.constructor, parameters=())) if empty_base else source
    lines, names = inheritance._emit_sv_natural_constructor_wrappers("Arguments", python, base)
    emitted = "\n".join(lines)
    assert names["object_id"] not in formals
    assert names["prepared"] not in formals
    for name in formals:
        assert f"input int {name}" in emitted
        assert f".{name} = {name};" in emitted
    assert "svx_inheritance_call_python_function" in emitted
    assert f"static function longint unsigned {names['prepare_id']}" in emitted
    assert f"{names['prepared']}.delete({names['object_id']})" in emitted
    if empty_base:
        assert "empty super constructor received arguments" in emitted
        assert "arguments have trailing bytes" not in emitted
    else:
        assert "arguments have trailing bytes" in emitted
        for name in formals:
            assert f"static function int {names['argument_' + name]}" in emitted
    projection = "\n".join(inheritance._emit_sv_projection_class(
        "Proxy", "MirrorPackage::Base", python, base_methods=(), dispatch_virtuals=(),
        reuse_base_object_id=True, super_accepts_object_id=True,
        delegate_unmatched_to_super=True, natural_constructor_base=base))
    assert "class Proxy extends MirrorPackage::Base" in projection
    assert "= svx_inheritance_registry::allocate_object_id()" in projection
    assert f"Proxy_constructor_arguments::{names['prepare_id']}" in projection
    assert f"Proxy_constructor_arguments::{names['resume']}(this.__svx_remote_object_id)" in projection
    assert "svx_inheritance_create_python_function" not in projection
    constructor_line = next(line for line in projection.splitlines() if "super.new(" in line)
    for parameter in base.constructor.parameters:
        assert f"Proxy_constructor_arguments::{names['argument_' + parameter.name]}" in constructor_line
    staged = "\n".join(inheritance._emit_sv_projection_class(
        "Proxy", "MirrorPackage::Base", python, base_methods=(), dispatch_virtuals=(),
        reuse_base_object_id=True, super_accepts_object_id=True,
        delegate_unmatched_to_super=True, natural_constructor_base=base,
        staged_python_root=python, constructor_python_portions=()))
    assert "this.__svx_reserve_early_receiver();" in staged
    assert "svx_construction_context" in staged
    assert "::leave(this, " in staged
    prototype = next(line for line in staged.splitlines() if "function new(" in line)
    assert prototype.index("::enter(") < prototype.index("__svx_prepare_natural_receiver(")
    assert "(this.__svx_remote_object_id," in staged
