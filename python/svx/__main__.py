from __future__ import annotations

import sys

from .cli import entrypoint


if __name__ == "__main__":
    raise SystemExit(entrypoint(sys.argv[1:]))
