"""Runtime entry point: use the generated Python-to-SV proxy, not its source base."""

import svx
from svx_py.examples.foreign_handles.python_api import HandlePortal


@svx.export(name="foreign_handles.run")
def run():
    svx.publish_object("foreign-handles.portal", HandlePortal())
