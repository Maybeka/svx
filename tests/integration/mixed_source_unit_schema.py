"""Qualify mixed-root source layout, not the complete public runtime frontend."""

import json
import argparse
from pathlib import Path

from svx.declarations import manifest_dict
from dataclasses import replace
from svx.inheritance import (_emit_source_python_artifacts, _manifest_sv_record_types,
                             artifact_manifest, parse_manifest)
from svx.source_layout import _emit_source_units
from tests.integration.same_package_schema import manifest_data as sv_manifest
from tests.integration.python_unit_schema import manifest_data as python_manifest


def manifest_and_source(*, endpoint_handles=False, multiple_endpoint_packages=False, forward_endpoint_type=False,
                        independent_targets=False):
    data = sv_manifest()
    data['classes'] += python_manifest()['classes']
    if endpoint_handles:
        import svtypes
        from tests.integration.constructor_handles_schema import binding, manifest_data as handles
        packet_target = 'sv://mixed_source_pkg/Packet'
        packet = {'name': 'native_packet', 'type': binding(svtypes.RemoteRef[packet_target]),
                  'handle': {'kind': 'sv_class', 'target_type_name': packet_target,
                             'sv_type': ('endpoint_types_pkg' if multiple_endpoint_packages else 'mixed_source_pkg') + '::Packet'}}
        vif = handles()['classes'][0]['fields'][1]
        for child in (data['classes'][0], data['classes'][1]['base_lineage'][1]):
            child.setdefault('fields', []).extend([packet, vif])
            for field, name in [(packet, 'echo_packet'), (vif, 'echo_vif')]:
                child['methods'].append({
                    'canonical_id': child['canonical_id'] + '#' + name, 'name': name,
                    'parameters': [{'name': 'value', 'type': field['type'], 'handle': field['handle']}],
                    'return_type': field['type'], 'return_handle': field['handle'],
                    'timing': 'function', 'virtual': False})

    def relocate(declaration):
        if declaration['language'] == 'sv':
            declaration['symbol'] = 'mixed_source_pkg::' + declaration['symbol'].split('::')[-1]
        for ancestor in declaration.get('base_lineage', []):
            relocate(ancestor)

    for declaration in data['classes']:
        relocate(declaration)
    if independent_targets:
        scalar = data['classes'][0]['methods'][0]['return_type']
        data['classes'].extend([
            {'canonical_id': 'py://mixed/Independent', 'language': 'python',
             'symbol': 'tests.integration.python_unit_source.Independent',
             'constructor': {'initiator': 'python', 'parameters': []},
             'methods': [{'canonical_id': 'py://mixed/Independent#ping', 'name': 'ping',
                          'parameters': [{'name': 'value', 'type': scalar}], 'return_type': scalar,
                          'timing': 'function', 'virtual': True}]},
            {'canonical_id': 'sv://mixed_source_pkg/Pure', 'language': 'sv',
             'symbol': 'mixed_source_pkg::Pure',
             'constructor': {'initiator': 'python', 'parameters': []},
             'fields': [{'name': 'value', 'type': scalar}],
             'methods': [{'canonical_id': 'sv://mixed_source_pkg/Pure#answer', 'name': 'answer',
                          'parameters': [], 'return_type': scalar, 'timing': 'function', 'virtual': False}]},
        ])
    directory = Path(__file__).parent
    sv = (directory / 'same_package_source.sv').read_text()
    python = (directory / 'python_unit_source.sv').read_text()
    body = sv.removeprefix('package same_package_pkg;').removesuffix('endpackage\n')
    body = '''
  class Holder;
    svx_proxy_same_package_test::B peer;
    function svx_proxy_same_package_test::B identity(svx_proxy_same_package_test::B value);
      return value;
    endfunction
  endclass
''' + body
    body += python.removeprefix('package python_unit_pkg;').removesuffix('endpackage\n')
    body = body.replace('    int extra = 100;', '''    svx_proxy_same_package_test::B peer;
    function svx_proxy_same_package_test::B identity(svx_proxy_same_package_test::B value);
      return value;
    endfunction
    int extra = 100;''')
    body = body.replace('  class Child extends svx_proxy_python_unit_source::Root;', '''  class Child extends svx_proxy_python_unit_source::Root;
    function int proxy_scale(int value);
      return svx_proxy_python_unit_source::Root::scale(value);
    endfunction''')
    if endpoint_handles:
        if forward_endpoint_type:
            body = '  typedef class Packet;\n' + body + '  class Packet; int value; endclass\n'
        else:
            body = '  class Packet; int value; endclass\n' + body
        endpoints = '''    Packet native_packet;
    virtual external_bus_if.master native_vif;
    function Packet echo_packet(Packet value); return value; endfunction
    function virtual external_bus_if.master echo_vif(virtual external_bus_if.master value);
      return value;
    endfunction
'''
        body = body.replace('    int extra = 100;', endpoints + '    int extra = 100;')
        body = body.replace('    int child_value = 100;', endpoints + '    int child_value = 100;')
    source = 'package mixed_source_pkg;' + body + 'endpackage\n'
    if independent_targets:
        source = source.replace('endpackage\n', '''  class IndependentImpl extends svx_proxy_python_unit_source::Independent;
    function new(longint unsigned object_id); super.new(object_id); endfunction
    virtual function int ping(input int value); return super.ping(value) + 100; endfunction
  endclass
  class Pure;
    int value = 9;
    static int allocations = 0;
    function new(); allocations++; endfunction
    function int answer(); return value + 5; endfunction
  endclass
endpackage
''')
        source += '''package later_source_pkg;
  class IndependentLaterImpl extends svx_proxy_python_unit_source::Independent;
    function new(longint unsigned object_id); super.new(object_id); endfunction
    virtual function int ping(input int value); return super.ping(value) + 100; endfunction
  endclass
endpackage
'''
    return parse_manifest(data), source


