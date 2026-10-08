"""Heterogeneous construction transport qualification, not factory routing."""

from pathlib import Path
import sys

from svtypes import CodecSession, String
from svx import runtime
from svx._construction import _ConstructionRequest
from svx.declarations import _svtypes_binding
from svx.inheritance import parse_manifest
from tests.integration.python_unit_schema import manifest_data


def request():
    data = manifest_data()
    target = data['classes'][0]
    derived = target['base_lineage'][-1]
    derived['constructor']['parameters'].append({
        'name': 'label', 'type': _svtypes_binding(String, where='constructor label')})
    target['constructor']['parameters'] = []
    return _ConstructionRequest(parse_manifest(data).classes[0])


def values(plan):
    root, child, derived, final = (portion.class_id for portion in plan.portions)
    return {root: {'seed': 17}, child: {'child_seed': 23},
            derived: {'child_seed': 29, 'label': 'separate portion'}, final: {}}


def emit(root):
    plan = request()
    records = plan.sv_record_types()
    root.mkdir(parents=True, exist_ok=True)
    (root / 'records.svh').write_text('\n'.join(record.to_sv_obj() for record in records))
    payload = plan.encode(values(plan))
    (root / 'input.hex').write_text(''.join(f'{value:02x}\n' for value in payload))
    (root / 'tb.sv').write_text(f'''module tb;
  import svtypes_pkg::*;
  `include "{root}/records.svh"
  initial begin
    {records[-1].__name__} request;
    {records[2].__name__} derived;
    byte unsigned bytes[$], stage[$], response[$];
    int fd, count, offset;
    byte unsigned octet;
    fd = $fopen("{root}/input.hex", "r");
    if (!fd) $fatal(2, "missing construction input");
    while ($fscanf(fd, "%h", octet) == 1) bytes.push_back(octet);
    $fclose(fd);
    request = new(); offset = 0; request.unpack(bytes, offset);
    if (offset != bytes.size() || request.target_id != "{plan.target_id}")
      $fatal(2, "construction envelope mismatch");
    if (request.owner_0 != "{plan.portions[0].class_id}" ||
        request.owner_1 != "{plan.portions[1].class_id}" ||
        request.owner_2 != "{plan.portions[2].class_id}" ||
        request.owner_3 != "{plan.portions[3].class_id}" || request.arguments_3.size() != 0)
      $fatal(2, "construction lineage mismatch");
    stage = request.arguments_2;
    derived = new(); offset = 0; derived.unpack(stage, offset);
    if (offset != stage.size() || derived.child_seed != 29 || derived.label != "separate portion")
      $fatal(2, "heterogeneous constructor values mismatch");
    derived.child_seed = 31; derived.label = "updated in SV";
    stage.delete(); derived.pack(stage); request.arguments_2 = stage;
    request.pack(response);
    fd = $fopen("{root}/output.hex", "w");
    foreach (response[i]) $fwrite(fd, "%02x\\n", response[i]);
    $fclose(fd);
    $display("CONSTRUCTION_REQUEST_SV_PASS");
    $finish;
  end
endmodule
''')


if __name__ == '__main__':
    runtime._state = runtime.RuntimeState.READY
    runtime._codec_session = CodecSession()
    root = Path(sys.argv[1])
    if '--verify' in sys.argv[2:]:
        plan = request()
        expected = values(plan)
        expected[plan.portions[2].class_id] = {'child_seed': 31, 'label': 'updated in SV'}
        assert plan.decode(bytes.fromhex((root / 'output.hex').read_text())) == expected
        print('CONSTRUCTION_REQUEST_PYTHON_PASS')
    else:
        emit(root)
