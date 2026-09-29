import svx

from svx_py.tests.integration.external_handle_base import HandlePortal


@svx.export(name="external_handles.run")
def run():
    portal = HandlePortal()
    svx.publish_object("external-handles.portal", portal)
