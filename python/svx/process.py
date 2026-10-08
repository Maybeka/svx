from __future__ import annotations

from enum import Enum

from . import _native
from .callback_context import require_blocking_operations_allowed


class ProcessStatus(Enum):
    FINISHED = "finished"
    RUNNING = "running"
    KILLED = "killed"
    UNKNOWN = "unknown"


class ProcessGroup:
    def __init__(self, capsule):
        self._capsule = capsule

    def status(self) -> ProcessStatus:
        return ProcessStatus(_native.group_status(self._capsule))

    def await_(self) -> None:
        require_blocking_operations_allowed("svx.ProcessGroup.await_()")
        _native.group_await(self._capsule)

    def kill(self) -> None:
        require_blocking_operations_allowed("svx.ProcessGroup.kill()")
        _native.group_kill(self._capsule)

    def kill_running(self) -> None:
        self.kill()
