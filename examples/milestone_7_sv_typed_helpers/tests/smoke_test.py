import svx

from svtypes import clear_svx_object_registry

from .types import M7BusObs, M7BusOp, M7BusReq, M7BusRsp


def _req(tx_id: int, op: M7BusOp, addr: int, data: int = 0) -> M7BusReq:
    req = M7BusReq()
    req.id.value = tx_id
    req.op.value = op
    req.addr.value = addr
    req.data.value = data
    return req


def _check_rsp(rsp: M7BusRsp, tx_id: int, data: int) -> None:
    assert rsp.id.value == tx_id, f"rsp id mismatch: {rsp.id.value} != {tx_id}"
    assert rsp.ok.value == 1, f"rsp not ok for id {tx_id}"
    assert rsp.data.value == data, f"rsp data mismatch: 0x{rsp.data.value:08x} != 0x{data:08x}"


def _check_obs(obs: M7BusObs, req: M7BusReq, data: int) -> None:
    assert obs.id.value == req.id.value, f"obs id mismatch: {obs.id.value} != {req.id.value}"
    assert obs.op.value == req.op.value, f"obs op mismatch for id {req.id.value}"
    assert obs.addr.value == req.addr.value, f"obs addr mismatch for id {req.id.value}"
    assert obs.data.value == data, f"obs data mismatch: 0x{obs.data.value:08x} != 0x{data:08x}"


@svx.test
def test_smoke():
    clear_svx_object_registry()

    bus = svx.reqrsp_channel("m7.bus", M7BusReq, M7BusRsp)
    mon = svx.mon_channel("m7.bus.mon", M7BusObs)

    program = [
        (_req(1, M7BusOp.M7_OP_WRITE, 0x50, 0x77778888), 0x77778888),
        (_req(2, M7BusOp.M7_OP_READ, 0x50), 0x77778888),
    ]

    for req, expected in program:
        rsp = bus.request(req)
        _check_rsp(rsp, req.id.value, expected)
        obs = mon.get()
        _check_obs(obs, req, expected)

    svx.display(f"M7 SV typed helpers checked {len(program)} transactions")
