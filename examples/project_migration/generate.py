"""Generate or read-only check the migration project's typed SV contract."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    target = root / "examples/project_migration/generated/models.sv"
    command = [sys.executable, "-m", "svx", "svtypes-gen", "--module",
               "examples.project_migration.models", "--channel-helpers"]
    if args.check:
        generated = subprocess.run(command, cwd=root, check=True, capture_output=True).stdout
        if not target.exists() or target.read_bytes() != generated:
            raise SystemExit("Migration models are stale; run python -m examples.project_migration.generate")
        print("MIGRATION_MODELS_CURRENT")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([*command, "--out", str(target)], cwd=root, check=True)
        print("MIGRATION_MODELS_GENERATED")


if __name__ == "__main__":
    main()
