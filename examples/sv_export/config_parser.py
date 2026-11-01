"""Example project-owned JSON format; this is not a built-in SVX schema."""

import json
from pathlib import Path


def svx_args(config_path: Path, argv: list[str]) -> list[str]:
    config = json.loads(config_path.read_text(encoding='utf-8'))
    directory = (config_path.parent / config['build_directory']).resolve()
    output = (config_path.parent / config['output']).resolve()
    arguments = ['--sv-build-directory', str(directory)]
    for filename in config.get('filelists', []):
        arguments.extend(['-f', filename])
    for target in config.get('classes', []):
        arguments.extend(['--class', target])
    for package in config.get('packages', []):
        arguments.extend(['--package', package])
    arguments.extend(['--out', str(output)])
    # This adapter forwards trailing options unchanged; projects can parse them.
    return arguments + argv
