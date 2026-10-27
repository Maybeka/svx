from __future__ import annotations

import argparse
import builtins
import importlib
import importlib.machinery
import importlib.util
import inspect
import hashlib
import json
import os
import sys
import sysconfig
from pathlib import Path, PurePosixPath
from posixpath import normpath as posix_normpath
from types import ModuleType
from typing import Iterable, TextIO
from contextlib import contextmanager

from .inheritance import (
    artifact_manifest,
    emit_python_mirrors,
    emit_sv_mirrors,
    emit_sv_mirror_stages,
    load_manifest,
    migrate_manifest,
    write_text_atomic,
    write_text_atomic_group,
    obsolete_generated_sources,
    write_generated_sources,
    validate_generated_sources,
    validate_output_path,
    generated_inventory_text,
    recover_obsolete_artifacts,
)
from .declarations import (
    enrich_virtual_interface_manifest,
    manifest_dict,
    manifest_from_declarations,
)
from .errors import SVXError, SVXInheritanceError
from .discovery_provenance import (
    _validate_python_selections, discovery_contract_digest, validate_discovery_provenance,
)


def repo_root() -> Path:
    source_root = sv_dir().parent
    if (source_root / "CMakeLists.txt").is_file():
        return source_root
    installed = Path(sysconfig.get_path("data")) / "share" / "svx"
    if (installed / "CMakeLists.txt").is_file():
        return installed
    return source_root


def sv_dir() -> Path:
    override = os.environ.get("SVX_SHARE_DIR")
    if override:
        path = Path(override).expanduser().resolve()
        if (path / "svx_pkg.sv").is_file():
            return path
        raise RuntimeError(f"SVX_SHARE_DIR does not contain svx_pkg.sv: {path}")

    for parent in Path(__file__).resolve().parents:
        for relative in ("sv", "share/svx/sv"):
            candidate = parent / relative
            if (candidate / "svx_pkg.sv").is_file():
                return candidate
    candidate = Path(sysconfig.get_path("data")) / "share" / "svx" / "sv"
    if (candidate / "svx_pkg.sv").is_file():
        return candidate
    raise RuntimeError(
        "SVX SystemVerilog support files are unavailable; install the SVX package "
        "or set SVX_SHARE_DIR to its sv directory"
    )


def svtypes_file() -> Path:
    import svtypes

    return svtypes.sv_runtime_file()


def build_dir() -> Path:
    override = os.environ.get("SVX_LIB_DIR")
    if override:
        return Path(override).expanduser().resolve()
    root = repo_root()
    if (root / "CMakeLists.txt").is_file():
        return root / "build"
    candidates = [
        Path(sysconfig.get_path("platlib")),
        Path(sys.prefix) / "lib",
        Path(sys.prefix) / "lib64",
    ]
    for candidate in candidates:
        if any(candidate.glob("libsvx.*")):
            return candidate
    raise RuntimeError(
        "the installed SVX native runtime was not found; set SVX_LIB_DIR to "
        "the CMake install library directory"
    )


def sv_files() -> list[Path]:
    return [svtypes_file(), sv_dir() / "svx_pkg.sv"]


def _print_lines(lines: Iterable[str], out: TextIO) -> None:
    for line in lines:
        print(line, file=out)


def _cmd_share(_args: argparse.Namespace, out: TextIO) -> int:
    print(sv_dir(), file=out)
    return 0


def _cmd_native_source(_args: argparse.Namespace, out: TextIO) -> int:
    root = repo_root()
    if not (root / "CMakeLists.txt").is_file() or not (
        root / "svx_runtime" / "src" / "svx.cpp"
    ).is_file():
        raise RuntimeError("installed SVX native build sources are unavailable")
    print(root, file=out)
    return 0


def _cmd_sv_files(_args: argparse.Namespace, out: TextIO) -> int:
    _print_lines((str(path) for path in sv_files()), out)
    return 0


def _cmd_libs(_args: argparse.Namespace, out: TextIO) -> int:
    lib = build_dir() / "libsvx"
    print(str(lib), file=out)
    return 0


def _cmd_compile_flags(_args: argparse.Namespace, out: TextIO) -> int:
    root = repo_root()
    _print_lines(
        [
            f"+incdir+{root}",
            f"+incdir+{svtypes_file().parent}",
            *(str(path) for path in sv_files()),
        ],
        out,
    )
    return 0


def _is_direct_member(obj: object, module: ModuleType) -> bool:
    return getattr(obj, "__module__", None) == module.__name__


def _is_sv_enum_class(obj: object) -> bool:
    try:
        from svtypes import Enum
    except ImportError:
        return False
    return inspect.isclass(obj) and obj is not Enum and issubclass(obj, Enum)


def _is_sv_object_class(obj: object) -> bool:
    try:
        from svtypes import SvObject
    except ImportError:
        return False
    return inspect.isclass(obj) and obj is not SvObject and issubclass(obj, SvObject)


def _select_types(module_names: list[str], type_names: list[str] | None) -> list[type]:
    modules = [importlib.import_module(name) for name in module_names]
    selected: list[type] = []
    seen: set[type] = set()

    if type_names:
        requested = set(type_names)
        for module in modules:
            for name in list(requested):
                obj = getattr(module, name, None)
                if obj is None:
                    continue
                if not (_is_sv_enum_class(obj) or _is_sv_object_class(obj)):
                    raise SystemExit(f"{module.__name__}.{name} is not an SvTypes enum or object class")
                if obj not in seen:
                    selected.append(obj)
                    seen.add(obj)
                requested.remove(name)
        if requested:
            missing = ", ".join(sorted(requested))
            raise SystemExit(f"SvTypes classes not found in selected modules: {missing}")
        return selected

    for module in modules:
        for obj in module.__dict__.values():
            if not (_is_sv_enum_class(obj) or _is_sv_object_class(obj)):
                continue
            if not _is_direct_member(obj, module):
                continue
            if obj not in seen:
                selected.append(obj)
                seen.add(obj)
    return selected


