"""ayka — 4ayka-kit command line."""
import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .scaffold import TEMPLATES
from .version import bump_version, current_version

VERSION_RE_BODY = (
    "ayka-kit: Python console for building FastAPI apps from spec.yaml.\n"
    "  ayka new fastapi <name>   scaffold a spec + run.bat project\n"
    "  ayka new game <title>     scaffold an HTML5 canvas game skeleton\n"
    "  ayka gen [-s spec.yaml]   generate app/ from spec.yaml\n"
    "  ayka ctx [DIR] [--ai]     scan a project and dump its context (for AI agents)\n"
    "  ayka version show|bump    show this package or bump its version"
)


def cmd_version(args) -> int:
    if args.action == "show":
        print(f"ayka-kit {__version__}")
        return 0
    if args.action == "bump":
        new = bump_version(args.part)
        print(f"ayka-kit {__version__} -> {new}")
        return 0
    print(VERSION_RE_BODY)
    return 0


def cmd_gen(args) -> int:
    from .generator import generate, load_spec

    spec_path = Path(args.spec)
    if not spec_path.is_file():
        print(f"spec not found: {spec_path}", file=sys.stderr)
        return 1
    spec = load_spec(spec_path)
    target = Path(args.target) or spec_path.parent
    written = generate(spec, target)
    print(f"generated {len(written)} files for '{spec.name}' in {target}")
    return 0


def cmd_new(args) -> int:
    name = args.name
    target = Path(args.target) or Path(name)
    if args.template not in TEMPLATES:
        print(f"unknown template '{args.template}'. Available: {', '.join(TEMPLATES)}", file=sys.stderr)
        return 1
    label, fn = TEMPLATES[args.template]
    try:
        files = fn(name, target)
    except FileExistsError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"created {len(files)} files under {target}")
    for f in files:
        print("  " + f)
    if args.template == "fastapi":
        print("\nNext: cd into the project and run:  ayka gen   (then: python run.py)")
    return 0


def cmd_ctx(args) -> int:
    from .scanner import render_ai, render_structure, scan

    root = Path(args.dir) if args.dir else Path.cwd()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 1
    ctx = scan(root)
    body = render_ai(ctx) if args.ai else render_structure(ctx)
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"context written to {args.out}")
    else:
        print(body)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ayka", description=VERSION_RE_BODY)
    parser.add_argument("--version", action="version", version=f"ayka-kit {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    p_ver = sub.add_parser("version", help="show or bump ayka-kit version")
    ver_action = p_ver.add_subparsers(dest="action")
    p_show = ver_action.add_parser("show")
    p_bump = ver_action.add_parser("bump")
    p_bump.add_argument("part", choices=["patch", "minor", "major"])

    p_gen = sub.add_parser("gen", help="generate app/ from spec.yaml")
    p_gen.add_argument("-s", "--spec", default="spec.yaml", help="path to spec.yaml")
    p_gen.add_argument("-t", "--target", default="", help="output dir (default: spec dir)")

    p_new = sub.add_parser("new", help="scaffold a starter project")
    p_new.add_argument("template", choices=list(TEMPLATES))
    p_new.add_argument("name", help="project name/title")
    p_new.add_argument("-t", "--target", default="", help="target dir (default: ./<name>)")

    p_ctx = sub.add_parser("ctx", help="dump project context for AI agents")
    p_ctx.add_argument("dir", nargs="?", default="", help="directory to scan (default: cwd)")
    p_ctx.add_argument("--ai", action="store_true", help="compact AI-oriented output")
    p_ctx.add_argument("--out", default="", help="write to file instead of stdout")

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "version":
        return cmd_version(args)
    if args.cmd == "gen":
        return cmd_gen(args)
    if args.cmd == "new":
        return cmd_new(args)
    if args.cmd == "ctx":
        return cmd_ctx(args)
    build_parser().print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())