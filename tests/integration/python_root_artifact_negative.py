"""Produce a startup-hash negative without changing valid generated artifacts."""

import json
from pathlib import Path
import sys


def main():
    source, destination = map(Path, sys.argv[1:])
    metadata = json.loads(source.read_text())
    artifact = next(entry for entry in metadata["artifacts"] if entry["language"] == "python")
    artifact["sha256"] = "0" * 64
    destination.write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
