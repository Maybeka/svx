"""Public generated static bridge: source objects must never be allocated."""

import svx


class Source:
    calls = []

    def __new__(cls, *args, **kwargs):
        raise AssertionError('static bridge allocated a source object')

    @staticmethod
    def scale(delta):
        Source.calls.append(('scale', delta))
        return delta * 3

    @staticmethod
    def wait_once():
        svx.delay(2, 'ns')
        Source.calls.append(('wait',))

    @staticmethod
    def illegal_wait():
        svx.delay(1, 'ns')


@svx.test
def run():
    from svx_py.tests.integration.python_static_source import Source as View

    assert View.scale(11) == 33
    View.wait_once()
    assert Source.calls == [('scale', 7), ('wait',), ('scale', 11), ('wait',)]
    svx.display('PYTHON_STATIC_VIEW_PASS')
