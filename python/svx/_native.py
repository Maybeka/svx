def _native():
    import _svx_native

    return _svx_native


def display(message: str) -> None:
    _native().display(str(message))


def delay(duration: float, unit_code: int) -> None:
    _native().delay(float(duration), int(unit_code))


def fork_join(callables):
    return _native().fork_join(tuple(callables))


def fork_join_any(callables):
    return _native().fork_join_any(tuple(callables))


def fork_join_none(callables):
    return _native().fork_join_none(tuple(callables))


def group_status(capsule):
    return _native().group_status(capsule)


def group_await(capsule) -> None:
    _native().group_await(capsule)


def group_kill(capsule) -> None:
    _native().group_kill(capsule)


def set_exception_policy(policy: str) -> None:
    _native().set_exception_policy(policy)


def inheritance_bind(object_id: int, instance) -> None:
    _native().inheritance_bind(object_id, instance)


def inheritance_unbind(object_id: int) -> None:
    _native().inheritance_unbind(object_id)


def inheritance_get(object_id: int):
    return _native().inheritance_get(object_id)


def inheritance_close(object_id: int) -> None:
    _native().inheritance_close(object_id)


def inheritance_call_sv(object_id: int, method_id: str, request: bytes) -> bytes:
    return _native().inheritance_call_sv(object_id, method_id, request)


def inheritance_create_sv(class_id: str, request: bytes) -> int:
    return int(_native().inheritance_create_sv(class_id, request))


def inheritance_stats() -> tuple[int, int]:
    count, nanoseconds = _native().inheritance_stats()
    return int(count), int(nanoseconds)


def inheritance_stats_reset() -> None:
    _native().inheritance_stats_reset()


def signal_declare(path: str, width: int, signed: bool) -> None:
    _native().signal_declare(path, int(width), bool(signed))


def signal_read(path: str) -> bytes:
    return _native().signal_read(path)


def signal_write(path: str, payload: bytes) -> None:
    _native().signal_write(path, payload)


def signal_force(path: str, payload: bytes) -> None:
    _native().signal_force(path, payload)


def signal_release(path: str) -> None:
    _native().signal_release(path)


def channel_put_payload(
    name: str,
    kind: str,
    type_name: str,
    content_type: str,
    data: bytes,
) -> None:
    _native().channel_put_payload(name, kind, type_name, content_type, data)


def channel_get_payload(name: str):
    return _native().channel_get_payload(name)


def channel_peek_payload(name: str):
    return _native().channel_peek_payload(name)


def channel_try_put_payload(
    name: str,
    kind: str,
    type_name: str,
    content_type: str,
    data: bytes,
) -> bool:
    return bool(
        _native().channel_try_put_payload(
            name, kind, type_name, content_type, data
        )
    )


def channel_try_get_payload(name: str):
    result = _native().channel_try_get_payload(name)
    if result is None:
        return None
    return result
