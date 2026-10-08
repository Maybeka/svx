import os

import svx
from svx_mirror.pure_virtual_pkg import Base


class Derived(Base):
    def check(self, value):
        if os.environ.get('SVX_PURE_BASE') == 'function':
            return super().check(value)
        return value + 7

    def update(self, delta, value, observed):
        if os.environ.get('SVX_PURE_BASE') == 'task':
            return super().update(delta, value, observed)
        svx.delay(2, 'ns')
        value.value += delta
        observed.value = value.value * 2


_instance = None


@svx.export(name='pure_virtual.run')
def run():
    global _instance
    value = Derived()
    _instance = value
    if not os.environ.get('SVX_PURE_BASE'):
        for method, arguments in (
            ('check', (3,)),
            ('update', (5, svx.Inout(11), svx.Output())),
        ):
            try:
                getattr(Base, method)(value, *arguments)
            except svx.SVXRemoteError as error:
                assert error.code == 'pure_virtual_base'
                assert error.object_id == value._svx_remote_object_id
                assert error.method_id == 'sv://pure_virtual_pkg/Base#' + method
                assert 'no base implementation' in error.remote_message
            else:
                raise AssertionError('pure-virtual base call unexpectedly succeeded')
        assert arguments[1].value == 11
        try:
            _ = arguments[2].value
        except svx.SVXInheritanceError as error:
            assert 'not available' in str(error)
        else:
            raise AssertionError('failed pure base call assigned its output')
        svx.display('PURE_VIRTUAL_BASE_ERROR_PASS')
    svx.publish_object('pure_virtual.instance', value)


@svx.export(name='pure_virtual.close')
def close():
    svx.close_instance(_instance)
