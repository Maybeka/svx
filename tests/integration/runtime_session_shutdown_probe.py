"""Check the Python shutdown boundary with the real SvTypes session API.

This does not exercise native/SV cancellation or interpreter finalization.
"""

import svtypes
import svx
from svx import _registry, runtime


@svtypes.svobj
class Value(svtypes.SvObject):
    count = svtypes.Int()


def run():
    assert runtime.state() is runtime.RuntimeState.UNINITIALIZED
    independent = svtypes.CodecSession(origin=2)
    independent_value = Value(session=independent)
    runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)
    runtime._native_finish_initialize()
    owned = runtime.codec_session()
    owned_value = Value(session=owned)
    assert owned.get(owned_value.svtypes_object_number) is owned_value

    @svx.export(name='shutdown_probe.entry')
    def entry():
        pass

    assert _registry.resolve('shutdown_probe.entry') is entry
    runtime._native_shutdown()
    assert runtime.state() is runtime.RuntimeState.STOPPED
    assert owned.get(owned_value.svtypes_object_number) is None
    assert independent.get(independent_value.svtypes_object_number) is independent_value
    assert _registry.list_exports() == {}
    for action in (runtime.codec_session,
                   lambda: runtime._native_initialize(runtime.SVX_RUNTIME_ABI_VERSION)):
        try:
            action()
        except svx.SVXError:
            pass
        else:
            raise AssertionError('stopped session remained accessible or restarted')
    runtime._native_shutdown()
    assert runtime.state() is runtime.RuntimeState.STOPPED
    assert independent.get(independent_value.svtypes_object_number) is independent_value
    independent.close()
    print('REAL_CODEC_SESSION_SHUTDOWN_PYTHON_BOUNDARY_PASS', flush=True)


if __name__ == '__main__':
    run()
