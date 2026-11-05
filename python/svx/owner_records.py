"""Shared declarations for transport records emitted outside SV packages."""

from contextvars import ContextVar
from functools import wraps
from dataclasses import replace
import json

from .value_exports import native_value_name


_local_call_records = ContextVar('svx_local_call_records', default=False)


def record_api_name(fields, name):
    return '_svx__' + name if name in fields else name


def render_call_record(record, indent=0):
    """Add payload-level convenience methods without changing SvTypes encoding."""
    from .sv_codegen_mode import render_sv_object
    text = render_sv_object(record, indent)
    name = record.__name__
    import svtypes
    fields = {field['name'] for field in svtypes.schema_descriptor(record).to_dict()['schema']['fields']}
    decode = record_api_name(fields, 'decode')
    encode = record_api_name(fields, 'encode')
    initialize = record_api_name(fields, 'from_request')
    methods = f'''
    static function {name} {decode}(input chandle payload);
      byte unsigned bytes[$];
      int offset;
      {name} value;
      value = new();
      offset = 0;
      svx_pkg::svx_payload_to_byte_queue(payload, bytes);
      value.unpack(bytes, offset);
      svx_pkg::svx_require_unpacked_all("{name}", "request", "record", offset, bytes.size());
      return value;
    endfunction

    function chandle {encode}();
      byte unsigned bytes[$];
      this.pack(bytes);
      return svx_pkg::svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");
    endfunction
'''
    position = text.rfind('endclass')
    constructor_fields = getattr(record, '__svx_constructor_fields__', ())
    if constructor_fields:
        from .inheritance import _codec_from_spec
        used = {field for field, _ in constructor_fields}
        local = '_svx__record'
        while local in used:
            local += '_'
        declarations = ', '.join('input ' + svtypes.sv_declaration(
            _codec_from_spec(binding.runtime_spec()), field).rstrip(';')
            for field, binding in constructor_fields)
        assignments = '\n'.join(f'      {local}.{field} = {field};' for field, _ in constructor_fields)
        method = record_api_name(fields, 'encode_arguments')
        methods += f'''
    static function chandle {method}({declarations});
      {name} {local};
      {local} = new();
{assignments}
      return {local}.{encode}();
    endfunction
'''
    request_type = getattr(record, '__svx_request_type__', None)
    if request_type:
        assignments = '\n'.join(f'      value.{field} = request.{field};'
                                for field in record.__svx_inout_fields__)
        methods += f'''
    static function {name} {initialize}(input {request_type} request);
      {name} value;
      value = new();
{assignments}
      return value;
    endfunction
'''
    if position < 0:
        raise ValueError(f'call record {name} has no generated SV class')
    return '\n'.join(line.rstrip() for line in
                     (text[:position] + methods + text[position:]).split('\n'))


def emit_owner_initializer(key, *, owner_root=None, owner_path=None):
    """Register one lexical callback without invoking user constructors early."""
    conditions = ['1']
    if owner_root is not None:
        parts = owner_path.split('.')
        start = len(owner_root.split('.'))
        scopes = ['.'.join(parts[:length]) for length in range(start, len(parts)+1)]
        scopes.append(key)
        conditions = ['scope == ' + json.dumps(scope) for scope in scopes]
    return [
        'class SVXOwnerInitializer implements svx_owner_initializer;',
        '  function new(string scope);',
        '    if (' + ' || '.join(conditions) + ')',
        '      svx_inheritance_registry::register_owner_initializer(' + json.dumps(key) + ', this);',
        '  endfunction',
        '  virtual function void _svx__initialize_owner();',
        '    initialize();',
        '  endfunction',
        'endclass',
        'SVXOwnerInitializer svx_owner_bootstrap = new($sformatf("%m"));',
    ]


