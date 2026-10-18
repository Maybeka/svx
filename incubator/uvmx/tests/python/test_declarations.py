from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

import svx
from uvmx import Test, declared_tests, uvm_test


def test_declaration_registers_empty_phase_contracts() -> None:
    @uvm_test(
        canonical_id="py://uvmx/unit/RegisteredTest",
        factory_name="uvmx_registered_test",
    )
    class RegisteredTest(Test):
        def build_phase(self) -> None:
            pass

        def run_phase(self) -> None:
            pass

    declaration = next(
        item for item in declared_tests() if item.canonical_id == "py://uvmx/unit/RegisteredTest"
    )
    assert declaration.factory_name == "uvmx_registered_test"
    assert declaration.function_phases == ("build_phase",)
    assert declaration.task_phases == ("run_phase",)


def test_rejects_phase_with_user_parameters() -> None:
    with pytest.raises(TypeError, match="exactly one self"):

        @uvm_test(
            canonical_id="py://uvmx/unit/BadPhase",
            factory_name="uvmx_bad_phase",
        )
        class BadPhase(Test):
            def run_phase(self, value: int) -> None:
                pass


def test_rejects_duplicate_factory_name() -> None:
    @uvm_test(
        canonical_id="py://uvmx/unit/FirstDuplicate",
        factory_name="uvmx_duplicate_factory",
    )
    class FirstDuplicate(Test):
        pass

    with pytest.raises(ValueError, match="duplicate UVMX factory_name"):

        @uvm_test(
            canonical_id="py://uvmx/unit/SecondDuplicate",
            factory_name="uvmx_duplicate_factory",
        )
        class SecondDuplicate(Test):
            pass


def test_function_phase_rejects_delay_before_entering_native_runtime() -> None:
    @uvm_test(
        canonical_id="py://uvmx/unit/BlockingBuild",
        factory_name="uvmx_blocking_build",
    )
    class BlockingBuild(Test):
        def build_phase(self) -> None:
            svx.delay(1, "ns")

    from svx import _native
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(_native, "inheritance_get", lambda _id: BlockingBuild())
    try:
        with pytest.raises(svx.SVXContextError, match="executing SV function callback"):
            svx.inheritance.dispatch_python_call(
                1, "py://uvmx/unit/BlockingBuild#build_phase", b"", function_context=True
            )
    finally:
        monkeypatch.undo()


def test_constructor_rejects_delay_before_entering_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    bound: list[object] = []
    monkeypatch.setattr(svx.inheritance, "bind_instance", lambda _id, value: bound.append(value))
    monkeypatch.setattr(svx.inheritance, "unbind_instance", lambda _id: None)

    class BlockingConstructor(Test):
        def __init__(self) -> None:
            svx.delay(1, "ns")

    from svx.callbacks import CallbackAdapter
    adapter = CallbackAdapter("py://uvmx/unit/BlockingConstructor", ())
    adapter.register_type(BlockingConstructor)
    with pytest.raises(svx.SVXContextError, match="constructing an SV callback companion"):
        svx.inheritance.create_python_instance(adapter.class_id, 1, b"")
    assert len(bound) == 1


def test_generator_emits_deterministic_factory_proxy(tmp_path: Path) -> None:
    module = tmp_path / "generated_test.py"
    module.write_text(
        "from uvmx import Test, uvm_test\n"
        "@uvm_test(canonical_id='py://uvmx/unit/Generated', factory_name='uvmx_generated')\n"
        "class Generated(Test):\n"
        "    def build_phase(self): pass\n"
        "    def run_phase(self): pass\n",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location("generated_test", module)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)

    tool = Path(__file__).parents[2] / "tools" / "uvmx_gen.py"
    spec = importlib.util.spec_from_file_location("uvmx_gen", tool)
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    declarations = declared_tests("generated_test")
    output = generator.render_sv(declarations, "uvmx_generated_pkg")
    assert 'class uvmx_generated' not in output
    assert 'py://uvmx/unit/Generated' not in output
    assert 'uvmx_typed_base_factory' not in output  # Default bridge is built in.
    assert generator.render_sv((), 'uvmx_generated_pkg') == output


def test_generator_emits_each_supported_phase(tmp_path: Path) -> None:
    module = tmp_path / "all_phases.py"
    module.write_text(
        "from uvmx import Test, uvm_test\n"
        "@uvm_test(canonical_id='py://uvmx/unit/AllPhases', factory_name='uvmx_all_phases')\n"
        "class AllPhases(Test):\n"
        "    def build_phase(self): pass\n"
        "    def connect_phase(self): pass\n"
        "    def end_of_elaboration_phase(self): pass\n"
        "    def start_of_simulation_phase(self): pass\n"
        "    def run_phase(self): pass\n",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location("all_phases", module)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)

    tool = Path(__file__).parents[2] / "tools" / "uvmx_gen.py"
    spec = importlib.util.spec_from_file_location("uvmx_gen_all_phases", tool)
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    output = (Path(__file__).parents[2] / 'sv/uvmx_factory.sv').read_text()
    for phase in (
        "build_phase",
        "connect_phase",
        "end_of_elaboration_phase",
        "start_of_simulation_phase",
        "run_phase",
    ):
        assert f"virtual {'task' if phase == 'run_phase' else 'function void'} {phase}" in output


