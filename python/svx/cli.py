from __future__ import annotations

import argparse
import importlib
import inspect
import os
import sys
import sysconfig
from pathlib import Path
from types import ModuleType
from typing import Iterable, TextIO

from .inheritance import emit_sv_mirrors, load_manifest, write_python_mirrors


def repo_root() -> Path:
    return sv_dir().parent


def sv_dir() -> Path:
    override = os.environ.get("SVX_SHARE_DIR")
    if override:
        path = Path(override).expanduser().resolve()
        if (path / "svx_pkg.sv").is_file():
            return path
        raise RuntimeError(f"SVX_SHARE_DIR does not contain svx_pkg.sv: {path}")

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "sv"
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
    return Path(sysconfig.get_path("platlib"))


def sv_files() -> list[Path]:
    return [svtypes_file(), sv_dir() / "svx_pkg.sv"]


def _print_lines(lines: Iterable[str], out: TextIO) -> None:
    for line in lines:
        print(line, file=out)


def _cmd_share(_args: argparse.Namespace, out: TextIO) -> int:
    print(sv_dir(), file=out)
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
    return "\n".join(
        [
            f"{ind}task automatic svx_get_{type_name}(string channel_name, output {type_name} item);",
            f"{ind1}chandle payload;",
            f"{ind1}byte unsigned bytes[$];",
            f"{ind1}int offset;",
            f"{ind1}svx_pkg::svx_channel_get_payload(channel_name, payload);",
            f'{ind1}svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "{type_name}", "svx_get_{type_name}", bytes);',
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
            f'{ind1}svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "{type_name}", "svx_peek_{type_name}", bytes);',
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
            f'{ind1}svx_pkg::svx_channel_put_byte_queue(channel_name, bytes, "svtypes", "{type_name}", "application/x-svtypes");',
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
            f'{ind1}svx_pkg::svx_payload_to_checked_byte_queue(payload, channel_name, "{type_name}", "svx_try_get_{type_name}", bytes);',
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
            f'{ind1}return svx_pkg::svx_channel_try_put_byte_queue(channel_name, bytes, "svtypes", "{type_name}", "application/x-svtypes");',
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
    if args.python_out:
        written = write_python_mirrors(manifest, Path(args.python_out))
        for path in written:
            print(path, file=out)
    sv_text = emit_sv_mirrors(manifest)
    if args.sv_out:
        Path(args.sv_out).write_text(sv_text)
    elif sv_text.strip() != "// Generated by svx inheritance-gen. Do not edit.":
        print(sv_text, end="", file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m svx")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("share", help="print the SVX SystemVerilog support directory")
    p.set_defaults(func=_cmd_share)

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

    p = sub.add_parser("inheritance-gen", help="generate M8 cross-language inheritance mirrors")
    p.add_argument("--manifest", required=True, help="versioned JSON inheritance manifest")
    p.add_argument("--python-out", help="directory for generated Python SV mirrors")
    p.add_argument("--sv-out", help="output file for generated SystemVerilog Python mirrors")
    p.set_defaults(func=_cmd_inheritance_gen)

    return parser


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args, out)
