import svx
from svtypes import Bit, Int, SvObject, svobj


@svobj
class M2Transaction(SvObject):
    addr = Bit(16)
    data = Int()


@svx.export
def python_puts_typed():
    tx = M2Transaction()
    tx.addr.value = 0x1234
    tx.data.value = -7

    svx.channel("m2.typed.py_to_sv").put(tx)
    svx.display(
        f"python_puts_typed addr=0x{tx.addr.value:04x} data={tx.data.value}"
    )


@svx.export
def python_gets_typed():
    ch = svx.channel("m2.typed.sv_to_py")
    if ch.try_get(M2Transaction) is not None:
        raise AssertionError("try_get should be empty before SV typed put")

    rx = ch.get(M2Transaction)
    svx.display(f"python_gets_typed addr=0x{rx.addr.value:04x} data={rx.data.value}")

    if rx.addr.value != 0xABCD:
        raise AssertionError(f"unexpected addr: 0x{rx.addr.value:04x}")
    if rx.data.value != 0x10203040:
        raise AssertionError(f"unexpected data: {rx.data.value}")


@svx.export
def python_rejects_type_mismatch():
    ch = svx.channel("m2.typed.bad_type")
    try:
        ch.get(M2Transaction)
    except svx.SVXChannelError as exc:
        svx.display(f"python_rejects_type_mismatch caught {exc}")
        return
    raise AssertionError("typed channel accepted mismatched payload type")