def _sv_helper_block(obj_cls: type, level: int = 0) -> str:
    ind = "  " * level
    ind1 = "  " * (level + 1)
    type_name = obj_cls.__name__
    import svtypes

    descriptor = svtypes.encoding_descriptor(obj_cls)
    type_id = descriptor.unified_type_name
    fingerprint = descriptor.encoding_fingerprint_hex
    format_version = descriptor.binary_format_version
    checked_args = (
        f'"{type_name}", "{type_id}", "{fingerprint}", '
        f'{format_version}'
    )
    put_metadata = (
        f'"svtypes", "{type_name}", "application/x-svtypes", '
        f'"{type_id}", "{fingerprint}", {format_version}'
    )
    return "\n".join(
        [
            f"{ind}task automatic svx_get_{type_name}(string channel_name, output {type_name} item);",
            f"{ind1}chandle payload;",
            f"{ind1}byte unsigned bytes[$];",
            f"{ind1}int offset;",
            f"{ind1}svx_pkg::svx_channel_get_payload(channel_name, payload);",
            f'{ind1}svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, {checked_args}, "svx_get_{type_name}", bytes);',
            f"{ind1}svx_pkg::svx_payload_destroy(payload);",
            f"{ind1}item = new();",
            f"{ind1}offset = 0;",
            f"{ind1}item.unpack(bytes, offset);",
            f'{ind1}svx_pkg::svx_require_unpacked_all("svx_get_{type_name}", channel_name, "{type_name}", offset, bytes.size());',
            f"{ind}endtask",
            "",
            f"{ind}task automatic svx_peek_{type_name}(string channel_name, output {type_name} item);",
            f"{ind1}chandle payload;",
            f"{ind1}byte unsigned bytes[$];",
            f"{ind1}int offset;",
            f"{ind1}svx_pkg::svx_channel_peek_payload(channel_name, payload);",
            f'{ind1}svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, {checked_args}, "svx_peek_{type_name}", bytes);',
            f"{ind1}item = new();",
            f"{ind1}offset = 0;",
            f"{ind1}item.unpack(bytes, offset);",
            f'{ind1}svx_pkg::svx_require_unpacked_all("svx_peek_{type_name}", channel_name, "{type_name}", offset, bytes.size());',
            f"{ind}endtask",
            "",
            f"{ind}task automatic svx_put_{type_name}(string channel_name, input {type_name} item);",
            f"{ind1}byte unsigned bytes[$];",
            f"{ind1}if (item == null) begin",
            f'{ind1}  $fatal(2, "svx_put_{type_name}(%s): cannot put null SvTypes object type {type_name}", channel_name);',
            f"{ind1}end",
            f"{ind1}item.pack(bytes);",
            f'{ind1}svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, {put_metadata});',
            f"{ind}endtask",
            "",
            f"{ind}task automatic svx_try_get_{type_name}(string channel_name, output bit ok, output {type_name} item);",
            f"{ind1}chandle payload;",
            f"{ind1}byte unsigned bytes[$];",
            f"{ind1}int offset;",
            f"{ind1}payload = svx_pkg::svx_channel_try_get_payload(channel_name);",
            f"{ind1}if (payload == null) begin",
            f"{ind1}  ok = 0;",
            f"{ind1}  item = null;",
            f"{ind1}  return;",
            f"{ind1}end",
            f'{ind1}svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, {checked_args}, "svx_try_get_{type_name}", bytes);',
            f"{ind1}svx_pkg::svx_payload_destroy(payload);",
            f"{ind1}item = new();",
            f"{ind1}offset = 0;",
            f"{ind1}item.unpack(bytes, offset);",
            f'{ind1}svx_pkg::svx_require_unpacked_all("svx_try_get_{type_name}", channel_name, "{type_name}", offset, bytes.size());',
            f"{ind1}ok = 1;",
            f"{ind}endtask",
            "",
            f"{ind}function automatic bit svx_try_put_{type_name}(string channel_name, input {type_name} item);",
            f"{ind1}byte unsigned bytes[$];",
            f"{ind1}if (item == null) begin",
            f'{ind1}  $fatal(2, "svx_try_put_{type_name}(%s): cannot put null SvTypes object type {type_name}", channel_name);',
            f"{ind1}end",
            f"{ind1}item.pack(bytes);",
            f'{ind1}return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, {put_metadata});',
            f"{ind}endfunction",
        ]
    )


def _emit_svtypes(types: list[type], package: str | None, source: str, channel_helpers: bool = False) -> str:
    enums = [cls for cls in types if _is_sv_enum_class(cls)]
    objects = [cls for cls in types if _is_sv_object_class(cls)]
    object_names = [cls.__name__ for cls in objects]
    duplicate_names = sorted({name for name in object_names if object_names.count(name) > 1})
    if channel_helpers and duplicate_names:
        raise SystemExit(
            "duplicate SvTypes object names cannot generate channel helpers: "
            + ", ".join(duplicate_names)
        )
    body: list[str] = [
        f"// Generated from {source}",
        "// Do not edit by hand.",
        "",
    ]

    if package:
        body.append(f"package {package};")
        body.append("")

    content_level = 1 if package else 0
    ind = "  " if package else ""

    for enum_cls in enums:
        body.append(enum_cls.to_sv_enum(content_level))
        body.append("")

    for obj_cls in objects:
        body.append(f"{ind}typedef class {obj_cls.__name__};")
    if objects:
        body.append("")

    for obj_cls in objects:
        body.append(obj_cls.to_sv_obj(content_level))
        body.append("")

    if channel_helpers and objects:
        body.append(f"{ind}// SvTypes typed channel helpers")
        for obj_cls in objects:
            body.append(_sv_helper_block(obj_cls, content_level))
            body.append("")

    if package:
        body.append(f"endpackage : {package}")
        body.append("")

    return "\n".join(body).rstrip() + "\n"


def _cmd_svtypes_gen(args: argparse.Namespace, out: TextIO) -> int:
    type_names = None
    if args.types:
        type_names = [name.strip() for part in args.types for name in part.split(",") if name.strip()]
    classes = _select_types(args.module, type_names)
    source = ", ".join(args.module)
    text = _emit_svtypes(classes, args.package, source, channel_helpers=args.channel_helpers)
    if args.out:
        write_text_atomic(Path(args.out), text)
    else:
        print(text, end="", file=out)
    return 0


def _sv_macro_config(args: argparse.Namespace) -> dict:
    from .compile_config import import_compile_configuration
    if not hasattr(args, '_explicit_sv_sources'):
        args._explicit_sv_sources = list(args.sv_source)
    recipe = {
        'directory': str(Path(getattr(args, 'sv_build_directory', None) or '.').resolve()),
        'filelists': [str(Path(p).resolve()) for p in getattr(args, 'sv_filelist', [])],
        'relative_filelists': [str(Path(p).resolve()) for p in getattr(args, 'sv_relative_filelist', [])],
        'commands': [str(Path(p).resolve()) for p in getattr(args, 'sv_build_command', [])],
    }
    imported = import_compile_configuration(recipe)
    args._sv_build_configuration = imported
    args._sv_build_recipe = recipe
    args.sv_source = [str(p) for p in imported.sources] + args._explicit_sv_sources
    definitions = dict(imported.defines)
    explicit = {}
    for item in args.sv_define:
        name, separator, value = item.partition("=")
        replacement = value if separator else None
        if name in explicit and explicit[name] != replacement:
            raise SystemExit(f"conflicting --sv-define values for {name}")
        explicit[name] = replacement
        definitions[name] = replacement
    undefines = [name for name in imported.undefines if name not in explicit] + list(args.sv_undefine)
    for name in undefines:
        definitions.pop(name, None)
    shared = args.sv_compilation_unit or imported.shared
    includes = [str(p) for p in imported.include_dirs] + list(args.sv_include_dir)
    if (definitions or undefines or shared or includes) and not args.sv_source:
        raise SystemExit("SV source configuration requires --sv-source")
    if definitions or undefines or includes:
        from .sv_source_options import _source_parse_options
        _source_parse_options(definitions, undefines, includes)
    return {"sv_predefines": definitions, "sv_undefines": undefines,
            "sv_compilation_unit": shared, "sv_include_dirs": includes}


