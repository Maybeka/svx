from pathlib import PurePosixPath
import json
import pytest

from svx.inheritance import (
    _sv_root_artifact_portions, _sv_root_construction_plan, _emit_sv_root_sv_packages,
    _emit_sv_root_artifacts, artifact_manifest, parse_manifest,
    _emit_sv_projection_class,
    _dispatch_python_call, _PYTHON_CALLBACK_METHOD_PREFIX,
    emit_python_mirrors, _PendingPythonRoot, _pending_python_root,
    _initialize_pending_python_root, _PYTHON_ROOT_ALLOC_PREFIX,
)
from tests.integration.sv_root_target_schema import emit_sources, manifest_data


def test_sv_root_final_view_has_complete_fields_and_first_python_source_owner():
    manifest, python, sv = emit_sources()
    view = python[PurePosixPath('svx_mirror/sv_root_child_pkg.py')]
    assert "'count': 'sv://sv_root_pkg/A.count'" in view
    assert "'retry': 'py://tests/integration/sv_root/B.retry'" in view
    assert "'extra': 'sv://sv_root_child_pkg/C.extra'" in view
    assert "'sv://sv_root_pkg/A': 'py://tests/integration/sv_root/B'" in view
    companion = python[PurePosixPath('svx_py/tests/integration/sv_root_target_test.py')]
    assert "    def __init__(self, *args, **kwargs):\n" in companion
    assert companion.index('_Owner.__init__(self)') < companion.index('_Source.__init__(self, *args, **kwargs)')
    for path, text in python.items():
        compile(text, str(path), 'exec')
    root = sv[PurePosixPath('a.svh')]
    assert 'this.__svx_python_constructor_target()' in root
    assert '{"svx-python-root-init:", this.__svx_python_constructor_target()}' in root
    metadata = artifact_manifest(manifest, python, sv_sources=sv)
    types = {entry['canonical_class_id']: entry for entry in metadata['generated_types']}
    assert types['sv://sv_root_child_pkg/C']['python_fqn'] == 'svx_mirror.sv_root_child_pkg.C'


def test_sv_root_metadata_does_not_claim_unemitted_terminal_view():
    manifest, python, sv = emit_sources()
    del python[PurePosixPath('svx_mirror/sv_root_child_pkg.py')]
    metadata = artifact_manifest(manifest, python, sv_sources=sv)
    assert not any(entry['canonical_class_id'] == 'sv://sv_root_child_pkg/C'
                   for entry in metadata['generated_types'])


def test_first_python_proxy_initializes_after_its_own_field_declarations():
    manifest = parse_manifest(manifest_data())
    packages = _emit_sv_root_sv_packages(manifest, has_call_records=True)
    root = packages['svx_mirror_sv_sv_root_pkg_A']
    proxy = packages['svx_proxy_sv_root_target_test']
    assert 'Reserve now; the first Python proxy initializes after its field declarations.' in root
    assert 'this.__svx_reserve_early_receiver();\n      end else begin' in root
    constructor = proxy[proxy.index('    function new('):]
    assert constructor.index('super.new(') < constructor.index('B_constructor_arguments::resume(')
    assert 'svx-natural-constructor:' in proxy
    assert 'svx-python-root-init:' not in constructor
    assert 'svx-python-portion-init:py://tests/integration/sv_root/B' not in constructor


def test_sv_root_plans_derive_first_python_and_ordered_later_portions():
    manifest = parse_manifest(manifest_data(extended=True))
    portions = {source.canonical_id: source for source in _sv_root_artifact_portions(manifest)}
    assert set(portions) == {
        'sv://sv_root_pkg/A', 'py://tests/integration/sv_root/B', 'sv://sv_root_child_pkg/C',
        'py://tests/integration/sv_root/D', 'sv://sv_root_e_pkg/E',
    }
    first = _sv_root_construction_plan(portions['sv://sv_root_pkg/A'], manifest=manifest)
    assert first.first_python.canonical_id == 'py://tests/integration/sv_root/B'
    final = _sv_root_construction_plan(portions['sv://sv_root_e_pkg/E'], manifest=manifest)
    assert final.root.canonical_id == 'sv://sv_root_pkg/A'
    assert final.first_python == first.first_python
    assert final.preceding_python.canonical_id == 'py://tests/integration/sv_root/D'
    assert [source.canonical_id for source in final.python_portions] == ['py://tests/integration/sv_root/D']


