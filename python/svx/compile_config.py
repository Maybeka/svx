"""Import existing build inputs without executing a compiler or shell command."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shlex

from .errors import SVXInheritanceError


@dataclass
class CompileConfiguration:
    sources: list[Path]
    include_dirs: list[Path]
    defines: dict[str, str | None]
    undefines: list[str]
    inputs: list[Path]
    shared: bool = False
    ignored: list[list[str]] | None = None
    library_dirs: list[Path] = field(default_factory=list)
    library_extensions: list[str] = field(default_factory=list)
    top_modules: list[str] = field(default_factory=list)

    def as_dict(self, root: Path) -> dict:
        relative = lambda path: Path(os.path.relpath(path, root)).as_posix()
        data = dict(sources=[relative(p) for p in self.sources],
                    include_dirs=[relative(p) for p in self.include_dirs],
                    defines=self.defines, undefines=self.undefines,
                    inputs=[relative(p) for p in self.inputs],
                    compilation_unit=self.shared, non_parser_arguments=self.ignored or [])
        if self.library_dirs or self.library_extensions:
            data.update(library_dirs=[relative(p) for p in self.library_dirs],
                        library_extensions=self.library_extensions)
        if self.top_modules:
            data['top_modules'] = self.top_modules
        return data


def _expand(value: str) -> str:
    def replace(match):
        name = next(item for item in match.groups() if item is not None)
        if name not in os.environ:
            raise SVXInheritanceError(f'undefined build environment variable: {name}')
        return os.environ[name]
    return os.path.expanduser(re.sub(r'\$\{(\w+)\}|\$\((\w+)\)|\$(\w+)', replace, value))


def _tokens(text: str, source: Path) -> list[str]:
    # Remove filelist comments without treating slashes inside quoted paths as comments.
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*'
    text = re.sub(pattern, lambda m: '\n' * m[0].count('\n') + ' '
                  if m[0].startswith(('//', '/*')) else m[0], text, flags=re.S)
    try:
        return shlex.split(text, comments=True)
    except ValueError as error:
        raise SVXInheritanceError(f'invalid filelist quoting in {source}: {error}') from error


def _implicit_uvm_library(library: str) -> Path:
    home = os.environ.get('VCS_HOME')
    if not home:
        raise SVXInheritanceError('implicit UVM library requires the original compiler environment')
    return Path(home).resolve() / 'etc' / library


def import_compile_configuration(recipe: dict, root: Path | None = None) -> CompileConfiguration:
    """-f paths use the invocation directory; -F contents use their file's directory.

    The JSON command input is {directory, arguments}; arguments are the actual
    compiler argv including its executable, not a shell script or make command.
    """
    if (not isinstance(recipe, dict) or set(recipe) - {'directory', 'commands', 'filelists', 'relative_filelists'}
            or not isinstance(recipe.get('directory', '.'), str)
            or any(not isinstance(recipe.get(key, []), list)
                   or any(not isinstance(p, str) or not p or '\0' in p for p in recipe.get(key, []))
                   for key in ('commands', 'filelists', 'relative_filelists'))):
        raise SVXInheritanceError('invalid build input recipe')
    root = (root or Path.cwd()).resolve()
    directory = (root / recipe.get('directory', '.')).resolve()
    result = CompileConfiguration([], [], {}, [], [], ignored=[])
    active: list[Path] = []

    def path(value, base):
        return (base / _expand(value)).resolve()

    def remember_input(value):
        if value not in result.inputs:
            result.inputs.append(value)

    def source(value):
        if not value.is_file():
            raise SVXInheritanceError(f'build source does not exist: {value}')
        if value in result.sources:
            raise SVXInheritanceError(f'duplicate build source: {value}')
        result.sources.append(value)

    def definition(value):
        name, separator, replacement = value.partition('=')
        if not name.isascii() or not name.isidentifier():
            raise SVXInheritanceError(f'unsupported build macro definition: {value}')
        result.defines[name] = replacement if separator else None
        if name in result.undefines:
            result.undefines.remove(name)

    def filelist(filename, base, relative):
        filename = path(filename, base)
        if filename in active:
            raise SVXInheritanceError('recursive filelist: ' + ' -> '.join(map(str, [*active, filename])))
        remember_input(filename)
        active.append(filename)
        try:
            parse(_tokens(filename.read_text(encoding='utf-8'), filename),
                  filename.parent if relative else base)
        finally:
            active.pop()

    def parse(arguments, base):
        index = 0
        while index < len(arguments):
            item = arguments[index]
            index += 1
            def argument():
                nonlocal index
                if index == len(arguments):
                    raise SVXInheritanceError(f'missing argument after {item}')
                value = arguments[index]
                index += 1
                return value

            if item in {'-f', '-F'}:
                filelist(argument(), base, item == '-F')
            elif item.startswith(('-f=', '-F=')):
                filelist(item[3:], base, item.startswith('-F'))
            elif item.startswith('+incdir+'):
                for value in item[len('+incdir+'):].split('+'):
                    if not value:
                        raise SVXInheritanceError('empty +incdir+ entry')
                    result.include_dirs.append(path(value, base))
            elif item == '-I' or item.startswith('-I'):
                result.include_dirs.append(path(argument() if item == '-I' else item[2:], base))
            elif item.startswith('+define+'):
                for value in item[len('+define+'):].split('+'):
                    definition(value)
            elif item == '-D' or item.startswith('-D'):
                definition(argument() if item == '-D' else item[2:])
            elif item == '-U' or item.startswith('-U'):
                name = argument() if item == '-U' else item[2:]
                if not name.isascii() or not name.isidentifier():
                    raise SVXInheritanceError(f'invalid macro undefinition: {name}')
                result.defines.pop(name, None)
                if name not in result.undefines:
                    result.undefines.append(name)
            elif item in {'--single-unit', '-mfcu'}:
                result.shared = True
            elif item in {'--separate-units', '-sfcu'}:
                result.shared = False
            elif item in {'-top', '--top-module'} or item.startswith(('-top=', '--top-module=')):
                top = argument() if '=' not in item else item.split('=', 1)[1]
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', top):
                    raise SVXInheritanceError(f'unsupported build top name: {top!r}')
                if top not in result.top_modules:
                    result.top_modules.append(top)
            elif item == '-v':
                source(path(argument(), base))
            elif item == '-y':
                result.library_dirs.append(path(argument(), base))
            elif item.startswith('+libext+'):
                for extension in item[len('+libext+'):].split('+'):
                    if (extension and (not extension.startswith('.')
                            or any(c in extension for c in '/\\\0\r\n'))):
                        raise SVXInheritanceError(f'invalid library extension: {extension!r}')
                    if extension not in result.library_extensions:
                        result.library_extensions.append(extension)
            elif item == '-ntb_opts':
                library = argument()
                if library not in {'uvm-1.1', 'uvm-1.2', 'uvm-ieee', 'uvm-ieee-2020'}:
                    raise SVXInheritanceError(f'unsupported implicit language library: {library}')
                location = _implicit_uvm_library(library)
                source(location / 'uvm_pkg.sv')
                result.include_dirs.append(location)
            elif item in {'-sverilog', '-sv', '-full64', '-licqueue', '-lca', '-dpi_lrm_task',
                          '-deraceclockdata', '-q', '-quiet'}:
                result.ignored.append([item])
            elif item in {'-o', '-l', '-CFLAGS', '-LDFLAGS', '-Xcflags', '-assert'}:
                result.ignored.append([item, argument()])
            elif item == '-xlrm':
                value = argument()
                if value != 'uniq_prior_final':
                    raise SVXInheritanceError(f'unsupported language extension: {item} {value}')
                result.ignored.append([item, value])
            elif item.startswith(('-Mdir=', '-timescale=', '-debug_region=', '-debug_access+',
                                  '+warn=', '-error=', '-xprop=', '-Xcflags=', '-CFLAGS=', '-LDFLAGS=')):
                result.ignored.append([item])
                if item.startswith('-xprop='):
                    value = item.partition('=')[2]
                    if value not in {'mmsopt', 'xmerge', 'tmerge'}:
                        config = path(value, base)
                        if not config.is_file():
                            raise SVXInheritanceError(f'build configuration file does not exist: {config}')
                        remember_input(config)
            elif item.startswith(('-', '+')):
                raise SVXInheritanceError(f'unsupported build option {item!r}; do not silently drop language configuration')
            elif Path(item).suffix.lower() in {'.sv', '.v', '.svh', '.vh'}:
                source(path(item, base))
            elif Path(item).suffix.lower() in {'.c', '.cc', '.cpp', '.cxx', '.o', '.a', '.so', '.dylib'}:
                result.ignored.append([item])
            else:
                raise SVXInheritanceError(f'unsupported build input: {item!r}')

    for value in recipe.get('commands', []):
        filename = path(value, root)
        remember_input(filename)
        try:
            data = json.loads(filename.read_text(encoding='utf-8'))
        except ValueError as error:
            raise SVXInheritanceError(f'invalid build command JSON: {filename}') from error
        if (not isinstance(data, dict) or set(data) != {'directory', 'arguments'}
                or not isinstance(data['directory'], str)
                or not isinstance(data['arguments'], list) or not data['arguments']
                or any(not isinstance(x, str) or not x or '\0' in x for x in data['arguments'])):
            raise SVXInheritanceError(f'build command requires directory and nonempty compiler arguments: {filename}')
        if Path(data['arguments'][0]).name in {'vcs', 'vcs.exe'}:
            result.shared = True
        parse(data['arguments'][1:], path(data['directory'], filename.parent))
    for value in recipe.get('filelists', []):
        filelist(value, directory, False)
    for value in recipe.get('relative_filelists', []):
        filelist(value, directory, True)
    return result


def replay_build_record(record: dict, root: Path) -> CompileConfiguration:
    if not isinstance(record, dict) or set(record) != {'recipe', 'configuration'}:
        raise SVXInheritanceError('invalid imported build configuration record')
    configuration = import_compile_configuration(record['recipe'], root)
    if configuration.as_dict(root) != record['configuration']:
        raise SVXInheritanceError('imported build configuration changed; refresh discovery and generated artifacts')
    return configuration