def _sv_build_record(args, root):
    imported = args._sv_build_configuration
    if not imported.inputs:
        return None
    recipe = args._sv_build_recipe
    relative = lambda p: Path(os.path.relpath(p, root)).as_posix()
    return {'recipe': {'directory': relative(recipe['directory']),
                       **{key: [relative(p) for p in recipe[key]]
                          for key in ('filelists', 'relative_filelists', 'commands')}},
            'configuration': imported.as_dict(root)}


def _cmd_compile_config(args, out):
    effective = _sv_macro_config(args)
    root = Path.cwd()
    relative = lambda p: Path(os.path.relpath(Path(p).resolve(), root)).as_posix()
    data = args._sv_build_configuration.as_dict(root)
    data.update(sources=[relative(p) for p in args.sv_source],
                include_dirs=[relative(p) for p in effective['sv_include_dirs']],
                defines=effective['sv_predefines'], undefines=effective['sv_undefines'],
                compilation_unit=effective['sv_compilation_unit'])
    text = json.dumps(data, indent=2) + '\n'
    if args.out:
        _protect_generation_inputs([Path(args.out)], [*args._sv_build_configuration.inputs,
                                                    *(Path(p) for p in args.sv_source)])
        write_text_atomic(Path(args.out), text)
    else:
        print(text, end='', file=out)
    return 0


def _cmd_inheritance_gen(args: argparse.Namespace, out: TextIO) -> int:
    _sv_macro_config(args)
    from .sv_library_search import library_search
    certified_sources = {}
    with library_search(args._sv_build_configuration), _fresh_declaration_entries((), all_sources=True,
                                    cached_sources=certified_sources,
                                    command='inheritance-gen') as consumed:
        return _generate_inheritance(args, out, consumed, certified_sources)


