from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
import sys
import sysconfig
from pathlib import Path
from types import ModuleType
from typing import Iterable, TextIO

from .inheritance import (
    artifact_manifest,
    emit_python_mirrors,
    emit_sv_mirrors,
    load_manifest,
    migrate_manifest,
    write_text_atomic,
    write_python_mirrors,
)
from .declarations import manifest_dict, manifest_from_declarations


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

    candidate = Path(sysconfig.get_path("data")) / "share" / "svx" / "sv"
    if (candidate / "svx_pkg.sv").is_file():
        return candidate
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "sv"
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
        Path(args.out).write_text(text)
    else:
        print(text, end="", file=out)
    return 0


def _cmd_inheritance_gen(args: argparse.Namespace, out: TextIO) -> int:
    manifest = load_manifest(Path(args.manifest))
    python_sources = emit_python_mirrors(manifest)
    sv_text = emit_sv_mirrors(manifest)
    if args.check:
        if not args.python_out or not args.sv_out or not args.artifact_manifest:
            raise SystemExit(
                "inheritance-gen --check requires --python-out, --sv-out, and --artifact-manifest"
            )
        mismatches: list[Path] = []
        python_targets = [Path(args.python_out) / path for path in python_sources]
        for target, source in zip(python_targets, python_sources.values()):
            if not target.is_file() or target.read_text(encoding="utf-8") != source:
                mismatches.append(target)
        sv_target = Path(args.sv_out)
        if not sv_target.is_file() or sv_target.read_text(encoding="utf-8") != sv_text:
            mismatches.append(sv_target)
        artifact_target = Path(args.artifact_manifest)
        artifact_text = _generated_artifact_text(
            manifest, python_sources, sv_text, args, artifact_target
        )
        if (
            not artifact_target.is_file()
            or artifact_target.read_text(encoding="utf-8") != artifact_text
        ):
            mismatches.append(artifact_target)
        if mismatches:
            raise SystemExit(
                "generated inheritance artifacts are stale: "
                + ", ".join(str(path) for path in mismatches)
            )
        for path in [*python_targets, sv_target, artifact_target]:
            print(path, file=out)
        return 0
    if args.python_out:
        written = write_python_mirrors(manifest, Path(args.python_out))
        for path in written:
            print(path, file=out)
    if args.sv_out:
        write_text_atomic(Path(args.sv_out), sv_text)
    elif sv_text.strip() != "// Generated by svx inheritance-gen. Do not edit.":
        print(sv_text, end="", file=out)
    if args.artifact_manifest:
        artifact_path = Path(args.artifact_manifest)
        write_text_atomic(
            artifact_path,
            _generated_artifact_text(
                manifest, python_sources, sv_text, args, artifact_path
            ),
        )
        print(artifact_path, file=out)
    return 0


def _generated_artifact_text(
    manifest,
    python_sources,
    sv_text: str,
    args: argparse.Namespace,
    artifact_path: Path,
) -> str:
    artifact_root = artifact_path.parent.resolve()
    python_prefix = ""
    if args.python_out:
        python_prefix = os.path.relpath(Path(args.python_out).resolve(), artifact_root)
    sv_path = "mirrors.sv"
    if args.sv_out:
        sv_path = os.path.relpath(Path(args.sv_out).resolve(), artifact_root)
    return (
        json.dumps(
            artifact_manifest(
                manifest,
                python_sources,
                sv_text,
                python_path_prefix=python_prefix,
                sv_path=sv_path,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _cmd_inheritance_migrate(args: argparse.Namespace, out: TextIO) -> int:
    source = Path(args.manifest)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read inheritance manifest {source}: {error}") from error
    migrated = migrate_manifest(data)
    text = json.dumps(migrated, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="", file=out)
    return 0


def _cmd_inheritance_manifest(args: argparse.Namespace, out: TextIO) -> int:
    modules = [importlib.import_module(name) for name in args.python_module]
    manifest = manifest_from_declarations(
        python_modules=modules,
        sv_declaration_files=[Path(item) for item in args.sv_declarations],
        sv_source_files=[Path(item) for item in args.sv_source],
    )
    text = json.dumps(manifest_dict(manifest), indent=2, sort_keys=True) + "\n"
    target = Path(args.out)
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            raise SystemExit(f"generated inheritance manifest is stale: {target}")
    else:
        write_text_atomic(target, text)
    print(target, file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m svx")
    sub = parser.add_subparsers(dest="cmd", required=True)

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
    p.add_argument("--manifest", required=True, help="versioned JSON inheritance manifest")
    p.add_argument("--python-out", help="directory for generated Python SV mirrors")
    p.add_argument("--sv-out", help="output file for generated SystemVerilog Python mirrors")
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
