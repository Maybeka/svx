import pytest

from svx import SVMirror, SVXInheritanceError, sv_mirror
from svx import declarations


@pytest.fixture(autouse=True)
def isolated_source_mirrors(monkeypatch):
    monkeypatch.setattr(declarations, "_source_mirror_declarations", {})
    monkeypatch.setattr(declarations, "_source_mirror_implementations", {})


@pytest.mark.parametrize("generated_first", [False, True])
def test_empty_source_mirror_keeps_existing_child_identity_and_super(generated_first):
    class Implementation(SVMirror):
        __svx_foreign_class_id__ = "sv://binding/A"

        def __init__(self, seed):
            self.seed = seed

        def check(self, value):
            return self.seed + value

    if generated_first:
        declarations._register_source_mirror_implementation("sv://binding/A", Implementation)

    @sv_mirror("sv://binding/A")
    class AMirror(SVMirror):
        pass

    class B(AMirror):
        def __init__(self, seed):
            super().__init__(seed + 1)

        def check(self, value):
            return super().check(value) + 100

    original = B
    declarations._register_source_mirror_implementation("sv://binding/A", Implementation)
    instance = B(7)
    assert B is original and B.__bases__ == (AMirror,)
    assert AMirror.__bases__ == (Implementation,)
    assert isinstance(instance, Implementation)
    assert instance.check(2) == 110


def test_generated_source_mirror_conflict_is_explicit():
    one = type("One", (SVMirror,), {"__svx_foreign_class_id__": "sv://binding/A"})
    two = type("Two", (SVMirror,), {"__svx_foreign_class_id__": "sv://binding/A"})
    declarations._register_source_mirror_implementation("sv://binding/A", one)
    source = sv_mirror("sv://binding/A")(type("Source", (SVMirror,), {}))
    with pytest.raises(SVXInheritanceError, match="conflicting generated"):
        declarations._register_source_mirror_implementation("sv://binding/A", two)
    assert source.__bases__ == (one,)


def test_unloaded_source_mirror_does_not_construct_a_disconnected_python_object():
    @sv_mirror("sv://binding/Unloaded")
    class Source(SVMirror):
        pass

    with pytest.raises(SVXInheritanceError, match="generated mirror.*not loaded"):
        Source()


def test_late_binding_installs_failure_guard_on_preexisting_children():
    @sv_mirror("sv://binding/Guarded")
    class Source(SVMirror):
        pass

    class Child(Source):
        def __init__(self):
            super().__init__()

    implementation = type("Implementation", (SVMirror,), {
        "__svx_foreign_class_id__": "sv://binding/Guarded",
        "__svx_guard_descendant_initializers__": True})
    declarations._register_source_mirror_implementation("sv://binding/Guarded", implementation)
    initializer = Child.__init__
    assert initializer.__svx_initializer_guard__
    declarations._register_source_mirror_implementation("sv://binding/Guarded", implementation)
    assert Child.__init__ is initializer
