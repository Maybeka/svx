import io
import json
from pathlib import Path

import pytest

from svx.cli import entrypoint, main
from svx.cli_config import expand_config_arguments
from svx.errors import SVXError


@pytest.fixture
def project(tmp_path):
    config = tmp_path / 'project settings.json'
    config.write_text(json.dumps(['--out', 'path with spaces', '--sv-define', 'TEXT="a b"']))
    parser = tmp_path / 'adapter.py'
    parser.write_text('import json\ndef svx_args(path, argv):\n    return json.loads(path.read_text(encoding="utf-8")) + argv\n')
    return config, parser


def options(project):
    config, parser = project
    return ['--config', str(config), '--config-parser', str(parser)]


def test_expansion_is_argv_not_shell_text_and_explicit_options_follow(project):
    result = expand_config_arguments(['--debug', 'export', '--out', 'override', *options(project)])
    assert result == ['--debug', 'export', '--out', 'path with spaces',
                      '--sv-define', 'TEXT="a b"', '--out', 'override']


def test_multiple_configs_keep_order_and_load_parser_once(project, tmp_path):
    config, parser = project
    second = tmp_path / 'second.json'
    second.write_text('["--package", "second_pkg"]')
    marker = tmp_path / 'loads'
    parser.write_text(f'from pathlib import Path\nmarker = Path({str(marker)!r})\n'
                      'marker.write_text((marker.read_text() if marker.exists() else "") + "loaded\\n")\n' +
                      parser.read_text())
    result = expand_config_arguments(['export', '--config=' + str(second), *options(project)])
    assert result[1:3] == ['--package', 'second_pkg']
    assert marker.read_text() == 'loaded\n'
    assert result.count('--out') == 1


@pytest.mark.parametrize('arguments', [['--config', 'file'], ['--config-parser', 'adapter.py']])
def test_configuration_requires_both_inputs(arguments):
    with pytest.raises(SVXError, match='supplied together'):
        expand_config_arguments(['export', *arguments])


@pytest.mark.parametrize('body', [
    'svx_args = None',
    'def svx_args(path, argv): return "--out generated"',
    'def svx_args(path, argv): return [123]',
    'def svx_args(path, argv): return ["--config=recursive"]',
    'def svx_args(path, argv): raise RuntimeError("invalid project setting")',
])
def test_invalid_adapters_fail_before_running_command(project, body):
    project[1].write_text(body)
    with pytest.raises(SVXError, match='configuration parser.*failed'):
        main(['export', *options(project)], out=io.StringIO())


def test_help_does_not_execute_parser(project, capsys):
    project[1].write_text('raise AssertionError("must not execute")')
    with pytest.raises(SystemExit) as error:
        main(['export', '--help', *options(project)])
    assert error.value.code == 0
    assert '--config-parser' in capsys.readouterr().out


def test_entrypoint_formats_adapter_errors_and_debug_preserves_traceback(project, capsys):
    project[1].write_text('def svx_args(path, argv): raise ValueError("bad setting")')
    arguments = ['export', *options(project)]
    assert entrypoint(arguments) == 2
    error = capsys.readouterr().err
    assert 'bad setting' in error and 'svx: error:' in error and 'Traceback' not in error
    with pytest.raises(SVXError, match='bad setting'):
        entrypoint(['--debug', *arguments])
    assert entrypoint([*arguments, '--debug']) == 2
    assert 'Traceback' not in capsys.readouterr().err


@pytest.mark.parametrize('inline', [False, True])
def test_every_trailing_token_is_owned_by_adapter(project, inline):
    config, parser = project
    tail = ['--profile', 'large project', '--help', '--debug', '--config', 'custom.json', '--', '-x']
    parser.write_text('''import json
def svx_args(path, argv):
    path.write_text(json.dumps(argv))
    return ['--package', 'selected_pkg']
''')
    flag = ['--config-parser=' + str(parser)] if inline else ['--config-parser', str(parser)]
    result = expand_config_arguments(['export', '--config', str(config), *flag, *tail])
    assert json.loads(config.read_text()) == tail
    assert result == ['export', '--package', 'selected_pkg']


def test_adapter_can_parse_custom_options_without_forwarding_them(project):
    project[1].write_text('''import argparse
def svx_args(path, argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    options = parser.parse_args(argv)
    return ['--package', options.profile + '_pkg']
''')
    assert expand_config_arguments(['export', *options(project), '--profile', 'uart']) == [
        'export', '--package', 'uart_pkg']


def test_trailing_help_is_processed_by_user_parser(project, capsys):
    project[1].write_text('''import argparse
def svx_args(path, argv):
    parser = argparse.ArgumentParser(description='Project configuration options')
    parser.add_argument('--profile')
    parser.parse_args(argv)
    return []
''')
    with pytest.raises(SystemExit) as error:
        main(['export', *options(project), '--help'])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert 'Project configuration options' in output
    assert '--profile' in output and '--config-parser' not in output


def test_config_export_uses_identical_generation_and_check_path(project, tmp_path):
    pytest.importorskip('pyslang')
    source = tmp_path / 'design.sv'
    source.write_text('package user_pkg; class Item; int value; endclass endpackage')
    root = tmp_path / 'generated'
    direct = ['--package', 'user_pkg', '--sv-source', str(source), '--out', str(root)]
    assert main(['export', *direct], out=io.StringIO()) == 0
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in root.rglob('*') if path.is_file()}
    project[0].write_text(json.dumps(direct))
    assert main(['export', *options(project), '--check'], out=io.StringIO()) == 0
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before}
    # The parser runs again for each command, including check/incremental use.
    project[0].write_text(json.dumps([*direct, '--member', 'missing']))
    with pytest.raises(SVXError, match='member selector'):
        main(['export', *options(project)], out=io.StringIO())
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before}