def test_inherited_python_phase_is_forwarded():
    class Parent(Test):
        def run_phase(self):
            pass

    @uvm_test(canonical_id="py://uvmx/unit/Inherited", factory_name="uvmx_inherited")
    class Child(Parent):
        pass

    declaration = next(item for item in declared_tests() if item.python_type is Child)
    assert declaration.task_phases == ("run_phase",)


def test_adding_python_tests_does_not_change_base_bridge_output():
    tool = Path(__file__).parents[2] / 'tools/uvmx_gen.py'
    spec = importlib.util.spec_from_file_location('uvmx_gen_invariance', tool)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    first = SimpleNamespace(sv_base='environment_pkg::BaseTest', factory_name='first')
    added = SimpleNamespace(sv_base='environment_pkg::BaseTest', factory_name='added')
    assert generator.render_sv([first], 'bridges') == generator.render_sv([first, added], 'bridges')
    assert generator.artifact_manifest([first], 'bridges') == generator.artifact_manifest([first, added], 'bridges')
    output = generator.render_sv([first, added], 'bridges')
    assert 'uvmx_typed_base_factory#(environment_pkg::BaseTest)' in output
    assert 'class added' not in output


def test_runtime_publishing_does_not_construct_user_tests(monkeypatch):
    from uvmx import bootstrap
    constructed = []

    class User(Test):
        def __init__(self):
            constructed.append(self)

    declaration = SimpleNamespace(canonical_id='py://uvmx/unit/RuntimeMetadata',
        factory_name='runtime_metadata', sv_base='uvm_pkg::uvm_test', python_type=User)
    monkeypatch.setattr(bootstrap, 'declared_tests', lambda: (declaration,))
    messages = []
    monkeypatch.setattr(bootstrap.svx, 'channel', lambda name:
        SimpleNamespace(put=messages.append))
    bootstrap._publish_tests()
    assert len(messages) == 2 and messages[-1].finished.value == 1
    assert messages[0].factory_name.value == 'runtime_metadata'
    assert not constructed


def test_fixed_callback_support_matches_public_generator():
    from uvmx.bootstrap import PHASE_ADAPTER
    support = Path(__file__).parents[2] / 'sv/uvmx_callbacks.sv'
    assert support.read_text() == PHASE_ADAPTER.render_sv('uvmx_phase_callbacks')


def test_inherited_async_phase_is_rejected_before_registration():
    class Parent(Test):
        async def run_phase(self):
            pass

    with pytest.raises(TypeError, match='synchronously'):
        uvm_test(canonical_id='py://uvmx/unit/AsyncInherited', factory_name='async_inherited')(
            type('Child', (Parent,), {}))


def test_inherited_constructor_arguments_are_rejected():
    class Parent(Test):
        def __init__(self, required):
            pass

    with pytest.raises(TypeError, match='no-user-argument'):
        uvm_test(canonical_id='py://uvmx/unit/ConstructorInherited', factory_name='constructor_inherited')(
            type('Child', (Parent,), {}))


def test_register_lab_extended_case_keeps_state_and_super_in_python(monkeypatch):
    from incubator.uvmx.examples.register_lab.python_test import PythonTest, PythonExtendedTest

    calls = []
    messages = []
    monkeypatch.setattr(PythonTest, 'run_phase', lambda self: calls.append(self))
    monkeypatch.setattr(svx, 'display', messages.append)
    instance = PythonExtendedTest()
    instance.build_phase()
    instance.run_phase()
    assert calls == [instance]
    assert instance.completed_runs == 1
    assert messages == ['REGISTER_LAB_UVMX_EXTENDED_BUILD_PASS', 'REGISTER_LAB_UVMX_EXTENDED_PASS']
    registered = {item.factory_name for item in declared_tests(PythonTest.__module__)}
    assert registered == {'register_lab_python_test', 'register_lab_extended_test'}


def test_cookbook_uvmx_markers_match_optional_sources():
    import re

    root = Path(__file__).resolve().parents[4]
    cookbook = (root / 'docs/SVX_COOKBOOK.zh-CN.md').read_text()
    optional = cookbook.split('### 7.1 ', 1)[1].split('### 7.2 ', 1)[0]
    source = (root / 'incubator/uvmx/examples/register_lab/python_test.py').read_text()
    markers = set(re.findall(r'REGISTER_LAB_[A-Z_]+', optional))
    assert markers == {'REGISTER_LAB_UVMX_EXTENDED_BUILD_PASS', 'REGISTER_LAB_UVMX_EXTENDED_PASS'}
    assert all(marker in source for marker in markers)
