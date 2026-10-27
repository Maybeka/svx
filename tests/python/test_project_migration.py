"""Project logic and tutorial acceptance; real HDL execution is a separate gate."""

from pathlib import Path
import subprocess
import sys

import pytest

from examples.project_migration.scenarios import expected_results, program, request_for
from examples.project_migration.verify import expected_trace, verify_failure, verify_run

ROOT = Path(__file__).resolve().parents[2]


def test_migration_program_preserves_legacy_sequence_and_reset_reads():
    operations = program()
    assert len(operations) == 64
    assert [(op.tag, op.write, op.address) for op in operations[:8]] == [
        (0, 0, 0), (1, 0, 12), (2, 0, 8), (3, 0, 4),
        (4, 1, 0), (5, 1, 12), (6, 1, 8), (7, 1, 4),
    ]
    values = expected_results(operations)
    assert values[:4] == (0, 0, 0, 0)
    assert values[9] == 0xA0AF554E
    assert values[63] == 0x9ED3EBB6
    assert values == tuple(row[3] for row in expected_trace(64))
    assert expected_trace(64)[-1][-1] == 1_775_000


@pytest.mark.parametrize("count,salt", [(64, 0), (192, 0xDEADBEEF), (4096, 0x12345678)])
def test_project_contract_roundtrips_all_requests(count, salt):
    from examples.project_migration.models import MigrationRequest

    codec = MigrationRequest.codec_template()
    for op in program(count, salt):
        item = request_for(op)
        payload = codec.pack(item)
        decoded, used = codec.unpack(payload)
        assert used == len(payload)
        assert (decoded.tag.value, decoded.stop.value, decoded.write.value,
                decoded.address.value, decoded.data.value) == (
                    op.tag, 0, op.write, op.address, op.data)


def positive_log():
    traces = [f"MIGRATION_TRACE tag={a} write={b} address={c} data={d:08x} time_ps={e}"
              for a, b, c, d, e in expected_trace(64)]
    return "\n".join([*traces, "MIGRATION_PY_RESPONSES_PASS count=64",
                      "MIGRATION_PY_SCOREBOARD_PASS count=64 addresses=4 operations=2",
                      "MIGRATION_PROJECT_PASS count=64 observations=64 waits=48"])


def test_log_verifier_rejects_wrong_data_timing_and_missing_completion():
    text = positive_log()
    verify_run(text, "03_python")
    for wrong in (text.replace("time_ps=35000", "time_ps=35001"),
                  text.replace("data=00000000", "data=00000001", 1),
                  text.replace("MIGRATION_PROJECT_PASS", "NOT_A_PASS"),
                  text + "\nFatal: checker failed"):
        with pytest.raises(ValueError):
            verify_run(wrong, "03_python")


def test_negative_verifier_requires_the_checker_error_not_arbitrary_failure():
    verify_failure("Fatal: checker failed\nMIGRATION_MONITOR_MISMATCH", ["MIGRATION_MONITOR_MISMATCH"])
    for text in ("Segmentation fault", "Fatal: missing module",
                 "Fatal: MIGRATION_MONITOR_MISMATCH\nMIGRATION_PROJECT_PASS"):
        with pytest.raises(ValueError):
            verify_failure(text, ["MIGRATION_MONITOR_MISMATCH"])


def test_migration_generated_contract_is_current():
    result = subprocess.run([sys.executable, "-m", "examples.project_migration.generate", "--check"],
                            cwd=ROOT, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_migration_checkpoints_keep_driver_and_monitor_shared():
    base = ROOT / "examples/project_migration"
    pure = (base / "00_sv/tb.sv").read_text()
    assert "svx_pkg" not in pure and "svtypes_pkg" not in pure
    for stage in ("00_sv", "01_entry", "02_stimulus", "03_python"):
        top = (base / stage / "tb.sv").read_text()
        assert 'common/harness.svh' in top
        assert "driver();" in top and "monitor();" in top
        assert "join\n" in top and "check_complete();" in top
    final = (base / "03_python/tb.sv").read_text()
    assert "legacy_sequence();" not in final and "legacy_scoreboard();" not in final
    assert "monitor_bridge();" in final
    assert final.index("check_complete();") < final.index("svx_shutdown();") < final.index("report_complete();")
