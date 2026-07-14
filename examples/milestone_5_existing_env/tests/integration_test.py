import svx

from svtypes import clear_svx_object_registry

from .types import M5BusObs, M5BusOp, M5BusReq, M5BusRsp


REQ_CH = "env.bus0.req"
RSP_CH = "env.bus0.rsp"
MON_CH = "env.bus0.mon"


def _req(tx_id: int, op: M5BusOp, addr: int, data: int = 0) -> M5BusReq:
    req = M5BusReq()
    req.id.value = tx_id
    req.op.value = op
    req.addr.value = addr
    req.data.value = data
    return req


def _expect_rsp(rsp: M5BusRsp, tx_id: int, data: int) -> None:
    assert rsp.id.value == tx_id, f"response id mismatch: {rsp.id.value} != {tx_id}"
    assert rsp.ok.value == 1, f"response not ok for id {tx_id}"
    assert rsp.data.value == data, f"response data mismatch for id {tx_id}: 0x{rsp.data.value:08x} != 0x{data:08x}"


def _expect_obs(obs: M5BusObs, req: M5BusReq, data: int) -> None:
    assert obs.id.value == req.id.value, f"monitor id mismatch: {obs.id.value} != {req.id.value}"
    assert obs.op.value == req.op.value, f"monitor op mismatch for id {req.id.value}"
    assert obs.addr.value == req.addr.value, f"monitor addr mismatch for id {req.id.value}"
    assert obs.data.value == data, f"monitor data mismatch for id {req.id.value}: 0x{obs.data.value:08x} != 0x{data:08x}"


@svx.export
def python_controlled_test():
    clear_svx_object_registry()

    req_ch = svx.channel(REQ_CH)
    rsp_ch = svx.channel(RSP_CH)
    mon_ch = svx.channel(MON_CH)

    program = [
        (_req(1, M5BusOp.M5_OP_WRITE, 0x10, 0x11112222), 0x11112222),
        (_req(2, M5BusOp.M5_OP_READ, 0x10), 0x11112222),
        (_req(3, M5BusOp.M5_OP_WRITE, 0x20, 0x33334444), 0x33334444),
        (_req(4, M5BusOp.M5_OP_READ, 0x20), 0x33334444),
    ]

    for req, expected_data in program:
        svx.display(
            f"M5 Python sends id={req.id.value} op={req.op.value.name} "
            f"addr=0x{req.addr.value:02x} data=0x{req.data.value:08x}"
        )
        req_ch.put(req)

        rsp = rsp_ch.get(M5BusRsp)
        _expect_rsp(rsp, req.id.value, expected_data)

        obs = mon_ch.get(M5BusObs)
        _expect_obs(obs, req, expected_data)

    svx.display(f"M5 Python checked {len(program)} transactions")


@svx.export
def python_checker_failure_demo():
    clear_svx_object_registry()

    req_ch = svx.channel(REQ_CH)
    rsp_ch = svx.channel(RSP_CH)

    req = _req(101, M5BusOp.M5_OP_WRITE, 0x30, 0x55556666)
    svx.display("M5 Python checker-failure demo sends one transaction")
    req_ch.put(req)

    rsp = rsp_ch.get(M5BusRsp)
    _expect_rsp(rsp, req.id.value, 0xDEADBEEF)
