from examples.milestone_5_existing_env.tests.types import M5BusObs, M5BusOp, M5BusReq, M5BusRsp


def main() -> None:
    print("// Generated from examples.milestone_5_existing_env.tests.types")
    print("// Do not edit by hand.")
    print()
    print(M5BusOp.to_sv_enum())
    print()
    print("typedef class M5BusReq;")
    print("typedef class M5BusRsp;")
    print("typedef class M5BusObs;")
    print()
    print(M5BusReq.to_sv_obj())
    print()
    print(M5BusRsp.to_sv_obj())
    print()
    print(M5BusObs.to_sv_obj())


if __name__ == "__main__":
    main()
