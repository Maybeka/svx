import svx


@svx.export(name="disable_external.run")
def run() -> None:
    svx.delay(100, "ns")
    raise AssertionError("external disable did not interrupt svx.delay()")
