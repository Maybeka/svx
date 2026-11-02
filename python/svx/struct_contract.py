"""Public SvTypes struct-kind negotiation; never infer packing from encoding."""

from .errors import SVXInheritanceError


CAPABILITY = 'svtypes.struct-kinds.v1'


def validate_struct_metadata(value, *, where):
    """Check nested identities and schemas, including container arguments."""
    from collections.abc import Mapping

    found = False
    if isinstance(value, Mapping):
        if value.get('kind') == 'struct':
            struct_base(value.get('packed'), where=where)
            found = True
        for name, child in value.items():
            found = validate_struct_metadata(child, where=f'{where}.{name}') or found
    elif isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            found = validate_struct_metadata(child, where=f'{where}[{index}]') or found
    return found


def struct_base(packed, *, where):
    import svtypes

    if type(packed) is not bool:
        raise SVXInheritanceError(f'{where}: struct packed must be an explicit boolean')
    if CAPABILITY not in svtypes.runtime_capabilities().provided:
        raise SVXInheritanceError(f'{where}: SvTypes requires capability {CAPABILITY}')
    return svtypes.SvPackedStruct if packed else svtypes.SvStruct


def bind_native_struct_declaration(text, model_name, reference, *, packed, schema=None):
    """Retain public generated packers while using the actual source typedef."""
    marker = '} ' + model_name + '_t;'
    declaration, separator, packer = text.partition(marker)
    prefix = 'typedef struct packed {' if packed else 'typedef struct {'
    if not separator or not declaration.lstrip().startswith(prefix):
        raise SVXInheritanceError('SvTypes struct codegen does not expose its expected typed packer')
    indent = declaration[:len(declaration) - len(declaration.lstrip())]
    handles = [field for field in (schema or {}).get('fields', ())
               if _contains_native_reference(field['type'])]
    if handles:
        return _native_handle_struct(text, model_name, reference, schema, indent)
    return indent + 'typedef ' + reference + ' ' + model_name + '_t;' + packer


def _native_handle_struct(text, name, reference, schema, indent):
    import re

    wire = 'SVXStructWire_' + name
    text = re.sub(r'\b' + re.escape(name) + r'_(t|packer)\b',
                  lambda match: wire + '_' + match[1], text)
    encode, decode = [], []
    for field in schema['fields']:
        member = field['name']
        source, target = 'value.' + member, 'wire_value.' + member
        if not _contains_native_reference(field['type']):
            encode.append(f'    {target} = {source};')
            decode.append(f'    {source} = {target};')
            continue
        encode.extend(_convert_native_reference(field['type'], source, target, encode=True,
                                                where=reference + '.' + member))
        decode.extend(_convert_native_reference(field['type'], target, source, encode=False,
                                                where=reference + '.' + member))
    lines = [text, f'typedef {reference} {name}_t;', f'class {name}_packer;',
             f'  static function void pack(input {name}_t value, ref byte unsigned bytes[$]);',
             f'    {wire}_t wire_value;', *encode,
             f'    {wire}_packer::pack(wire_value, bytes);', '  endfunction',
             f'  static function void unpack(ref {name}_t value, ref byte unsigned bytes[$], ref int offset);',
             f'    {wire}_t wire_value;', '    string error;',
             f'    {wire}_packer::unpack(wire_value, bytes, offset);', *decode,
             '  endfunction', 'endclass']
    return '\n'.join(indent + line if index else line for index, line in enumerate(lines))


def _contains_native_reference(schema):
    kind = schema['kind']
    if kind == 'remote_ref':
        return True
    if kind in {'array', 'dyn_array', 'queue'}:
        return _contains_native_reference(schema['element'])
    if kind == 'assoc_array':
        return _contains_native_reference(schema['value'])
    # Nested named structs have their own native packer and matching typedef.
    return False


def _convert_native_reference(schema, source, target, *, encode, where, depth=0):
    import json
    from .sv_scan import _source_class_selector

    prefix = '    ' + '  ' * depth
    kind = schema['kind']
    if kind == 'remote_ref':
        identity = schema['target_type_name']
        if not identity.startswith('sv://'):
            raise SVXInheritanceError(f'{where}: native handle target requires source metadata')
        adapter = f'svx_pkg::svx_class_reference#({_source_class_selector(identity)}, {json.dumps(identity)})'
        if encode:
            return [f'{prefix}{target} = {adapter}::encode({source});']
        return [f'{prefix}if (!{adapter}::decode({source}, {target}, error))',
                f'{prefix}  svx_pkg::svx_fatal_svx({json.dumps(where)}, error);']
    index = f'svx_index_{depth}'
    lines = []
    if kind == 'dyn_array':
        lines.append(f'{prefix}{target} = new[{source}.size()];')
    elif kind in {'queue', 'assoc_array'}:
        lines.append(f'{prefix}{target}.delete();')
    lines.append(f'{prefix}foreach ({source}[{index}]) begin')
    element = schema['value'] if kind == 'assoc_array' else schema['element']
    destination = f'{target}[{index}]'
    if kind == 'queue':
        destination = f'svx_element_{depth}'
        lines.extend([f'{prefix}  typedef type({target}[0]) svx_element_type_{depth};',
                      f'{prefix}  svx_element_type_{depth} {destination};'])
    lines.extend(_convert_native_reference(element, f'{source}[{index}]', destination,
                                           encode=encode, where=where, depth=depth + 1))
    if kind == 'queue':
        lines.append(f'{prefix}  {target}.push_back({destination});')
    lines.append(prefix + 'end')
    return lines
