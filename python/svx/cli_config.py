"""Expand user-owned configuration formats into the ordinary CLI argument list."""

import argparse
from collections.abc import Sequence
from pathlib import Path
import runpy

from .errors import SVXError


def _split_arguments(argv):
    arguments = list(argv)
    boundary = next((index for index, token in enumerate(arguments)
                     if token == '--config-parser' or token.startswith('--config-parser=')), None)
    tail = None
    if boundary is not None:
        option = arguments[boundary]
        tail = ([option.split('=', 1)[1], *arguments[boundary + 1:]]
                if '=' in option else arguments[boundary + 1:])
        arguments = arguments[:boundary]
    parser = argparse.ArgumentParser(prog='svx', add_help=False)
    parser.add_argument('--config', action='append', default=[])
    parser.add_argument('--config-parser')
    options, explicit = parser.parse_known_args(arguments)
    if boundary is not None:
        options.config_parser = tail
    elif options.config_parser is not None:
        raise SVXError('spell --config-parser in full to mark the argument boundary')
    return options, explicit


def explicit_debug_requested(argv):
    return '--debug' in _split_arguments(argv)[1]


def expand_config_arguments(argv):
    arguments = list(argv)
    options, explicit = _split_arguments(arguments)
    # Only help before the parser boundary belongs to SVX.
    if '--help' in explicit or '-h' in explicit:
        return explicit
    if not options.config and options.config_parser is None:
        return arguments
    if not options.config or options.config_parser is None:
        raise SVXError('--config and --config-parser must be supplied together')
    if not options.config_parser:
        raise SVXError('--config-parser requires a Python script path')
    script = Path(options.config_parser[0]).resolve(strict=True)
    parser_arguments = options.config_parser[1:]
    try:
        namespace = runpy.run_path(str(script), run_name='__svx_cli_config__')
        convert = namespace.get('svx_args')
        if not callable(convert):
            raise ValueError('parser must define svx_args(config_path: pathlib.Path, argv: list[str])')
        expanded = []
        for filename in options.config:
            path = Path(filename).resolve(strict=True)
            tokens = convert(path, list(parser_arguments))
            if (isinstance(tokens, (str, bytes)) or not isinstance(tokens, Sequence)
                    or not all(isinstance(token, str) for token in tokens)):
                raise ValueError(f'{path}: svx_args must return a sequence of strings, not a command string')
            if any(token.split('=', 1)[0] in {'--config', '--config-parser'} for token in tokens):
                raise ValueError('parser output must not contain --config or --config-parser')
            expanded.extend(tokens)
    except Exception as error:
        raise SVXError(f'configuration parser {script} failed: {error}') from error
    command = next((index for index, token in enumerate(explicit) if not token.startswith('-')), None)
    if command is None:
        raise SVXError('a command is required before configuration arguments')
    return [*explicit[:command + 1], *expanded, *explicit[command + 1:]]
