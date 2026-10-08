"""Manifest input for the public CLI static bridge regression."""

from copy import deepcopy
from .python_root_proxy_schema import manifest_data as root_manifest


def manifest_data():
    data = deepcopy(root_manifest())
    source = data['classes'][0]
    source['symbol'] = 'tests.integration.python_static_source.Source'
    source['fields'] = []
    source.pop('constructor')
    source['methods'] = [method for method in source['methods'] if method.get('static')]
    invalid = deepcopy(source['methods'][1])
    invalid.update(canonical_id=source['canonical_id'] + '#illegal_wait',
                   name='illegal_wait', timing='function')
    source['methods'].append(invalid)
    return data
