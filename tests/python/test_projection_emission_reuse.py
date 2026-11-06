from dataclasses import replace

import pytest

from svx import inheritance as bridge
from svx.generated_names import sv_name_scope


def test_record_label_formatting_is_lazy_and_names_remain_collision_safe(monkeypatch):
    original = bridge.readable
    calls = []

    def readable(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(bridge, 'readable', readable)
    with sv_name_scope():
        first = bridge._call_record_class_name('sv://p/A#f', 'request')
        assert bridge._call_record_class_name('sv://p/A#f', 'request') == first
        assert bridge._call_record_class_name('sv://q/A#f', 'request') != first
        assert len(calls) == 2


def test_shared_lineage_prefixes_retain_complete_ancestry_and_conflict_context():
    from test_m8_inheritance import manifest_data
    model = bridge.parse_manifest(manifest_data())
    root = replace(model.classes[0], base_lineage=())
    ancestors = [root]
    targets = []
    for index in range(1, 40):
        node = replace(root, canonical_id=f'sv://deep/C{index}', base_lineage=())
        targets.append(replace(node, base_lineage=tuple(ancestors)))
        ancestors.append(node)
    manifest = replace(model, classes=tuple(targets))
    contexts = bridge._manifest_lineage_contexts(manifest)
    for index, node in enumerate(ancestors):
        assert contexts[node.canonical_id] == tuple(ancestors[:index])
    conflicting = replace(ancestors[-1], base_lineage=(ancestors[0], ancestors[2]))
    with pytest.raises(bridge.SVXInheritanceError, match=r'conflicting lineage ancestry.*target.*has.*target.*has'):
        bridge._manifest_lineage_contexts(replace(manifest, classes=(*targets, conflicting)))
