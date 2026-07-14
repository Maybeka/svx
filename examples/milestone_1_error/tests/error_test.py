import svx


@svx.export
def main():
    svx.display("error test start")
    raise RuntimeError("intentional M1 fatal test")