def _generate_inheritance(args: argparse.Namespace, out: TextIO, consumed: dict,
                          certified_sources: dict) -> int:
    macro_config = _sv_macro_config(args)
    integrated_dir = getattr(args, 'sv_integrated_dir', None)
    output_options = (args.sv_out, args.sv_stage_dir, integrated_dir)
    if sum(bool(option) for option in output_options) > 1:
        raise SystemExit("inheritance-gen accepts only one of --sv-out, --sv-stage-dir, --sv-integrated-dir")
    if integrated_dir and not args.sv_source:
        raise SystemExit('--sv-integrated-dir requires --sv-source')
    if integrated_dir and len(args.sv_source) > 1 and not macro_config['sv_compilation_unit']:
        raise SystemExit('multiple integrated sources require --sv-compilation-unit')
    if args.check and (not args.python_out or not any(output_options) or not args.artifact_manifest):
        raise SystemExit(
            "inheritance-gen --check requires --python-out, one SV output option, and --artifact-manifest")
    if integrated_dir and len({Path(path).resolve() for path in args.sv_source}) != len(args.sv_source):
        raise SVXInheritanceError('duplicate integrated source input')
    python_dependencies = _python_source_dependencies(args)
    input_root = Path(args.artifact_manifest).parent.resolve() if args.artifact_manifest else Path.cwd()
    args._generation_imports = _cached_generation_imports(args, input_root)
    input_fingerprints = _generation_inputs(args, input_root, certified_sources)
    manifest = load_manifest(Path(args.manifest))
    manifest = enrich_virtual_interface_manifest(
        manifest, sv_source_files=[Path(item) for item in args.sv_source], **macro_config
    )
    stage_root = Path(integrated_dir or args.sv_stage_dir) if integrated_dir or args.sv_stage_dir else None
    if integrated_dir:
        from .source_layout import _emit_source_units
        from .inheritance import _emit_source_python_artifacts, _manifest_sv_record_types
        inputs = {str(Path(path).resolve()): Path(path).read_text(encoding='utf-8')
                  for path in args.sv_source}
        python_sources = _emit_source_python_artifacts(manifest)
        records = ['// Generated by svx inheritance-gen. Do not edit.',
                   'package svx_call_records_pkg;', '  import svtypes_pkg::*;']
        records.extend(record.to_sv_obj(1) for record in _manifest_sv_record_types(manifest))
        records.append('endpackage : svx_call_records_pkg')
        sv_text = '\n'.join(records) + '\n' + _emit_source_units(
            manifest, inputs, predefines=macro_config['sv_predefines'],
            undefines=macro_config['sv_undefines'], include_dirs=macro_config['sv_include_dirs'])
        stage_sources = {'source.sv': sv_text}
    else:
        python_sources = emit_python_mirrors(manifest)
        sv_text = emit_sv_mirrors(manifest)
        stage_sources = emit_sv_mirror_stages(manifest) if args.sv_stage_dir else None
    sv_outputs: dict[Path, str]
    if stage_sources is not None:
        sv_outputs = {stage_root / relative: source for relative, source in stage_sources.items()}
    elif args.sv_out:
        sv_outputs = {Path(args.sv_out): sv_text}
    else:
        sv_outputs = {}
    if args.check:
        mismatches: list[Path] = []
        inventories = [(Path(args.python_out) / ".svx-generated-python.json", python_sources)]
        if stage_sources is not None:
            inventories.append((stage_root / ".svx-generated-sv.json", stage_sources))
        for target, sources in inventories:
            if not target.is_file() or target.read_text(encoding="utf-8") != generated_inventory_text(sources):
                mismatches.append(target)
        mismatches.extend(obsolete_generated_sources(
            Path(args.python_out), python_sources, ".svx-generated-python.json"
        ))
        if stage_sources is not None:
            mismatches.extend(obsolete_generated_sources(
                stage_root, stage_sources, ".svx-generated-sv.json"
            ))
        python_targets = [Path(args.python_out) / path for path in python_sources]
        for target, source in zip(python_targets, python_sources.values()):
            if not target.is_file() or target.read_text(encoding="utf-8") != source:
                mismatches.append(target)
        for sv_target, source in sv_outputs.items():
            if not sv_target.is_file() or sv_target.read_text(encoding="utf-8") != source:
                mismatches.append(sv_target)
        artifact_target = Path(args.artifact_manifest)
        artifact_text = _generated_artifact_text(
            manifest, python_sources, sv_text, sv_outputs, args, artifact_target,
            generation_inputs=input_fingerprints,
            consumed_sources=consumed,
        )
        _require_stable_generation_inputs(args, input_root, input_fingerprints, consumed_sources=consumed)
        bridge_mismatches = bool(mismatches)
        previous_artifact = artifact_target.read_text(encoding="utf-8") if artifact_target.is_file() else None
        if (
            previous_artifact != artifact_text
        ):
            mismatches.append(artifact_target)
        if mismatches:
            raise SystemExit(
                "generated inheritance artifacts are stale: "
                + ", ".join(str(path) for path in mismatches)
                + _artifact_change_diagnostic(previous_artifact, artifact_text,
                                              bridge_mismatches=bridge_mismatches)
            )
        for path in [*python_targets, *sv_outputs, artifact_target]:
            print(path, file=out)
        return 0
    if args.python_out:
        validate_generated_sources(python_sources, Path(args.python_out), ".svx-generated-python.json")
    if stage_sources is not None:
        validate_generated_sources(stage_sources, stage_root, ".svx-generated-sv.json")
    else:
        for sv_target, source in sv_outputs.items():
            validate_generated_sources({sv_target.name: source}, sv_target.parent)
    artifact_path = Path(args.artifact_manifest) if args.artifact_manifest else None
    artifact_text = None
    previous = None
    if artifact_path is not None:
        validate_output_path(artifact_path)
        if artifact_path.is_file():
            try:
                previous = json.loads(artifact_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                previous = None
            if not isinstance(previous, dict) or previous.get("schema_uri") != "https://svx.dev/schema/generated-artifacts/v1":
                raise SVXInheritanceError(f"refusing to overwrite non-generated artifact manifest {artifact_path}")
        artifact_text = _generated_artifact_text(
            manifest, python_sources, sv_text, sv_outputs, args, artifact_path,
            generation_inputs=input_fingerprints,
            consumed_sources=consumed,
        )
    targets = list(sv_outputs)
    if args.python_out:
        targets.extend(Path(args.python_out) / path for path in python_sources)
        targets.append(Path(args.python_out) / ".svx-generated-python.json")
    if stage_sources is not None:
        targets.append(stage_root / ".svx-generated-sv.json")
    if artifact_path is not None:
        targets.append(artifact_path)
    resolved = set()
    for target in targets:
        path = target.resolve()
        if path in resolved:
            raise SVXInheritanceError(f"generated output path is used more than once: {path}")
        resolved.add(path)
    for target in targets:
        path = target.resolve()
        for parent in path.parents:
            if parent in resolved:
                raise SVXInheritanceError(f"generated output paths conflict: {path} and {parent}")
    protected_inputs = {*consumed, *getattr(args, '_generation_imports', {}),
                        *getattr(args, '_discovery_sources', ()),
                        Path(args.manifest).resolve(), *_sv_source_dependencies(args),
                        *args._sv_build_configuration.inputs,
                        *python_dependencies}
    removable = []
    if args.python_out:
        removable.extend(obsolete_generated_sources(
            Path(args.python_out), python_sources, ".svx-generated-python.json"))
    if stage_sources is not None:
        removable.extend(obsolete_generated_sources(
            stage_root, stage_sources, ".svx-generated-sv.json"))
    _protect_generation_inputs([*targets, *removable], protected_inputs)
    recovered_obsolete = []
    if previous is not None:
        if args.python_out:
            recovered_obsolete.extend(recover_obsolete_artifacts(
                previous, artifact_path, Path(args.python_out), python_sources,
                "python", targets
            ))
        if stage_sources is not None:
            recovered_obsolete.extend(recover_obsolete_artifacts(
                previous, artifact_path, stage_root, stage_sources,
                "systemverilog", targets
            ))
    _protect_generation_inputs(recovered_obsolete, protected_inputs)
    _require_stable_generation_inputs(args, input_root, input_fingerprints, consumed_sources=consumed)
    if args.python_out:
        written = write_generated_sources(python_sources, Path(args.python_out), ".svx-generated-python.json")
        for path in written:
            print(path, file=out)
    if stage_sources is not None:
        for target in write_generated_sources(stage_sources, stage_root, ".svx-generated-sv.json"):
            print(target, file=out)
    else:
        for sv_target, source in sv_outputs.items():
            write_text_atomic(sv_target, source)
            print(sv_target, file=out)
    if not sv_outputs and sv_text.strip() != "// Generated by svx inheritance-gen. Do not edit.":
        print(sv_text, end="", file=out)
    for path in recovered_obsolete:
        path.unlink(missing_ok=True)
    if artifact_path is not None:
        write_text_atomic(artifact_path, artifact_text)
        print(artifact_path, file=out)
    return 0


def _artifact_change_diagnostic(previous_text: str | None, expected_text: str,
                                *, bridge_mismatches: bool) -> str:
    if previous_text is None:
        return "\nArtifact manifest is missing; regenerate before running the artifact build check."
    try:
        previous, expected = json.loads(previous_text), json.loads(expected_text)
    except (ValueError, TypeError):
        return "\nArtifact manifest JSON is invalid; regenerate the artifact manifest."
    if not isinstance(previous, dict) or not isinstance(expected, dict):
        return "\nArtifact manifest metadata is invalid; regenerate the artifact manifest."
    old_inputs, new_inputs = previous.get('generation_inputs'), expected.get('generation_inputs')
    if not isinstance(old_inputs, dict) or not isinstance(new_inputs, dict):
        return "\nArtifact input records are missing or invalid; regenerate the artifact manifest."
    changed = [key for key in sorted(old_inputs.keys() | new_inputs.keys())
               if old_inputs.get(key) != new_inputs.get(key)]
    details = []
    for key in changed:
        old, new = old_inputs.get(key), new_inputs.get(key)
        if key in {'manifest', 'python_sources', 'python_imports', 'sv_dependencies'}:
            def records(value):
                items = [value] if key == 'manifest' else (value if value is not None else [])
                if (not isinstance(items, list)
                        or any(not isinstance(item, dict) or not isinstance(item.get('path'), str)
                               or not isinstance(item.get('sha256'), str) for item in items)):
                    return None
                result = {item['path']: item['sha256'] for item in items}
                return result if len(result) == len(items) else None
            old_records, new_records = records(old), records(new)
            if old_records is not None and new_records is not None:
                for path in sorted(old_records.keys() | new_records.keys()):
                    action = ('added' if path not in old_records else
                              'removed' if path not in new_records else
                              'changed' if old_records[path] != new_records[path] else None)
                    if action is not None:
                        details.append(f'{key}: {action} {json.dumps(path)}')
                continue
        details.append(f'{key}: changed')
    notes = ['Recorded inputs changed: ' + '; '.join(details)] if details else []
    metadata_matches = ({key: value for key, value in previous.items() if key != 'generation_inputs'}
                        == {key: value for key, value in expected.items() if key != 'generation_inputs'})
    if (not bridge_mismatches and metadata_matches and changed
            and set(changed) <= {'python_sources', 'python_imports'}):
        notes.extend([
            'Generated bridge files match; only recorded Python inputs changed.',
            'Rerun discovery first if declarations changed. Otherwise rerun inheritance-gen without --check to refresh the input record; unchanged bridge files retain their timestamps.',
        ])
    elif changed:
        notes.append('Rerun discovery if declarations changed, then regenerate and rebuild affected source inputs; matching generated bridges alone do not prove the whole build is current.')
    return ''.join('\n' + note for note in notes)


def _generated_artifact_text(
    manifest,
    python_sources,
    sv_text: str,
    sv_outputs: dict[Path, str],
    args: argparse.Namespace,
    artifact_path: Path,
    *, generation_inputs: dict | None = None,
    consumed_sources: dict | None = None,
) -> str:
    artifact_root = artifact_path.parent.resolve()
    python_prefix = ""
    if args.python_out:
        python_prefix = os.path.relpath(Path(args.python_out).resolve(), artifact_root)
    artifact_sv_sources = {
        PurePosixPath(os.path.relpath(path.resolve(), artifact_root)): source
        for path, source in sv_outputs.items()
    }
    if not artifact_sv_sources:
        artifact_sv_sources = {PurePosixPath("mirrors.sv"): sv_text}
    description = artifact_manifest(
        manifest, python_sources, python_path_prefix=python_prefix,
        sv_sources=artifact_sv_sources,
    )
    if generation_inputs is not None and consumed_sources is not None:
        imports = dict(getattr(args, '_generation_imports', {}))
        imports.update({path: next(iter(digests)) for path, digests in consumed_sources.items()
                        if not _is_framework_source(path)})
        args._generation_imports = imports
        if imports:
            generation_inputs['python_imports'] = [
                {'path': Path(os.path.relpath(path, artifact_root)).as_posix(), 'sha256': digest}
                for path, digest in sorted(imports.items())]
    description["generation_inputs"] = (_generation_inputs(args, artifact_root)
                                        if generation_inputs is None else generation_inputs)
    return (
        json.dumps(
            description,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _protect_generation_inputs(targets, inputs) -> None:
    for target in targets:
        path = target.resolve()
        for source in inputs:
            if path == source or (target.exists() and source.exists() and target.samefile(source)):
                raise SVXInheritanceError(f"generated output would replace or remove input source: {target}")


_STDLIB_SOURCE_ROOTS = tuple(dict.fromkeys(
    Path(sysconfig.get_path(key)).resolve() for key in ('stdlib', 'platstdlib')))


def _is_framework_source(path: Path, *, resolved: bool = False) -> bool:
    """Classify the current source location, without retaining root state."""
    # Framework imports depend on interpreter warm-up, not the user's source graph.
    # Use string path operations: pathlib parent construction itself imports
    # modules, recursively feeding the scoped import audit on some interpreters.
    source = os.fspath(path) if resolved else os.path.realpath(path)
    def within(root):
        try:
            return os.path.commonpath((source, root)) == root
        except ValueError:
            return False

    for directory in _STDLIB_SOURCE_ROOTS:
        root = str(directory)
        if within(root):
            relative = os.path.relpath(source, root)
            if os.path.splitext(relative.split(os.sep, 1)[0])[0] in sys.stdlib_module_names:
                return True
    for name in ('svx', 'svtypes', 'pyslang'):
        package = sys.modules.get(name)
        for directory in getattr(package, '__path__', ()):
            root = os.fspath(directory)
            # A canonical source cannot contain an unresolved symlink prefix.
            # Aliased or relative package roots still require live resolution.
            if os.path.isabs(root) and os.path.normpath(root) == root and within(root):
                return True
            root = os.path.realpath(directory)
            if within(root):
                return True
    return False


def _cached_generation_imports(args, root: Path) -> dict:
    """Retain audited imports reused by an in-process caller, without reloading."""
    if not args.artifact_manifest or not Path(args.artifact_manifest).is_file():
        return {}
    try:
        previous = json.loads(Path(args.artifact_manifest).read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return {}
    inputs = previous.get('generation_inputs', {}) if isinstance(previous, dict) else {}
    records = inputs.get('python_imports', []) if isinstance(inputs, dict) else []
    if not isinstance(records, list) or any(
            not isinstance(item, dict) or not isinstance(item.get('path'), str)
            or not isinstance(item.get('sha256'), str) for item in records):
        raise SVXInheritanceError('invalid automatic Python input records in artifact manifest')
    checked = []
    seen = set()
    for item in records:
        name, digest = item['path'], item['sha256']
        if (not name or '\0' in name or PurePosixPath(name).is_absolute()
                or name == '.' or PurePosixPath(name).as_posix() != name
                or posix_normpath(name) != name
                or len(digest) != 64 or not set(digest) <= set('0123456789abcdef')):
            raise SVXInheritanceError('invalid automatic Python input records in artifact manifest')
        path = (root / name).resolve()
        if path in seen:
            raise SVXInheritanceError('duplicate automatic Python input records in artifact manifest')
        seen.add(path)
        checked.append((path, digest))
    cached = {Path(module.__file__).resolve() for module in tuple(sys.modules.values())
              if getattr(module, '__file__', None)}
    result = {}
    for path, digest in checked:
        if _is_framework_source(path):
            continue
        if path not in cached:
            continue
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SVXInheritanceError(
                f'audited Python source changed while its module is cached: {path}; '
                'rerun inheritance-gen in a fresh Python process')
        result[path] = digest
    return result


def _sv_source_dependencies(args: argparse.Namespace) -> set[Path]:
    macro_config = _sv_macro_config(args)
    from .sv_source_options import _source_dependencies
    return _source_dependencies(args.sv_source, predefines=macro_config['sv_predefines'],
                                undefines=macro_config['sv_undefines'],
                                include_dirs=macro_config['sv_include_dirs'],
                                compilation_unit=macro_config['sv_compilation_unit'])


def _python_source_dependencies(args: argparse.Namespace) -> set[Path]:
    dependencies = set()
    for value in args.python_source:
        path = Path(value).resolve()
        if not path.is_file():
            raise SVXInheritanceError(f"Python source input is not a file: {value}")
        dependencies.add(path)
    return dependencies


def _changed_consumed_sources(consumed: dict) -> list[str]:
    return [str(path) for path, digests in sorted(consumed.items())
            if digests != {hashlib.sha256(path.read_bytes()).hexdigest()}]


def _require_stable_generation_inputs(args: argparse.Namespace, root: Path, fingerprints: dict,
                                      *, consumed_sources: dict | None = None) -> None:
    try:
        current = _generation_inputs(args, root)
        changed_imports = _changed_consumed_sources(consumed_sources or {})
    except (OSError, SVXInheritanceError) as error:
        raise SVXInheritanceError(
            'generation inputs could not be revalidated; no generated outputs were written. '
            'Retry after the source inputs are stable.'
        ) from error
    if current != fingerprints or changed_imports:
        diagnostic = _artifact_change_diagnostic(
            json.dumps({'generation_inputs': fingerprints}),
            json.dumps({'generation_inputs': current}), bridge_mismatches=True,
        )
        raise SVXInheritanceError(
            'generation inputs changed during generation; no generated outputs were written. '
            'Retry after the source inputs are stable.' + diagnostic
            + ('\nImported sources changed: ' + ', '.join(changed_imports) if changed_imports else '')
        )


def _generation_inputs(args: argparse.Namespace, root: Path, certified_sources=None) -> dict:
    """Record selected source dependencies, not a simulator build recipe."""
    macro_config = _sv_macro_config(args)
    source_paths = [Path(path).resolve() for path in args.sv_source]
    dependencies = _sv_source_dependencies(args)

    def relative(path):
        return Path(os.path.relpath(path, root)).as_posix()

    def file_record(path):
        return {"path": relative(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    inputs = {
        "manifest": file_record(Path(args.manifest).resolve()),
        "sv_sources": [relative(path) for path in source_paths],
        "sv_dependencies": [file_record(path) for path in sorted(dependencies)],
        "sv_predefines": dict(sorted(macro_config["sv_predefines"].items())),
        "sv_undefines": sorted(set(macro_config["sv_undefines"])),
        "sv_include_dirs": [relative(Path(path).resolve()) for path in macro_config["sv_include_dirs"]],
        "source_mode": "shared-compilation-unit" if macro_config['sv_compilation_unit'] else "separate-parse-inputs",
    }
    if build_record := _sv_build_record(args, root):
        inputs['sv_build'] = build_record
        inputs['sv_build_inputs'] = [file_record(path) for path in args._sv_build_configuration.inputs]
    python_dependencies = _python_source_dependencies(args)
    if python_dependencies:
        inputs["python_sources"] = [file_record(path) for path in sorted(python_dependencies)]
    imported = getattr(args, '_generation_imports', {})
    if imported:
        inputs['python_imports'] = [file_record(path) for path in sorted(imported)]
    manifest_path = Path(args.manifest).resolve()
    try:
        manifest_data = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise SVXInheritanceError(f'cannot read inheritance manifest {manifest_path}: {error}') from error
    discovery_fingerprints = {}
    discovered = (validate_discovery_provenance(
        manifest_data, manifest_path, fingerprints=discovery_fingerprints)
                  if isinstance(manifest_data, dict) else ())
    args._discovery_sources = discovered
    if discovered:
        inputs['discovery_inputs'] = [
            {'path': relative(path), 'sha256': discovery_fingerprints[path]}
            for path in discovered]
    if certified_sources is not None:
        certified_sources.update(imported)
        certified_sources.update(discovery_fingerprints)
    return inputs


def _cmd_inheritance_migrate(args: argparse.Namespace, out: TextIO) -> int:
    source = Path(args.manifest)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read inheritance manifest {source}: {error}") from error
    migrated = migrate_manifest(data)
    text = json.dumps(migrated, indent=2, sort_keys=True) + "\n"
    if args.out:
        write_text_atomic(Path(args.out), text)
    else:
        print(text, end="", file=out)
    return 0


def _manifest_input_fingerprints(args: argparse.Namespace) -> dict:
    def record(path):
        path = Path(path).resolve()
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    inputs = {
        'sv_declarations': [record(path) for path in args.sv_declarations],
        'sv_dependencies': [record(path) for path in sorted(_sv_source_dependencies(args))],
        'python_sources': [record(path) for path in sorted(_python_source_dependencies(args))],
        'sv_build_inputs': [record(path) for path in args._sv_build_configuration.inputs],
    }
    if build_record := _sv_build_record(args, Path.cwd()):
        inputs['sv_build'] = build_record
    modules = []
    for name in args.python_module:
        loaded = sys.modules.get(name)
        if loaded is not None:
            path = getattr(loaded, '__file__', None)
        else:
            spec = importlib.util.find_spec(name)
            path = spec.origin if spec is not None else None
        item = {'module': name}
        if path is not None and Path(path).is_file():
            item.update(record(path))
        modules.append(item)
    inputs['python_modules'] = modules
    return inputs


class _DeclarationSourceLoader(importlib.machinery.SourceFileLoader):
    def __init__(self, fullname, path, consumed, active):
        super().__init__(fullname, path)
        self.consumed = consumed
        self.active = active

    def exec_module(self, module):
        self.active[0] += 1
        try:
            super().exec_module(module)
        finally:
            self.active[0] -= 1

    def get_code(self, fullname):
        # Declaration discovery must observe source edits, not timestamp-valid pyc.
        source = self.get_data(self.path)
        self.consumed.setdefault(Path(self.path).resolve(), set()).add(
            hashlib.sha256(source).hexdigest())
        return self.source_to_code(source, self.path)


@contextmanager
def _fresh_declaration_entries(names, source_paths=(), *, all_sources=False,
                               cached_sources=None, command='inheritance-manifest'):
    """Read ordinary sources freshly, without replacing custom or cached imports.

    Discovery and generation load codecs after entry execution; all_sources keeps
    that materialization inside the same consumed-source protection boundary.
    """
    selected = frozenset('.'.join(parts[:index])
                         for name in names for parts in [name.split('.')]
                         for index in range(1, len(parts) + 1))
    selected_paths = frozenset(Path(path).resolve() for path in source_paths)
    consumed = {}
    active = [0]
    original_import = builtins.__import__
    original_import_module = importlib.import_module

    def certify(name):
        if cached_sources is None or not (active[0] or all_sources):
            return
        module = sys.modules.get(name)
        spec = getattr(module, '__spec__', None)
        if (spec is None or not isinstance(spec.loader, importlib.machinery.SourceFileLoader)
                or not spec.origin):
            return
        source = Path(spec.origin).resolve()
        if source in consumed or source in cached_sources or _is_framework_source(source, resolved=True):
            return
        raise SVXInheritanceError(
            f'Python dependency is cached without current '
            f'{"generation" if command == "inheritance-gen" else "discovery"} evidence: {name}; '
            f'rerun {command} in a fresh Python process')

    def certify_import(name, fromlist=()):
        parts = name.split('.')
        for index in range(1, len(parts) + 1):
            certify('.'.join(parts[:index]))
        for member in fromlist or ():
            if isinstance(member, str) and member != '*':
                certify(name + '.' + member)

    def audited_import(name, globals=None, locals=None, fromlist=(), level=0):
        absolute = name
        if level and globals:
            package = globals.get('__package__') or globals.get('__name__', '')
            absolute = importlib.util.resolve_name('.' * level + name, package)
        certify_import(absolute, fromlist)
        result = original_import(name, globals, locals, fromlist, level)
        certify_import(absolute, fromlist)
        return result

    def audited_import_module(name, package=None):
        absolute = importlib.util.resolve_name(name, package) if name.startswith('.') else name
        certify_import(absolute)
        result = original_import_module(name, package)
        certify_import(absolute)
        return result

    class EntryFinder:
        def find_spec(self, fullname, path=None, target=None):
            if fullname not in selected and not selected_paths and not active[0] and not all_sources:
                return None
            spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
            if spec is None or type(spec.loader) is not importlib.machinery.SourceFileLoader:
                return None
            if (fullname not in selected and Path(spec.origin).resolve() not in selected_paths
                    and not active[0] and not all_sources):
                return spec
            spec.loader = _DeclarationSourceLoader(fullname, spec.origin, consumed, active)
            return spec

    finder = EntryFinder()
    # Preserve custom importers ahead of the ordinary filesystem importer.
    index = next((i for i, item in enumerate(sys.meta_path)
                  if item is importlib.machinery.PathFinder), len(sys.meta_path))
    sys.meta_path.insert(index, finder)
    if cached_sources is not None:
        builtins.__import__ = audited_import
        importlib.import_module = audited_import_module
    try:
        yield consumed
    finally:
        if cached_sources is not None:
            builtins.__import__ = original_import
            importlib.import_module = original_import_module
        sys.meta_path.remove(finder)


def _cmd_inheritance_manifest(args: argparse.Namespace, out: TextIO) -> int:
    _sv_macro_config(args)
    from .sv_library_search import library_search
    with library_search(args._sv_build_configuration):
        return _discover_inheritance_manifest(args, out)


def _discover_inheritance_manifest(args: argparse.Namespace, out: TextIO) -> int:
    macro_config = _sv_macro_config(args)
    python_dependencies = _python_source_dependencies(args)
    target = Path(args.out)
    if not target.name:
        raise SVXInheritanceError(f'generated manifest target requires a filename: {target}')
    evidence = target.with_name(target.name + '.svx-discovery.json')
    retained = {}
    if target.is_file():
        try:
            previous = json.loads(target.read_text(encoding='utf-8'))
            paths = validate_discovery_provenance(previous, target) if isinstance(previous, dict) else ()
        except (OSError, ValueError, SVXInheritanceError):
            paths = ()
        cached = {Path(module.__file__).resolve() for module in tuple(sys.modules.values())
                  if getattr(module, '__file__', None)}
        retained = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in paths[1:] if path in cached and not _is_framework_source(path)}
    for name in args.python_module:
        module = sys.modules.get(name)
        source = getattr(module, '__file__', None)
        if source and Path(source).resolve() not in retained:
            raise SVXInheritanceError(
                f'Python declaration module is cached without current discovery evidence: {name}; '
                'rerun inheritance-manifest in a fresh Python process')
    with _fresh_declaration_entries(args.python_module, python_dependencies, all_sources=True,
                                    cached_sources=retained) as consumed:
        fingerprints = _manifest_input_fingerprints(args)
        modules = [importlib.import_module(name) for name in args.python_module]
        manifest = manifest_from_declarations(
            python_modules=modules,
            sv_declaration_files=[Path(item) for item in args.sv_declarations],
            sv_source_files=[Path(item) for item in args.sv_source],
            **macro_config,
        )
        data = manifest_dict(manifest)
        data['discovery_provenance'] = {'schema_version': '1.0.0', 'path': evidence.name}
        text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    protected_inputs = {
        *consumed,
        *(Path(path).resolve() for path in args.sv_declarations),
        *_sv_source_dependencies(args),
        *args._sv_build_configuration.inputs,
        *(Path(item['path']) for item in fingerprints['python_sources']),
        *(Path(module.__file__).resolve() for module in modules if getattr(module, "__file__", None)),
        *retained,
    }
    if not args.check:
        _protect_generation_inputs([target, evidence], protected_inputs)
        validate_output_path(target)
        validate_output_path(evidence)
        if evidence.is_file():
            try:
                old_record = json.loads(evidence.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                old_record = None
            if (not isinstance(old_record, dict)
                    or set(old_record) != {'schema_version', 'contract_sha256', 'sources', 'configuration'}
                    or old_record.get('schema_version') != '1.0.0'):
                raise SVXInheritanceError(f'refusing to overwrite non-generated discovery record {evidence}')
    try:
        current = _manifest_input_fingerprints(args)
        changed_imports = _changed_consumed_sources(consumed)
        changed_imports.extend(_changed_consumed_sources(
            {path: {digest} for path, digest in retained.items()}))
    except (OSError, SVXInheritanceError) as error:
        raise SVXInheritanceError(
            'manifest inputs could not be revalidated; no generated manifest was written. '
            'Retry after the declaration inputs are stable.'
        ) from error
    if current != fingerprints or changed_imports:
        changed = ', '.join(key for key in sorted(current.keys() | fingerprints.keys())
                            if current.get(key) != fingerprints.get(key))
        if changed_imports:
            changed = ', '.join(filter(None, [changed, 'imported sources: ' + ', '.join(changed_imports)]))
        raise SVXInheritanceError(
            f'manifest inputs changed during discovery ({changed}); no generated manifest was written. '
            'Retry after the declaration inputs are stable.'
        )
    sources = dict(retained)
    for category in ('sv_declarations', 'sv_dependencies', 'python_sources', 'python_modules', 'sv_build_inputs'):
        for item in fingerprints[category]:
            if 'path' in item:
                sources[Path(item['path']).resolve()] = item['sha256']
    sources.update({path: next(iter(digests)) for path, digests in consumed.items()
                    if not _is_framework_source(path)})
    if not sources:
        raise SVXInheritanceError('cannot record discovery without file-backed inputs')
    root = target.resolve().parent
    relative = lambda path: Path(os.path.relpath(Path(path).resolve(), root)).as_posix()
    configuration = {
        'python_modules': list(args.python_module),
        'python_selections': sorted([
            {'module': name, 'path': relative(spec.origin)}
            for name, module in tuple(sys.modules.items())
            if (spec := getattr(module, '__spec__', None)) is not None
            and isinstance(spec.loader, importlib.machinery.SourceFileLoader)
            and spec.origin and Path(spec.origin).resolve() in sources
            and not _is_framework_source(Path(spec.origin).resolve())
        ], key=lambda item: item['module']),
        'python_sources': sorted(relative(path) for path in python_dependencies),
        'sv_declarations': [relative(path) for path in args.sv_declarations],
        'sv_sources': [relative(path) for path in args.sv_source],
        'sv_dependencies': [relative(item['path']) for item in fingerprints['sv_dependencies']],
        'sv_predefines': dict(sorted(macro_config['sv_predefines'].items())),
        'sv_undefines': sorted(set(macro_config['sv_undefines'])),
        'sv_include_dirs': [relative(path) for path in macro_config['sv_include_dirs']],
        'source_mode': 'shared-compilation-unit' if macro_config['sv_compilation_unit'] else 'separate-parse-inputs',
    }
    if build_record := _sv_build_record(args, root):
        configuration['sv_build'] = build_record
    ancestors = {'.'.join(item['module'].split('.')[:index])
                 for item in configuration['python_selections']
                 for index in range(1, len(item['module'].split('.')))}
    configuration['python_namespaces'] = [
        {'module': name, 'paths': list(dict.fromkeys(
            relative(path) for path in spec.submodule_search_locations))}
        for name in sorted(ancestors)
        if (spec := getattr(sys.modules.get(name), '__spec__', None)) is not None
        and isinstance(spec.loader, importlib.machinery.NamespaceLoader)
    ]
    record = {'schema_version': '1.0.0', 'contract_sha256': discovery_contract_digest(data),
              'configuration': configuration,
              'sources': [{'path': relative(path), 'sha256': digest}
                          for path, digest in sorted(sources.items())]}
    _validate_python_selections(configuration, root, set(sources))
    record_text = json.dumps(record, indent=2, sort_keys=True) + '\n'
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            raise SystemExit(f"generated inheritance manifest is stale: {target}")
        if not evidence.is_file() or evidence.read_text(encoding='utf-8') != record_text:
            raise SystemExit(
                f'discovery provenance is stale: {evidence}; rerun inheritance-manifest; '
                'matching manifest and bridge files retain their timestamps')
    else:
        write_text_atomic_group({evidence: record_text, target: text})
    print(target, file=out)
    return 0


def _add_sv_macro_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--sv-filelist', action='append', default=[], metavar='FILE',
                        help='import an original -f filelist (paths relative to build directory)')
    parser.add_argument('--sv-relative-filelist', action='append', default=[], metavar='FILE',
                        help='import an original -F filelist (contents relative to filelist directory)')
    parser.add_argument('--sv-build-command', action='append', default=[], metavar='JSON',
                        help='import original compiler argv: JSON with directory and arguments')
    parser.add_argument('--sv-build-directory', metavar='DIRECTORY',
                        help='original working directory for -f filelists; default current directory')
    parser.add_argument("--sv-include-dir", action="append", default=[], metavar="DIRECTORY",
                        help="SV include search directory; repeat in compiler search order")
    parser.add_argument("--sv-compilation-unit", action="store_true",
                        help="parse ordered --sv-source files as one shared compilation unit")
    parser.add_argument("--sv-define", action="append", default=[], metavar="NAME[=VALUE]",
                        help="initial SV macro definition; repeat for multiple names")
    parser.add_argument("--sv-undefine", action="append", default=[], metavar="NAME",
                        help="remove an initial SV macro definition; overrides --sv-define")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m svx")
    parser.add_argument("--debug", action="store_true", help="show tracebacks for expected command errors")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser('compile-config', help='inspect imported original SV build inputs without executing them')
    _add_sv_macro_arguments(p)
    p.add_argument('--sv-source', action='append', default=[])
    p.add_argument('--out')
    p.set_defaults(func=_cmd_compile_config)

    p = sub.add_parser("share", help="print the SVX SystemVerilog support directory")
    p.set_defaults(func=_cmd_share)

    p = sub.add_parser("native-source", help="print the installed native build source directory")
    p.set_defaults(func=_cmd_native_source)

    p = sub.add_parser("sv-files", help="print required core SystemVerilog files")
    p.set_defaults(func=_cmd_sv_files)

    p = sub.add_parser("libs", help="print the SVX runtime library path")
    p.set_defaults(func=_cmd_libs)

    p = sub.add_parser("compile-flags", help="print SVX include paths and source files")
    p.set_defaults(func=_cmd_compile_flags)

    p = sub.add_parser("svtypes-gen", help="generate SystemVerilog from SvTypes Python modules")
    p.add_argument("--module", action="append", required=True, help="Python module containing SvTypes declarations")
    p.add_argument("--types", action="append", help="comma-separated class names to generate")
    p.add_argument("--package", help="optional SystemVerilog package name")
    p.add_argument("--channel-helpers", action="store_true", help="emit SystemVerilog typed channel helper tasks")
    p.add_argument("--out", help="output file; stdout if omitted")
    p.set_defaults(func=_cmd_svtypes_gen)

    p = sub.add_parser("inheritance-gen", help="generate cross-language inheritance mirrors")
    _add_sv_macro_arguments(p)
    p.add_argument("--python-source", action="append", default=[], metavar="FILE",
                   help="Python source input to fingerprint and protect; repeat for explicit dependencies")
    p.add_argument("--manifest", required=True, help="versioned JSON inheritance manifest")
    p.add_argument(
        "--sv-source",
        action="append",
        default=[],
        help="SystemVerilog input for interface analysis or integrated source output",
    )
    p.add_argument("--python-out", help="directory for generated Python SV mirrors")
    p.add_argument("--sv-out", help="output file for generated SystemVerilog Python mirrors")
    p.add_argument(
        "--sv-stage-dir",
        help="directory for source-order SystemVerilog projection includes",
    )
    p.add_argument('--sv-integrated-dir',
                   help='directory for an integrated copy of ordered SV sources and generated bridges')
    p.add_argument(
        "--artifact-manifest",
        help="output compatibility manifest for all generated artifacts",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="verify generated outputs are current without modifying them",
    )
    p.set_defaults(func=_cmd_inheritance_gen)

    p = sub.add_parser(
        "inheritance-migrate",
        help="migrate an inheritance manifest to the current declarative schema",
    )
    p.add_argument("--manifest", required=True, help="input inheritance manifest")
    p.add_argument("--out", help="output file; stdout if omitted")
    p.set_defaults(func=_cmd_inheritance_migrate)

    p = sub.add_parser(
        "inheritance-manifest",
        help="normalize Python and SV declarations to an inheritance manifest",
    )
    p.add_argument("--python-module", action="append", default=[], help="module containing decorated Python-owned classes")
    p.add_argument("--python-source", action="append", default=[], metavar="FILE",
                   help="additional Python input to fingerprint and protect during discovery; not imported by this option")
    _add_sv_macro_arguments(p)
    p.add_argument("--sv-declarations", action="append", default=[], help="versioned SV declaration metadata JSON")
    p.add_argument(
        "--sv-source",
        action="append",
        default=[],
        help="SystemVerilog package source validated with the optional pyslang frontend",
    )
    p.add_argument("--out", required=True, help="output inheritance manifest")
    p.add_argument("--check", action="store_true", help="verify the output is current")
    p.set_defaults(func=_cmd_inheritance_manifest)

    return parser


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args, out)


def entrypoint(argv: list[str] | None = None) -> int:
    """Present expected command errors without hiding unexpected failures."""

    args = build_parser().parse_args(argv)
    try:
        return args.func(args, sys.stdout)
    except (SVXError, OSError) as error:
        if args.debug:
            raise
        print(f"svx: error: {error}", file=sys.stderr)
        return 2
