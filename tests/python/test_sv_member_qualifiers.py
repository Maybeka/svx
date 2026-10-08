from copy import deepcopy
from io import StringIO
import json

import pytest

from svx import SVXInheritanceError
from svx.sv_scan import validate_sv_declarations


def source_file(tmp_path):
    source = tmp_path / 'qualifiers.sv'
    source.write_text('''package p;
virtual class A;
  pure virtual function int required();
  virtual function int dynamic(); return 1; endfunction
  static function int shared(); return 2; endfunction
  protected function int visible(); return 3; endfunction
  local function int hidden(); return 4; endfunction
  protected int count;
  local int secret;
endclass
class B extends A;
  function int required(); return 5; endfunction
  function int dynamic(); return 6; endfunction
endclass
endpackage
''')
    return source


def declaration(name, **qualifiers):
    return {'symbol': 'p::A', 'methods': [{
        'name': name, 'timing': 'function', 'parameters': [],
        'return_type': {'sv': 'int'}, 'virtual': False, **qualifiers,
    }]}


@pytest.mark.parametrize('name, flags, expected', [
    ('dynamic', {}, 'virtual'),
    ('shared', {'static': False}, 'static'),
    ('required', {'virtual': True, 'pure_virtual': False}, 'pure_virtual'),
    ('dynamic', {'virtual': True, 'pure_virtual': True}, 'pure_virtual'),
])
def test_source_member_qualifier_drift_is_not_silently_accepted(tmp_path, name, flags, expected):
    with pytest.raises(SVXInheritanceError, match=expected):
        validate_sv_declarations([declaration(name, **flags)], [source_file(tmp_path)])


def test_source_qualifiers_follow_effective_inherited_virtual_semantics(tmp_path):
    source = source_file(tmp_path)
    valid = declaration('required', virtual=True, pure_virtual=False)
    valid['symbol'] = 'p::B'
    validate_sv_declarations([valid], [source])
    wrong = deepcopy(valid)
    wrong['methods'][0]['virtual'] = False
    with pytest.raises(SVXInheritanceError, match='virtual'):
        validate_sv_declarations([wrong], [source])


def test_source_local_members_rejected_protected_members_remain_accessible(tmp_path):
    source = source_file(tmp_path)
    validate_sv_declarations([declaration('visible')], [source])
    with pytest.raises(SVXInheritanceError, match='local'):
        validate_sv_declarations([declaration('hidden')], [source])
    valid = {'symbol': 'p::A', 'fields': [{'name': 'count', 'type': {'sv': 'int'}}]}
    validate_sv_declarations([valid], [source])
    valid['fields'][0]['name'] = 'secret'
    with pytest.raises(SVXInheritanceError, match='local'):
        validate_sv_declarations([valid], [source])


def test_source_qualifier_edit_fails_before_manifest_replacement(tmp_path):
    from svtypes import Int
    from svx.cli import main
    from svx.declarations import (
        SV_DECLARATION_SCHEMA_URI, SV_DECLARATION_SCHEMA_VERSION, inheritance_parameter,
    )
    source = tmp_path / 'source.sv'
    sidecar = tmp_path / 'declarations.json'
    output = tmp_path / 'manifest.json'
    source.write_text('package p; class A; function int check(); return 7; endfunction '
                      'endclass endpackage\n')
    data = declaration('check')
    data.update(canonical_id='sv://p/A', language='sv')
    method = data['methods'][0]
    method['canonical_id'] = 'sv://p/A#check'
    method['return_type'] = inheritance_parameter('value', Int)['type']
    sidecar.write_text(json.dumps({
        'schema_uri': SV_DECLARATION_SCHEMA_URI,
        'schema_version': SV_DECLARATION_SCHEMA_VERSION, 'classes': [data],
    }))
    arguments = ['inheritance-manifest', '--sv-declarations', str(sidecar),
                 '--sv-source', str(source), '--out', str(output)]
    assert main(arguments, out=StringIO()) == 0
    before = (output.read_bytes(), output.stat().st_mtime_ns)
    source.write_text(source.read_text().replace('function int', 'virtual function int'))
    with pytest.raises(SVXInheritanceError, match='virtual is False, but source is True'):
        main(arguments, out=StringIO())
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before
