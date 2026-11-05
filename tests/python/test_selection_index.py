from types import SimpleNamespace

import pytest

from svx.errors import SVXInheritanceError
import svx.sv_selection as selection


def test_qualified_selection_uses_index_and_preserves_ambiguities(monkeypatch):
    monkeypatch.setattr(selection, 'source_packages', lambda *a, **k: {'p': ()})
    facts = {name: SimpleNamespace(python_proxy_id=None) for name in (
        'p::A', 'p::B', '$unit[0]::p::A', '$instance[tb.owner]::p::A')}
    original = selection.matches_sv_selector
    calls = []
    def observed(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)
    monkeypatch.setattr(selection, 'matches_sv_selector', observed)
    assert selection.select_sv_classes([], facts, classes=['p::B']) == ('sv://p/B',)
    assert not calls
    for pattern in ('p::A', 'sv://p/A'):
        with pytest.raises(SVXInheritanceError, match='ambiguous'):
            selection.select_sv_classes([], facts, classes=[pattern])
    assert not calls
    selected = selection.select_sv_classes([], facts, classes=['p::*'])
    expected = tuple(selection._source_class_id(name) for name in sorted(facts)
                     if original(name, 'p::*'))
    assert selected == expected and calls


def test_canonical_qualified_selection_does_not_promote_relative_unit_class(monkeypatch):
    monkeypatch.setattr(selection, 'source_packages', lambda *a, **k: {'p': ()})
    facts = {name: SimpleNamespace(python_proxy_id=None) for name in ('p::A', '$unit[0]::p::A')}
    assert selection.select_sv_classes([], facts, classes=['sv://p/A']) == ('sv://p/A',)
    with pytest.raises(SVXInheritanceError, match='ambiguous'):
        selection.select_sv_classes([], facts, classes=['p::A'])
