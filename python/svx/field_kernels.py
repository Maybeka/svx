"""Native field-reference binding and same-scope generated operation kernels."""
import json


def field_kernel(field, cases, core_name):
    from pyslang import SourceManager
    from .sv_scan import _pyslang, _check_source_diagnostics
    from .errors import SVXInheritanceError

    prefix = 'class SVXFieldScan; function void invoke(); case(method_id)\n'
    suffix = '\nendcase endfunction endclass\n'
    source = prefix+'\n'.join(cases)+suffix
    tree = _pyslang().SyntaxTree.fromText(source, SourceManager())
    _check_source_diagnostics(tree, 'generated field operation kernel')
    spans = []
    def visit(node):
        if type(node).__name__ != 'ScopedNameSyntax' or str(node.left).strip() != 'this':
            return
        member = node.right.getFirstToken()
        if member.valueText == field.name:
            spans.append((node.left.sourceRange.start.offset, member.range.end.offset))
        else:
            raise SVXInheritanceError(f'field kernel for {field.name} unexpectedly accesses owner member {member.valueText}')
    tree.root.visit(visit)
    data = source.encode('utf-8')
    resident = '__svx_resident_value'
    for start, end in sorted(set(spans), reverse=True):
        data = data[:start]+resident.encode()+data[end:]
    rewritten = data.decode('utf-8')[len(prefix):-len(suffix)].splitlines()
    kernel = '__svx_field_kernel_'+core_name.removeprefix('svx_core_field_')
    parameters = 'input string method_id, ref byte unsigned bytes[$], output bit ok, output chandle response, output string error'
    core = [f'    // Core field binding: {field.name}',
            f'    function void {core_name}({parameters});',
            f'      {kernel}#(type(this.{field.name}))::invoke(this.{field.name}, method_id, bytes, ok, response, error);',
            '    endfunction', '']
    support = [f'    class {kernel} #(type SVXResidentType = int);',
               f'      static function void invoke(ref SVXResidentType {resident}, {parameters});',
               '        response = null;', '        case (method_id)', *rewritten,
               '          default: begin ok = 0; error = "unsupported field operation"; end',
               '        endcase', '      endfunction', '    endclass', '']
    labels = [json.JSONDecoder().raw_decode(line.strip())[0] for line in cases
              if line.startswith('        "') and line.endswith(': begin')]
    dispatch = ['        '+', '.join(json.dumps(label) for label in labels)+': begin',
                f'          this.{core_name}(method_id, bytes, ok, response, error);', '        end']
    return [*support, *core], dispatch
