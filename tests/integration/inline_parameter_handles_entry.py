import svx
from svx_mirror.inline_drivers_pkg import Driver, Holder


@svx.export(name='inline_handles.run')
def run():
    driver = Driver()
    default = driver.make_default(17)
    wide = driver.make_wide(29)
    assert driver.default_tag(default) == 17
    assert driver.explicit_default_tag(default) == 17
    assert driver.wide_tag(wide) == 29
    assert driver.echo(wide) == wide
    holder = Holder(wide)
    assert holder.tag() == 29
    assert holder.item.value == wide
    result, changed = svx.Output(), svx.Inout(wide)
    driver.exchange(wide, result, changed)
    assert result.value == wide and changed.value == wide
    typed = driver.make_typed()
    assert driver.typed_value(typed) == 37
    nested = driver.make_nested()
    assert driver.nested_value(nested) == 43
    try:
        driver.wide_tag(default)
    except (TypeError, ValueError, svx.SVXInheritanceError):
        pass
    else:
        raise AssertionError('different specializations accepted')
    mode_type = type(driver.mode.value)
    driver.mode.value = mode_type.ACTIVE
    assert driver.echo_mode(driver.mode.value) == mode_type.ACTIVE
    svx.display('INLINE_PARAMETER_HANDLES_PASS')
    svx.display('IMPORTED_CLASS_ENUM_EXCLUDED_BASE_PASS')
