import pytest

import svx.object_handoff as object_handoff
from svx import SVXInheritanceError, publish_object


class _Instance:
    _svx_remote_object_id = 17


def test_publish_object_requires_the_live_bound_instance(monkeypatch):
    instance = _Instance()
    published = []

    monkeypatch.setattr(
        object_handoff._native,
        "inheritance_get",
        lambda object_id: instance if object_id == 17 else None,
    )
    monkeypatch.setattr(
        object_handoff._native,
        "inheritance_publish",
        lambda name, object_id: published.append((name, object_id)),
    )

    publish_object("env.driver", instance)

    assert published == [("env.driver", 17)]


@pytest.mark.parametrize("name", ["", "bad\x00name", 17])
def test_publish_object_rejects_invalid_names(name, monkeypatch):
    monkeypatch.setattr(object_handoff._native, "inheritance_get", lambda _: _Instance())

    with pytest.raises(ValueError, match="published object name"):
        publish_object(name, _Instance())


def test_publish_object_rejects_unbound_instances(monkeypatch):
    instance = _Instance()
    monkeypatch.setattr(object_handoff._native, "inheritance_get", lambda _: None)

    with pytest.raises(SVXInheritanceError, match="currently bound"):
        publish_object("env.driver", instance)
