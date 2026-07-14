import svx


@svx.export
def main():
    svx.display("SVX M1: start")
    svx.delay(1.5, "ns")
    svx.display("SVX M1: after 1.5ns")
