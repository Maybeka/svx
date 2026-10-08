import svx


@svx.export(name="disable-finally-error.run")
def run():
    try:
        svx.delay(100, "ns")
    finally:
        raise RuntimeError("EXPECTED_DISABLED_FINALLY_ERROR")
