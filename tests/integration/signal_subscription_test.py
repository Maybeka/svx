import svx
from svtypes import LogicValue

from .signal_subscription_declarations import (
    constant, data, driver, flag, huge, net, scalar, signed, wide,
)

subscriptions = []


@svx.export
def setup():
    for signal in (flag, data, constant, wide, huge, net):
        subscription = signal.subscribe()
        subscriptions.append(subscription)
        assert subscription.read() == signal.read(), signal.path
    assert subscriptions[2].read() == 0x13579bdf
    assert subscriptions[3].read() == LogicValue.from_string("x" * 65)
    assert subscriptions[4].read() == LogicValue.from_string("z" * 128)
    # Independent consumers on one HDL signal, not shared close ownership.
    subscriptions.append(data.subscribe())
    svx.display("SIGNAL_SUBSCRIPTION_SEED_PASS")


@svx.export
def immediate():
    assert data.read() == 0x87654321
    value = subscriptions[1].read()
    assert value in (0x12345678, 0x87654321)
    immediate_stale = value != data.read()
    svx.display(f"SIGNAL_SUBSCRIPTION_IMMEDIATE stale={immediate_stale}")


@svx.export
def settled():
    for signal, subscription in zip((flag, data, constant, wide, huge, net), subscriptions):
        assert subscription.read() == signal.read(), signal.path
    assert subscriptions[1].read() == 0x87654321
    assert subscriptions[6].read() == subscriptions[1].read()
    assert subscriptions[3].read() == LogicValue.from_string("1" + "xz10" * 16)
    assert subscriptions[4].read() == LogicValue.from_string("zx01" * 32)
    svx.display("SIGNAL_SUBSCRIPTION_SETTLED_PASS")


@svx.export
def unknown_two_state():
    with data.subscribe() as initial_unknown:
        for read in (data.read, subscriptions[1].read, subscriptions[6].read, initial_unknown.read):
            try:
                read()
            except svx.SVXSignalError as error:
                assert error.code == "state_domain_mismatch"
            else:
                raise AssertionError("two-state codec silently accepted X")
    svx.display("SIGNAL_SUBSCRIPTION_UNKNOWN_PASS")


@svx.test
def exercise():
    flag_cache, data_cache, _, wide_cache, huge_cache, net_cache, other = subscriptions
    data_cache.close()
    data_cache.close()
    try:
        data_cache.read()
    except svx.SVXSignalError as error:
        assert error.code == "subscription_closed"
    else:
        raise AssertionError("closed subscription was readable")
    data.write(9)
    svx.delay(1, "ns")
    assert other.read() == 9
    with data.subscribe() as reopened:
        assert reopened.read() == 9
        data.force(42)
        svx.delay(1, "ns")
        assert reopened.read() == data.read() == 42
        data.release()
        data.write(17)
        svx.delay(1, "ns")
        assert reopened.read() == other.read() == 17
    try:
        with flag.subscribe():
            raise ValueError("cleanup witness")
    except ValueError:
        pass
    net.force(LogicValue.from_string("10xz01z0"))
    svx.delay(1, "ns")
    assert net_cache.read() == net.read() == LogicValue.from_string("10xz01z0")
    driver.write(LogicValue.from_string("10101010"))
    svx.delay(1, "ns")
    assert net_cache.read() == LogicValue.from_string("10xz01z0")
    net.release()
    svx.delay(1, "ns")
    assert net_cache.read() == net.read() == LogicValue.from_string("10101010")
    retained = wide_cache.read()
    wide.write(LogicValue.from_string("z" * 65))
    huge.write(LogicValue.from_string("x" * 128))
    svx.delay(1, "ns")
    assert wide_cache.read() == wide.read() == LogicValue.from_string("z" * 65)
    assert huge_cache.read() == huge.read() == LogicValue.from_string("x" * 128)
    assert retained == LogicValue.from_string("1" + "xz10" * 16)
    flag.write(1)
    svx.delay(1, "ns")
    assert flag_cache.read() == flag.read() == 1
    with scalar.subscribe() as scalar_cache, signed.subscribe() as signed_cache:
        assert scalar_cache.read() == LogicValue.from_string("x")
        assert signed_cache.read() == -42
        for state in ("z", "1", "0", "x"):
            scalar.write(LogicValue.from_string(state))
            svx.delay(1, "ns")
            assert scalar_cache.read() == scalar.read() == LogicValue.from_string(state)
        signed.write(-123456)
        svx.delay(1, "ns")
        assert signed_cache.read() == signed.read() == -123456
    for subscription in subscriptions:
        subscription.close()
    # Intentionally left open: shutdown must retire it without invoking Python.
    subscriptions.append(data.subscribe())
    svx.display("SIGNAL_SUBSCRIPTION_PASS")
