from svtypes import Int
from svx.inheritance import parse_manifest
from tests.integration.same_package_schema import manifest_data as baseline


def retry_codec():
    return Int(17)


def manifest_data():
    data = baseline()
    b = data['classes'][0]['base_lineage'][1]
    b['symbol'] = 'tests.integration.field_default_stage_test.B'
    binding = b['fields'][0]['type']
    binding.pop('svtypes')
    binding['python'] = {'module': 'tests.integration.field_default_stage_schema',
                         'symbol': 'retry_codec', 'args': [], 'kwargs': {}}
    return data


def manifest():
    return parse_manifest(manifest_data())