def test_sv_root_target_only_e_materializes_edges_without_creating_new_targets():
    data = manifest_data(extended=True)
    data['classes'] = data['classes'][-1:]
    manifest = parse_manifest(data)
    packages = _emit_sv_root_sv_packages(manifest, has_call_records=True)
    assert len(manifest.classes) == 1
    assert set(packages) == {
        'svx_mirror_sv_sv_root_pkg_A', 'svx_proxy_sv_root_target_test',
        'svx_mirror_sv_sv_root_child_pkg_C', 'svx_proxy_sv_root_target_derived',
        'svx_mirror_sv_sv_root_e_pkg_E',
    }
    assert 'class D extends svx_mirror_sv_sv_root_child_pkg_C::C' in packages['svx_proxy_sv_root_target_derived']
    assert 'svx-natural-constructor:' in packages['svx_proxy_sv_root_target_derived']
    assert 'D_constructor_arguments::resume(' in packages['svx_proxy_sv_root_target_derived']
    assert 'svx-python-portion-init:' not in packages['svx_proxy_sv_root_target_derived']
    python = _emit_sv_root_artifacts(manifest)
    view = python[PurePosixPath('svx_mirror/sv_root_e_pkg.py')]
    assert "__svx_constructor_python_portions__ = ('py://tests/integration/sv_root/D',)" in view
    assert "'sv://sv_root_child_pkg/C': 'py://tests/integration/sv_root/D'" in view
    assert "'own': 'py://tests/integration/sv_root/D.own'" in view


def test_sv_root_python_terminal_d_does_not_manufacture_a_d_proxy_or_project_local_fields():
    data = manifest_data(extended=True)
    data['classes'] = data['classes'][1:2]
    manifest = parse_manifest(data)
    packages = _emit_sv_root_sv_packages(manifest, has_call_records=True)
    assert 'svx_proxy_sv_root_target_derived' not in packages
    python = _emit_sv_root_artifacts(manifest)
    assert PurePosixPath('svx_py/tests/integration/sv_root_target_derived.py') not in python
    view = python[PurePosixPath('svx_mirror/sv_root_child_pkg.py')]
    assert 'py://tests/integration/sv_root/D.own' not in view


def test_internal_sv_root_context_preserves_ordinary_source_constructor_arguments():
    _, _, sources = emit_sources(extended=True)
    for path in ('a.svh', 'c.svh', 'e.svh'):
        source = sources[PurePosixPath(path)]
        assert 'typedef svx_pkg::svx_construction_context __svx_construction_context_type;' in source
        enter = source.index('__svx_construction_context_type::enter(object_id, this)')
        parent = source.index('super.new();', enter)
        leave = source.index('__svx_construction_context_type::leave(this, scope_owned)', parent)
        assert enter < parent < leave
        assert 'super.new(object_id)' not in source
    root = sources[PurePosixPath('a.svh')]
    assert root.index('__svx_construction_context_type::current_id(this)') < root.index(
        'svx_inheritance_registry::register_object')
    for path in ('b.svh', 'd.svh'):
        source = sources[PurePosixPath(path)]
        constructor = source[source.index('    function new('):]
        assert constructor.index('::enter(') < constructor.index('__svx_prepare_natural_receiver(')
        assert constructor.index('super.new(') < constructor.index('::resume(') < constructor.index('::leave(')


def test_default_projection_does_not_enable_experimental_construction_context():
    source = parse_manifest(manifest_data()).classes[0]
    generated = '\n'.join(_emit_sv_projection_class(
        'C', source.symbol, source, base_methods=source.methods,
        dispatch_virtuals=(), reuse_base_object_id=True))
    assert 'svx_construction_context' not in generated
    assert 'super.new(object_id);' in generated


def test_internal_constructor_context_does_not_shadow_user_formals():
    data = manifest_data()
    source_data = data['classes'][0]
    binding = source_data['fields'][0]['type']
    source_data['constructor']['parameters'] = [
        {'name': name, 'type': binding} for name in ('object_id', 'scope_owned')]
    source = parse_manifest(data).classes[0]
    generated = '\n'.join(_emit_sv_projection_class(
        'C', source.symbol, source, base_methods=source.methods,
        dispatch_virtuals=(), reuse_base_object_id=True,
        transparent_construction=True))
    assert 'super.new(object_id, scope_owned);' in generated
    assert 'bit scope_owned = ' not in generated
    assert 'svx_construction_context::enter(object_id, this)' not in generated
    assert '__svx_construction_context_type::enter(' in generated


@pytest.mark.parametrize('formal', ['svx_construction_context', 'svx_pkg',
                                    '__svx_construction_context_type'])
