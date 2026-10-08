"""Negative callback fixtures selected by the integration runner."""

import os

import svx
from tests.integration import external_handle_base, external_handle_test


def prohibited(vif):
    if os.environ.get("SVX_FUNCTION_NEGATIVE") == "task":
        vif.write(1)
    else:
        svx.delay(1, "ns")


def callback(self, vif):
    prohibited(vif)
    raise AssertionError("function callback accepted a prohibited operation")


external_handle_base.HandlePortal.round_trip_vif = callback
if os.environ.get("SVX_FUNCTION_REPORT") == "1":
    svx.set_exception_policy(svx.REPORT)