def endpoint_source_inputs(source):
    source = source.replace('  class Packet; int value; endclass\n', '')
    source = source.replace('Packet native_packet;', 'endpoint_types_pkg::Packet native_packet;')
    source = source.replace('function Packet echo_packet(Packet value);',
                            'function endpoint_types_pkg::Packet echo_packet(endpoint_types_pkg::Packet value);')
    consumer = '''module early_endpoint_consumer;
  import svtypes_pkg::*;
  remote_ref reference;
  initial begin
    reference = svx_external_handles_pkg::SVXExternal_sv___mixed_source_pkg_Packet::encode(null);
    if (reference.object_number != 0) $fatal(1, "early null endpoint changed identity");
    $display("EARLY_ENDPOINT_CONSUMER_PASS");
  end
endmodule
'''
    return {'endpoint-types.sv': 'package endpoint_types_pkg; class Packet; int value; endclass endpackage\n',
            'early-endpoint-consumer.sv': consumer, 'mixed-source.sv': source}


def emit_sources(manifest=None, *, endpoint_handles=False, multiple_endpoint_packages=False, forward_endpoint_type=False,
                 independent_targets=False):
    original, source = manifest_and_source(endpoint_handles=endpoint_handles,
                                         multiple_endpoint_packages=multiple_endpoint_packages,
                                         forward_endpoint_type=forward_endpoint_type,
                                         independent_targets=independent_targets)
    if manifest is not None:
        source = source.replace('svx_proxy_same_package_test::', 'svx_proxy_mixed_sv_source::')
        source = source.replace('svx_proxy_python_unit_source::', 'svx_proxy_mixed_python_source::')
    manifest = manifest or original
    records = ['package svx_call_records_pkg;', '  import svtypes_pkg::*;']
    records.extend(record.to_sv_obj(1) for record in _manifest_sv_record_types(manifest))
    records.append('endpackage')
    inputs = endpoint_source_inputs(source) if multiple_endpoint_packages else {'mixed-source.sv': source}
    return {'common.svh': '\n'.join(records) + '\n', 'source.sv': _emit_source_units(manifest, inputs)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--public-cli', action='store_true')
    parser.add_argument('--proxy-type-macro', action='store_true')
    shape = parser.add_mutually_exclusive_group()
    shape.add_argument('--multiple-endpoint-packages', action='store_true')
    shape.add_argument('--forward-endpoint-type', action='store_true')
    args = parser.parse_args()
    if args.proxy_type_macro and not args.public_cli:
        parser.error('--proxy-type-macro requires --public-cli')
    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    manifest, _ = manifest_and_source(endpoint_handles=True,
                                     multiple_endpoint_packages=args.multiple_endpoint_packages,
                                     forward_endpoint_type=args.forward_endpoint_type,
                                     independent_targets=True)

    def runtime_source(source):
        ancestors = tuple(runtime_source(item) for item in source.base_lineage)
        symbol = source.symbol
        if source.language == 'python':
            symbol = ('mixed_sv_source' if source.name == 'B' else 'mixed_python_source') + '.' + source.name
        return replace(source, symbol=symbol, base_lineage=ancestors)

    manifest = replace(manifest, classes=tuple(runtime_source(source) for source in manifest.classes))
    sv = {Path(name): text for name, text in emit_sources(
        manifest, endpoint_handles=True, multiple_endpoint_packages=args.multiple_endpoint_packages,
        forward_endpoint_type=args.forward_endpoint_type, independent_targets=True).items()}
    python = _emit_source_python_artifacts(manifest)
    for name, text in sv.items():
        (root / name).write_text(text)
    for name, text in python.items():
        output = root / 'python' / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    # Reuse qualified source bodies; only fixture import locations change.
    directory = Path(__file__).parent
    for name, original in [('mixed_sv_source', 'same_package_test'),
                           ('mixed_python_source', 'python_unit_source'),
                           ('mixed_runtime_test', 'python_unit_test')]:
        text = (directory / (original + '.py')).read_text()
        for before, after in [('svx_mirror.same_package_pkg', 'svx_mirror.mixed_source_pkg'),
                              ('svx_mirror.python_unit_pkg', 'svx_mirror.mixed_source_pkg'),
                              ('tests.integration.python_unit_source', 'mixed_python_source')]:
            text = text.replace(before, after)
        if name == 'mixed_sv_source':
            text = text.replace('close(python_c, (python_c.count, python_c.retry, python_c.extra))',
                                'close(python_c, (python_c.count, python_c.retry, python_c.extra, '
                                'python_c.native_packet, python_c.native_vif))')
            text += '''

@svx.export(name='mixed_endpoint.verify')
def verify_endpoints():
    packet = python_c.native_packet.value
    assert packet.target_type_name == 'sv://mixed_source_pkg/Packet'
    assert python_c.echo_packet(packet) == packet
    vif = python_c.echo_vif(python_c.native_vif.value)
    assert vif.read().value_mask == 0x31
    vif.write_data(0x5c)
    assert vif.read().value_mask == 0x5c
    svx.display('MIXED_ENDPOINT_PYTHON_PASS')
'''
        if name == 'mixed_runtime_test':
            text = text.replace('fields = (value.count, value.child_value)',
                                'fields = (value.count, value.child_value, value.native_packet, value.native_vif)')
            text = text.replace('    close(values[0], True)', '''    verify_endpoints(values[0], 0x5c, 0x61)
    svx.display('MIXED_PYTHON_ROOT_SV_ENDPOINT_PASS')
    close(values[0], True)''')
            text += '''

def verify_endpoints(value, before, after):
    packet = value.native_packet.value
    assert packet.target_type_name == 'sv://mixed_source_pkg/Packet'
    assert value.echo_packet(packet) == packet
    vif = value.echo_vif(value.native_vif.value)
    assert vif.read().value_mask == before
    vif.write_data(after)
    assert vif.read().value_mask == after


@svx.export(name='mixed_python_endpoint.verify')
def verify_python_endpoints():
    for index, (value, seed, final) in enumerate(python_values):
        verify_endpoints(value, 0x61 + index, 0x62 + index)
    svx.display('MIXED_PYTHON_ROOT_ENDPOINT_PASS')
'''
            text += '''

@svx.export(name='mixed_independent.verify')
def verify_independent_targets():
    from svx_py.mixed_python_source import Independent
    from svx_mirror.mixed_source_pkg import Pure
    value = Independent()
    assert value.ready and value.ping(5) == 109
    svx.close_instance(value)
    assert value.ready
    pure = Pure()
    field = pure.value
    assert field.value == 9 and pure.answer() == 14
    field.value = 12
    assert pure.answer() == 17
    svx.close_instance(pure)
    try:
        _ = field.value
    except ExternalStorageError:
        pass
    else:
        raise AssertionError('standalone SV mirror field stayed valid after close')
    svx.display('MIXED_INDEPENDENT_TARGETS_PASS')
'''
        if name == 'mixed_python_source':
            text += '''

class Independent:
    def __init__(self):
        self.ready = True

    def ping(self, value):
        return value + 4
'''
        (root / 'python' / (name + '.py')).write_text(text)
    (root / 'manifest.json').write_text(json.dumps(manifest_dict(manifest), indent=2) + '\n')
    metadata = artifact_manifest(manifest, python, python_path_prefix='python', sv_sources=sv)
    (root / 'artifacts.json').write_text(json.dumps(metadata, indent=2) + '\n')
    if args.public_cli:
        from svx.cli import main
        _, original = manifest_and_source(
            endpoint_handles=True, multiple_endpoint_packages=args.multiple_endpoint_packages,
            forward_endpoint_type=args.forward_endpoint_type, independent_targets=True)
        original = original.replace('svx_proxy_same_package_test::', 'svx_proxy_mixed_sv_source::')
        original = original.replace('svx_proxy_python_unit_source::', 'svx_proxy_mixed_python_source::')
        inputs = endpoint_source_inputs(original) if args.multiple_endpoint_packages else {'mixed-source.sv': original}
        if args.proxy_type_macro:
            inputs = {filename: content.replace('svx_proxy_mixed_python_source::Independent', '`INDEPENDENT_PROXY')
                      for filename, content in inputs.items()}
            inputs = {'proxy-options.sv': '`define INDEPENDENT_PROXY svx_proxy_mixed_python_source::Independent\n',
                      **inputs}
        inputs = {'external-bus.sv': (directory / 'external_bus_if.sv').read_text(), **inputs}
        input_root = root / 'inputs'
        input_root.mkdir(exist_ok=True)
        command = ['inheritance-gen', '--manifest', str(root / 'manifest.json'),
                   '--sv-integrated-dir', str(root / 'integrated'),
                   '--python-out', str(root / 'python'), '--sv-compilation-unit',
                   '--artifact-manifest', str(root / 'artifacts.json')]
        for filename, content in inputs.items():
            path = input_root / filename
            path.write_text(content)
            command.extend(['--sv-source', str(path)])
        for name in ('mixed_sv_source', 'mixed_python_source', 'mixed_runtime_test'):
            command.extend(['--python-source', str(root / 'python' / (name + '.py'))])
        main(command)
        main(command + ['--check'])
