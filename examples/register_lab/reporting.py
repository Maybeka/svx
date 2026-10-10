"""A small callback-only integration, independent of any verification framework."""

import svx
from svx.callbacks import Callback, CallbackAdapter


ADAPTER = CallbackAdapter("py://examples/register_lab/reporting/Report", (
    Callback("completed", "function"),
    Callback("settle", "task"),
))


class Report:
    def completed(self):
        from .extensions import policy
        assert policy().local_checks.value == 16
        svx.display("REGISTER_LAB_REPORT_FUNCTION_PASS")

    def settle(self):
        svx.delay(0.1, "ns")
        svx.display("REGISTER_LAB_REPORT_TASK_PASS")


@svx.export(name="register_lab.register_report")
def register_report():
    ADAPTER.register_type(Report)