def test_constructor_context_type_alias_avoids_user_formal_names(formal):
    data = manifest_data()
    source_data = data['classes'][0]
    binding = source_data['fields'][0]['type']
    source_data['constructor']['parameters'] = [{'name': formal, 'type': binding}]
    source = parse_manifest(data).classes[0]
    generated = '\n'.join(_emit_sv_projection_class(
        'C', source.symbol, source, base_methods=source.methods,
        dispatch_virtuals=(), reuse_base_object_id=True,
        transparent_construction=True))
    alias = next(line.split()[-1].rstrip(';') for line in generated.splitlines()
                 if 'typedef svx_pkg::svx_construction_context ' in line)
    assert alias != formal
    assert f'super.new({formal});' in generated
    assert f'{alias}::enter(' in generated
    assert f'{alias}::leave(' in generated


def test_inherited_virtual_slot_uses_ancestor_contract_and_current_mirror_boundary():
    _, _, sources = emit_sources(extended=True, inherited_slot=True)
    source = sources[PurePosixPath('c.svh')]
    route = 'svx-python-callback:' + json.dumps({
        'boundary': 'sv://sv_root_child_pkg/C',
        'method': 'py://tests/integration/sv_root/B#check'}, separators=(',', ':'))
    assert 'virtual function int check();' in source
    assert json.dumps(route) in source
    assert '"sv://sv_root_child_pkg/C#check": begin' not in source
    assert 'svx-python-callback:' not in sources[PurePosixPath('a.svh')]


@pytest.mark.parametrize('route', ['broken', '[]', '{}',
                                   '{"boundary":1,"method":"sv://A#check"}',
                                   '{"boundary":"sv://C","method":""}'])
def test_invalid_inherited_callback_route_is_rejected_before_native_lookup(route):
    from svx import SVXInheritanceError
    with pytest.raises(SVXInheritanceError, match='invalid inherited callback route'):
        _dispatch_python_call(99, _PYTHON_CALLBACK_METHOD_PREFIX + route, b'')


def test_shared_sv_root_defers_first_python_selection_to_each_target():
    manifest, python, sv = emit_sources(branches=True)
    root = manifest.classes[0].base_lineage[0]
    assert _sv_root_construction_plan(root, manifest=manifest).first_python is None
    first = _sv_root_construction_plan(manifest.classes[0], manifest=manifest)
    other = _sv_root_construction_plan(manifest.classes[1], manifest=manifest)
    assert first.first_python.canonical_id == 'py://tests/integration/sv_root/B'
    assert other.first_python.canonical_id == 'py://tests/integration/sv_root/B2'
    assert 'py://tests/integration/sv_root/B' not in sv[PurePosixPath('a.svh')]
    root_view = python[PurePosixPath('svx_mirror/sv_root_pkg.py')]
    assert "register_python_subclass('sv://sv_root_pkg/A', A)" in root_view
    assert "register_python_subclass('sv://sv_root_pkg/A', cls)" not in root_view
    default_view = emit_python_mirrors(manifest)[PurePosixPath('svx_mirror/sv_root_pkg.py')]
    assert "register_python_subclass('sv://sv_root_pkg/A', cls)" in default_view


@pytest.mark.parametrize('selection', ['broken', '{}',
    '{"root":"py://B2","target":"sv://C","portions":[]}',
    '{"root":"py://B","target":"sv://Wrong","portions":[]}',
    '{"root":"py://B","target":"sv://C","portions":["py://D"]}'])
def test_pending_root_selector_must_match_receiver_plan(selection):
    from svx import SVXInheritanceError

    class Receiver:
        __svx_foreign_class_id__ = 'sv://C'

    pending = _PendingPythonRoot(Receiver(), 'py://B')
    token = _pending_python_root.set(pending)
    try:
        with pytest.raises(SVXInheritanceError):
            _initialize_pending_python_root(_PYTHON_ROOT_ALLOC_PREFIX + selection, 91, b'')
        assert pending.object_id is None and not pending.initialized
    finally:
        _pending_python_root.reset(token)


