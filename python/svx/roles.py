from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from .channel import Channel, channel


T = TypeVar("T")
ReqT = TypeVar("ReqT")
RspT = TypeVar("RspT")


@dataclass(frozen=True)
class TypedRoleChannel(Generic[T]):
    name: str
    item_type: type[T]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_channel", channel(self.name))

    @property
    def raw(self) -> Channel:
        return self._channel

    def put(self, item: T) -> None:
        self._channel.put(item, self.item_type)

    def get(self) -> T:
        return self._channel.get(self.item_type)

    def peek(self) -> T:
        return self._channel.peek(self.item_type)

    def try_put(self, item: T) -> bool:
        return self._channel.try_put(item, self.item_type)

    def try_get(self) -> T | None:
        return self._channel.try_get(self.item_type)


class ReqChannel(TypedRoleChannel[T]):
    pass


class RspChannel(TypedRoleChannel[T]):
    pass


class MonChannel(TypedRoleChannel[T]):
    pass


class ConfigChannel(TypedRoleChannel[T]):
    pass


@dataclass(frozen=True)
class ReqRspChannel(Generic[ReqT, RspT]):
    base_name: str
    req_type: type[ReqT]
    rsp_type: type[RspT]

    def __post_init__(self) -> None:
        object.__setattr__(self, "req", ReqChannel(f"{self.base_name}.req", self.req_type))
        object.__setattr__(self, "rsp", RspChannel(f"{self.base_name}.rsp", self.rsp_type))

    def put(self, item: ReqT) -> None:
        self.req.put(item)

    def get(self) -> RspT:
        return self.rsp.get()

    def request(self, item: ReqT) -> RspT:
        self.put(item)
        return self.get()


def req_channel(name: str, item_type: type[T]) -> ReqChannel[T]:
    return ReqChannel(name, item_type)


def rsp_channel(name: str, item_type: type[T]) -> RspChannel[T]:
    return RspChannel(name, item_type)


def mon_channel(name: str, item_type: type[T]) -> MonChannel[T]:
    return MonChannel(name, item_type)


def config_channel(name: str, item_type: type[T]) -> ConfigChannel[T]:
    return ConfigChannel(name, item_type)


def reqrsp_channel(base_name: str, req_type: type[ReqT], rsp_type: type[RspT]) -> ReqRspChannel[ReqT, RspT]:
    return ReqRspChannel(base_name, req_type, rsp_type)
