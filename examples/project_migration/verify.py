"""Check a saved project log, including every transaction and sampling time.

Only the Python standard library is needed; this can also verify the pure SV
checkpoint before installing SVX. It never invokes a simulator.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re

TRACE = re.compile(
    r"^MIGRATION_TRACE tag=(\d+) write=(\d+) address=(\d+) "
    r"data=([0-9a-fA-F]+) time_ps=(\d+)$", re.MULTILINE,
)
FAILURE = re.compile(
    r"^\s*(?:Fatal:|Error-)|SVX FATAL|DPI-(?:DSNA|IIDTRC)|"
    r"Fatal Python error:|Segmentation fault", re.MULTILINE,
)


def expected_trace(count: int, salt: int = 0) -> list[tuple[int, int, int, int, int]]:
    registers = [0, 0, 0, 0]
    result = []
    sample_ps = 15_000
    for tag in range(count):
        index = (tag * 3) % 4
        write = int(tag >= 4 and (tag < 8 or tag % 3 != 0))
        if write:
            registers[index] = ((tag * 0x01020304) ^ 0xA5A55A5A ^ salt) & 0xFFFFFFFF
        sample_ps += 20_000 + (index % 3) * 10_000
        result.append((tag, write, index * 4, registers[index], sample_ps))
    return result


def parse_trace(text: str) -> list[tuple[int, int, int, int, int]]:
    return [(int(tag), int(write), int(address), int(data, 16), int(time))
            for tag, write, address, data, time in TRACE.findall(text)]


def verify_run(text: str, stage: str, count: int = 64, salt: int = 0,
               baseline: str | None = None) -> None:
    if FAILURE.search(text):
        raise ValueError("a positive run contains a failure diagnostic")
    actual = parse_trace(text)
    expected = expected_trace(count, salt)
    if actual != expected:
        first = next((i for i, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]),
                     min(len(actual), len(expected)))
        raise ValueError(f"transaction/time trace mismatch at index {first}; got {len(actual)}, expected {count}")
    waits = sum(((i * 3) % 4) % 3 for i in range(count))
    required = [f"MIGRATION_PROJECT_PASS count={count} observations={count} waits={waits}"]
    if stage in {"00_sv", "01_entry", "02_stimulus"}:
        required.append("MIGRATION_SV_SCOREBOARD_PASS count=64")
    if stage in {"00_sv", "01_entry"}:
        required.append("MIGRATION_SV_RESPONSES_PASS count=64")
    if stage == "01_entry":
        required.append("MIGRATION_PY_ENTRY_PASS")
    if stage in {"02_stimulus", "03_python"}:
        required.append(f"MIGRATION_PY_RESPONSES_PASS count={count}")
    if stage == "03_python":
        required.append(f"MIGRATION_PY_SCOREBOARD_PASS count={count} addresses=4 operations=2")
    missing = set(required) - set(text.splitlines())
    if missing:
        raise ValueError(f"missing completion records: {sorted(missing)!r}")
    if baseline is not None and actual != parse_trace(baseline):
        raise ValueError("the migrated trace differs from the pure SV baseline")


def verify_failure(text: str, diagnostics: list[str]) -> None:
    if "MIGRATION_PROJECT_PASS" in text:
        raise ValueError("a negative run unexpectedly completed")
    if not re.search(r"^\s*Fatal:", text, re.MULTILINE):
        raise ValueError("a negative run has no fatal diagnostic")
    if not any(diagnostic in text for diagnostic in diagnostics):
        raise ValueError("the negative run did not report the expected checker error")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--stage", choices=("00_sv", "01_entry", "02_stimulus", "03_python"), required=True)
    parser.add_argument("--count", type=int, default=64)
    parser.add_argument("--salt", type=lambda text: int(text, 0), default=0)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--expect-error", action="append")
    args = parser.parse_args()
    try:
        text = args.log.read_text()
        if args.expect_error:
            verify_failure(text, args.expect_error)
        else:
            verify_run(text, args.stage, args.count, args.salt,
                       args.baseline.read_text() if args.baseline else None)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{args.log}: {error}\n")
    print("MIGRATION_LOG_VERIFIED")


if __name__ == "__main__":
    main()
