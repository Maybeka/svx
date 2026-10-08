import svx
import os


_hosted = None


@svx.export(name="signature_types.run")
def run():
    from svx_mirror.signature_types_pkg import Base, Hosted

    class HostedDerived(Hosted):
        def __init__(self, seed):
            global _hosted
            super().__init__(seed)
            assert self.count.value == seed
            self.count.value = seed + 1
            _hosted = self
            if seed == 40:
                raise RuntimeError("existing SV object wrapper initialization failed")
        def check(self, value):
            assert value.x_mask == 0 and value.z_mask == 0
            return self.count.value + value.value_mask
    try:
        HostedDerived(20)
    except TypeError as error:
        assert "must be created by SV" in str(error)
    else:
        raise AssertionError("SV-initiated mirror allocated from Python")

    if (os.environ.get("SVX_CLOSE_FUNCTION") == "1"
            or os.environ.get("SVX_CLEANUP_WAIT_NEGATIVE") == "1"
            or os.environ.get("SVX_HANDOFF_TYPE_NEGATIVE") == "1"):
        class ClosingDerived(Base):
            def check(self, value):
                svx.close_instance(self)
                svx.close_instance(self)
                from svx import _native
                assert _native.inheritance_get(self._svx_remote_object_id) is None
                return 9
            def _svx_release_projected_fields(self):
                super()._svx_release_projected_fields()
                if os.environ.get("SVX_CLEANUP_WAIT_NEGATIVE") == "1":
                    svx.delay(1)
        svx.publish_object("signature_types.close_function", ClosingDerived(0))
        return
    value = Base(13)
    assert value.count.value == 13
    value.count.value = 19
    assert value.count.value == 19
    retained = value.count
    assert value.check(5) == 13
    assert value.check(255) == 263
    svx.close_instance(value)
    svx.close_instance(value)
    from svtypes import ExternalStorageError
    try:
        retained.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError("closed typed field remained readable")
    try:
        value.check(5)
    except svx.SVXRemoteError as error:
        assert "unknown" in str(error)
    else:
        raise AssertionError("closed specialization remained callable")
    svx.display("SIGNATURE_TYPES_RUNTIME_PASS")


@svx.export(name="signature_types.verify_hosted")
def verify_hosted():
    from svtypes import ExternalStorageError
    assert _hosted is not None
    assert _hosted.count.value == 21
    retained = _hosted.count
    svx.close_instance(_hosted)
    svx.close_instance(_hosted)
    try:
        retained.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError("SV-origin field view survived close")
    svx.display("SIGNATURE_TYPES_SV_ORIGIN_FIELD_PASS")


@svx.export(name="signature_types.wrap_existing")
def wrap_existing():
    from svtypes import ExternalStorageError
    from svx import _native
    target = type(_hosted)
    first = target.__svx_create_from_sv__(100001, 30)
    assert first.count.value == 31
    assert first._svx_remote_object_id == 100001
    svx.close_instance(first)
    try:
        target.__svx_create_from_sv__(100002, 40)
    except RuntimeError as error:
        assert "wrapper initialization failed" in str(error)
    else:
        raise AssertionError("existing-handle initializer failure was swallowed")
    assert _native.inheritance_get(100002) is None
    try:
        _hosted.count.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError("failed wrapper retained a live field view")
    # Rebind the same surviving SV object: the failed attempt wrote 41 before
    # raising, and must not have destroyed that object or its native endpoint.
    retry = target.__svx_create_from_sv__(100002, 41)
    assert retry.count.value == 42
    svx.close_instance(retry)
    svx.display("SIGNATURE_TYPES_EXISTING_FIELD_ROLLBACK_PASS")
