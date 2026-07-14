import svx


@svx.export
def python_puts_payload():
    ch = svx.channel("m2.py_to_sv")
    ch.put_payload(
        bytes([0x00, 0x01, 0x02, 0x7F, 0x80, 0xFF]),
        kind="bytes",
        content_type="application/octet-stream",
    )
    ok = svx.channel("m2.py_try_put_to_sv").try_put_payload(
        b"try-put-ok",
        kind="trace",
        type_name="ascii",
        content_type="text/plain",
    )
    if not ok:
        raise AssertionError("try_put_payload unexpectedly failed")
    svx.display("python_puts_payload done")


@svx.export
def python_gets_payload():
    ch = svx.channel("m2.sv_to_py")
    if ch.try_get_payload() is not None:
        raise AssertionError("try_get_payload should be empty before SV put")

    payload = ch.peek_payload()
    if payload.data != bytes.fromhex("deadbeef001122"):
        raise AssertionError(f"unexpected peek payload data: {payload.data.hex()}")

    payload = ch.get_payload()
    svx.display(
        f"python_gets_payload kind={payload.kind} type={payload.type_name} "
        f"content={payload.content_type} data={payload.data.hex()}"
    )

    if payload.kind != "trace":
        raise AssertionError(f"unexpected kind: {payload.kind!r}")
    if payload.type_name != "raw.bytes":
        raise AssertionError(f"unexpected type_name: {payload.type_name!r}")
    if payload.content_type != "application/octet-stream":
        raise AssertionError(f"unexpected content_type: {payload.content_type!r}")
    if payload.data != bytes.fromhex("deadbeef001122"):
        raise AssertionError(f"unexpected payload data: {payload.data.hex()}")


@svx.export
def python_puts_large_payload():
    data = bytes((i & 0xFF) for i in range(1024 * 1024))
    svx.channel("m2.large_py_to_sv").put_payload(
        data,
        kind="bytes",
        type_name="large.pattern",
        content_type="application/octet-stream",
    )
    svx.display(f"python_puts_large_payload size={len(data)}")