def with_local_call_records(function):
    """Keep collection aliases in the native scope that owns their records."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        token = _local_call_records.set(True)
        try:
            return function(*args, **kwargs)
        finally:
            _local_call_records.reset(token)
    return wrapped


def bind_owner_types(source, native_references):
    """Change native spellings only; public SvTypes wire contracts stay intact."""
    def binding(value):
        return replace(value, sv=native_references.get(value.sv, value.sv)) if value is not None else None
    def parameters(values):
        return tuple(replace(value, type_binding=binding(value.type_binding), handle=handle(value.handle)) for value in values)
    def handle(value):
        return (replace(value, sv_type=native_references.get(value.sv_type, value.sv_type),
                        collection_binding=binding(value.collection_binding)) if value is not None else None)
    return replace(source,
        fields=tuple(replace(value, type_binding=binding(value.type_binding), handle=handle(value.handle)) for value in source.fields),
        constructor=replace(source.constructor, parameters=parameters(source.constructor.parameters)) if source.constructor else None,
        methods=tuple(replace(value, parameters=parameters(value.parameters), return_type=binding(value.return_type),
                              return_handle=handle(value.return_handle))
                      for value in source.methods),
        base_lineage=tuple(bind_owner_types(value, native_references) for value in source.base_lineage))


def owner_value_dependencies(manifest):
    """Return only value declarations used by this target's transport surface."""
    import svtypes
    from .inheritance import _codec_from_spec, _transport_owners
    bindings = []
    for owner in _transport_owners(manifest):
        bindings.extend(field.type_binding for field in owner.fields)
        bindings.extend(parameter.type_binding for parameter in (owner.constructor.parameters if owner.constructor else ()))
        for method in owner.methods:
            bindings.extend(parameter.type_binding for parameter in method.parameters)
            if method.return_type is not None:
                bindings.append(method.return_type)
    needed = set()

    def named_dependencies(schema):
        if isinstance(schema, dict):
            if isinstance(schema.get('type_name'), str):
                needed.add(schema['type_name'])
            for item in schema.values():
                named_dependencies(item)
        elif isinstance(schema, list):
            for item in schema:
                named_dependencies(item)

    for binding in bindings:
        named_dependencies(svtypes.schema_descriptor(_codec_from_spec(binding.runtime_spec())).to_dict())
    return tuple(value for value in manifest.value_types if value.as_dict()['schema']['type_name'] in needed)


def emit_owner_records(manifest, source_scope, *, native_references=None, inline=False,
                       local_enum_packers=None, native_struct_aliases=False,
                       visible_scopes=()):
    """Render actual nominal dependencies in the caller's codegen value scope."""
    import svtypes
    from .native_handles import uses_shared_handle_records
    if not inline and uses_shared_handle_records(manifest):
        return ['import svx_scoped_handles_pkg::*;']
    from .inheritance import _manifest_sv_collection_typedefs, _manifest_sv_record_types
    definitions = []
    for value in owner_value_dependencies(manifest):
        if value.source_scope is not None and value.source_scope not in (source_scope, *visible_scopes):
            continue
        data = value.as_dict()
        if data['schema']['type_name'] == value.module + '.' + value.qualname:
            definitions.append((value, data))
    lines = [f'import {package}::*;' for package in sorted({value.symbol.split('::')[0]
             for value, _ in definitions if value.source_scope is None
             and value.symbol not in (native_references or {})})]
    for value, data in definitions:
        if data['schema']['kind'] == 'enum':
            reference = (native_references or {}).get(value.symbol, value.native_reference)
            name = native_value_name(value.symbol, value.source_scope)
            lines.append(f'typedef {reference} {name};')
            if local_enum_packers is not None:
                codec = svtypes.materialize_type_spec(svtypes.type_spec_from_identity(data['svtypes']), location=value.symbol)
                wire = svtypes.Bit[data['schema']['width']]()
                packer = 'SVXLocalEnumPacker_' + name
                local_enum_packers[svtypes.sv_packer_expression(codec)] = packer
                wire_type, wire_packer = svtypes.sv_type_expression(wire), svtypes.sv_packer_expression(wire)
                lines.extend([
                    f'class {packer};',
                    f'  static function void pack(input {name} value, ref byte unsigned bytes[$]);',
                    f'    {wire_type} bits;',
                    '    bits = value;',
                    f'    {wire_packer}::pack(bits, bytes);',
                    '  endfunction',
                    f'  static function void unpack(ref {name} value, ref byte unsigned bytes[$], ref int offset);',
                    f'    {wire_type} bits;',
                    f'    {wire_packer}::unpack(bits, bytes, offset);',
                    f"    value = {name}'(bits);",
                    '  endfunction',
                    'endclass',
                ])
        elif data['schema']['kind'] == 'struct':
            model = svtypes.type_spec_from_identity(data['svtypes'], location=value.symbol)
            from .sv_codegen_mode import render_sv_object
            text = render_sv_object(model, 0)
            if native_struct_aliases and value.symbol in (native_references or {}):
                # Keep SvTypes' field packer, but bind its value to the original
                # native struct so output/inout and containers retain exact types.
                from .struct_contract import bind_native_struct_declaration
                text = bind_native_struct_declaration(text, model.__name__, native_references[value.symbol],
                                                      packed=data['schema']['packed'], schema=data['schema'])
            lines.append(text)
    lines.extend(_manifest_sv_collection_typedefs(manifest))
    from .sv_codegen_mode import render_sv_object
    lines.extend(render_call_record(record, 0) for record in _manifest_sv_record_types(manifest))
    return lines