def test_ordinary_sv_middle_members_share_final_helper_without_extra_projection():
    manifest, python, sv = emit_sources(ordinary_middle=True)
    assert len(manifest.classes) == 1
    assert set(sv) == {PurePosixPath(path) for path in ('common.svh', 'a.svh', 'b.svh', 'c.svh')}
    source = sv[PurePosixPath('c.svh')]
    assert '"sv://sv_root_middle_pkg/Middle.middle@svx_field_read": begin' in source
    assert '"sv://sv_root_middle_pkg/Middle#check": begin' in source
    assert 'sv_root_middle_pkg::Middle::check()' in source
    assert 'sv_root_middle_pkg::Middle::middle_value()' in source
    view = python[PurePosixPath('svx_mirror/sv_root_child_pkg.py')]
    assert "'middle': 'sv://sv_root_middle_pkg/Middle.middle'" in view
    assert '    middle = ' in view and '    def middle_value(self):' in view
    assert 'sv://sv_root_middle_pkg/Middle#middle_value' in view
    assert PurePosixPath('svx_mirror/sv_root_middle_pkg.py') not in python
    assert view.count('    def check(') == 1
    assert 'sv://sv_root_child_pkg/C#check' in view
    assert '    def middle_scale(value):' in view
    assert "invoke_sv_static('sv://sv_root_middle_pkg/Middle', 'sv://sv_root_middle_pkg/Middle#middle_scale'" in view
    assert "invoke_sv_static('sv://sv_root_child_pkg/C', 'sv://sv_root_child_pkg/C#scale'" in view
    assert view.count('    def scale(') == 1
    assert 'virtual class Middle_static_gateway extends sv_root_middle_pkg::Middle;' in source
    assert 'sv_root_middle_pkg::Middle::middle_scale(' in source
    assert 'register_static("sv://sv_root_middle_pkg/Middle", this)' in source
    assert 'register_static("sv://sv_root_child_pkg/C", this)' in source
    assert 'class Middle_factory' not in source
    for path, text in python.items():
        compile(text, str(path), 'exec')


def test_shared_middle_static_gateway_is_emitted_once_for_multiple_targets():
    _, python, sv = emit_sources(ordinary_middle=True, extended=True)
    combined = '\n'.join(sv.values())
    assert combined.count('register_static("sv://sv_root_middle_pkg/Middle", this)') == 1
    assert combined.count('register_static("sv://sv_root_pkg/A", this)') == 1
    assert 'sv://sv_root_middle_pkg/Middle#middle_wait' in python[PurePosixPath('svx_mirror/sv_root_child_pkg.py')]
    assert PurePosixPath('svx_mirror/sv_root_middle_pkg.py') not in python


def test_sv_prefix_keeps_logical_root_but_allocates_only_first_boundary_mirror():
    manifest, python, sv = emit_sources(sv_prefix=True)
    portions = {source.canonical_id: source for source in _sv_root_artifact_portions(manifest)}
    assert len(manifest.classes) == 1
    assert 'sv://sv_root_prefix_pkg/Z' not in portions
    for source in portions.values():
        plan = _sv_root_construction_plan(source, manifest=manifest)
        assert plan.root.canonical_id == 'sv://sv_root_prefix_pkg/Z'
        assert plan.bridge_root.canonical_id == 'sv://sv_root_pkg/A'
        assert plan.first_python.canonical_id == 'py://tests/integration/sv_root/B'
    assert set(sv) == {PurePosixPath(path) for path in ('common.svh', 'a.svh', 'b.svh', 'c.svh')}
    root = sv[PurePosixPath('a.svh')]
    assert 'class A extends sv_root_pkg::A' in root
    assert 'longint unsigned __svx_remote_object_id;' in root
    assert 'sv_root_prefix_pkg::Z::prefix_value()' in root
    assert 'sv://sv_root_prefix_pkg/Z.prefix_count@svx_field_read' in root
    assert 'virtual function int prefix_virtual()' in root
    assert 'register_static("sv://sv_root_prefix_pkg/Z", this)' in root
    view = python[PurePosixPath('svx_mirror/sv_root_pkg.py')]
    assert '    prefix_count = ' in view
    assert "'prefix_count': 'sv://sv_root_prefix_pkg/Z.prefix_count'" in view
    assert 'sv://sv_root_prefix_pkg/Z#prefix_value' in view
    assert "invoke_sv_static('sv://sv_root_prefix_pkg/Z', 'sv://sv_root_prefix_pkg/Z#prefix_scale'" in view
    assert PurePosixPath('svx_mirror/sv_root_prefix_pkg.py') not in python
    metadata = artifact_manifest(manifest, python, sv_sources=sv)
    assert all(entry['canonical_class_id'] != 'sv://sv_root_prefix_pkg/Z' for entry in metadata['generated_types'])
    for path, text in python.items():
        compile(text, str(path), 'exec')


def test_shared_sv_prefix_preserves_per_target_first_python_selection():
    manifest, _, _ = emit_sources(sv_prefix=True, branches=True)
    portions = {source.canonical_id: source for source in _sv_root_artifact_portions(manifest)}
    root = _sv_root_construction_plan(portions['sv://sv_root_pkg/A'], manifest=manifest)
    assert root.first_python is None
    for target, first_python in [('sv://sv_root_child_pkg/C', 'py://tests/integration/sv_root/B'),
                                 ('sv://sv_root_branch_pkg/C2', 'py://tests/integration/sv_root/B2')]:
        plan = _sv_root_construction_plan(portions[target], manifest=manifest)
        assert plan.root == root.root and plan.bridge_root == root.bridge_root
        assert plan.first_python.canonical_id == first_python
