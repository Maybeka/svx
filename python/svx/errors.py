FATAL = "fatal"
REPORT = "report"


class SVXError(RuntimeError):
    """Base class for SVX-specific errors."""


class SVXContextError(SVXError):
    """Raised when an SVX primitive is called outside an SVX context."""


class SVXCancellationError(SVXError):
    """Raised internally when an SVX process is stopped cooperatively."""


class SVXExportError(SVXError):
    """Raised when export registration or resolution fails."""


class SVXChannelError(SVXError):
    """Raised when channel payload metadata or typed conversion is invalid."""


class SVXSignalError(SVXError):
    """Raised when hierarchical signal resolution or access fails."""

    def __init__(
        self,
        path: str,
        operation: str,
        message: str,
        code: str = "signal_error",
        vpi_type: str = "",
    ) -> None:
        self.code = code
        self.path = path
        self.operation = operation
        self.vpi_type = vpi_type or None
        super().__init__(f"signal {operation} {path!r} failed [{code}]: {message}")


class SVXInheritanceError(SVXError):
    """Raised when a cross-language inheritance declaration is invalid."""


class SVXRemoteError(SVXInheritanceError):
    """Raised when a declared foreign object or method call fails."""

    def __init__(self, object_id: int, method_id: str, message: str, *, code: str = "remote_error") -> None:
        self.code = code
        self.object_id = object_id
        self.method_id = method_id
        self.remote_message = message
        super().__init__(f"inheritance call {method_id} on object {object_id} failed [{code}]: {message}")


_exception_policy = FATAL


def set_exception_policy(policy: str) -> None:
    global _exception_policy
    if policy not in (FATAL, REPORT):
        raise ValueError(f"unsupported SVX exception policy: {policy!r}")
    _exception_policy = policy

    try:
        from . import _native

        _native.set_exception_policy(policy)
    except ImportError:
        pass


def get_exception_policy() -> str:
    return _exception_policy
