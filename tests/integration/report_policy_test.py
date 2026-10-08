import svx


@svx.export(name="report-policy.run")
def run():
    svx.set_exception_policy(svx.REPORT)
    raise RuntimeError("EXPECTED_REPORT_POLICY_ERROR")
