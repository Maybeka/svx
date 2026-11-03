from pathlib import PurePosixPath

from svx.generated_locations import member_locations


def test_member_locations_point_to_core_calls_and_dispatch_cases():
    method = 'sv://drivers/Driver#read'
    python = {PurePosixPath('svx_mirror/drivers.py'):
              f'def read(self):\n    return invoke_sv(self.id, {method!r}, {{}})\n',
              PurePosixPath('svx_support/drivers.py'): f'contract = {method!r}\n'}
    sv = {PurePosixPath('mirrors.sv'): f'case (method_id)\n  "{method}": begin\nend\nendcase\n'}
    assert member_locations([method], python, sv, python_prefix='python') == {
        method: [{'language': 'python', 'path': 'python/svx_mirror/drivers.py', 'line': 2},
                 {'language': 'systemverilog', 'path': 'mirrors.sv', 'line': 2}]}


def test_native_core_location_does_not_require_protocol_cases_in_core_file():
    method = 'sv-vif://bus/master#read_data'
    sources = {PurePosixPath('mirrors.sv'):
               f'// Core operation: {method}\nfunction int _svx__core_read_data(); return 1; endfunction\n'}
    assert member_locations([method], {}, sources)[method] == [
        {'language': 'systemverilog', 'path': 'mirrors.sv', 'line': 1}]
