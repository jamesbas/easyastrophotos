"""Headless CLI for Easy Astro Photos (Phase 6).

Examples:
    python -m app.cli new-project --name "Orion" --target nebula
    python -m app.cli import-frames <project_id> --type light path/to/*.fits
    python -m app.cli stack <project_id> --method sigma_clip --align
    python -m app.cli stretch <project_id> --method asinh
    python -m app.cli run-recipe <project_id> --recipe recipe.json
    python -m app.cli export <project_id> --format png
    python -m app.cli list-projects
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import schemas
from .services import frame_service, job_service, project_service, recipe_service


def _print(obj) -> None:
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    print(json.dumps(obj, indent=2, default=str))


def cmd_list_projects(args) -> int:
    _print([p.model_dump() for p in project_service.list_projects()])
    return 0


def cmd_new_project(args) -> int:
    p = project_service.create_project(args.name, args.target)
    _print(p)
    return 0


def cmd_import_frames(args) -> int:
    paths = [Path(p) for pat in args.paths for p in _expand(pat)]
    out = []
    for src in paths:
        try:
            f = frame_service.import_frame(args.project_id, src, src.name, args.type)
            out.append(f.model_dump())
        except Exception as exc:
            print(f"skip {src}: {exc}", file=sys.stderr)
    _print(out)
    return 0


def _expand(pattern: str):
    p = Path(pattern)
    if any(ch in pattern for ch in "*?["):
        parent = p.parent if str(p.parent) else Path(".")
        yield from sorted(parent.glob(p.name))
    else:
        yield p


def cmd_stack(args) -> int:
    opts = schemas.StackOptions(
        method=args.method,
        align=args.align,
        weighting=args.weighting,
        calibrate=args.calibrate,
    )
    _print(job_service.stack_project(args.project_id, opts))
    return 0


def cmd_stretch(args) -> int:
    opts = schemas.StretchOptions(method=args.method)
    _print(job_service.stretch_current(args.project_id, opts))
    return 0


def cmd_export(args) -> int:
    path = job_service.export_image(args.project_id, args.format)
    _print({"path": str(path)})
    return 0


def cmd_run_recipe(args) -> int:
    data = json.loads(Path(args.recipe).read_text(encoding="utf-8"))
    steps = data.get("steps", data) if isinstance(data, dict) else data
    recipe_service.save_recipe(args.project_id, {"project_id": args.project_id, "steps": steps})
    _print(job_service.replay_recipe(args.project_id))
    return 0


def cmd_dump_recipe(args) -> int:
    _print(recipe_service.load_recipe(args.project_id))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="eap")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-projects").set_defaults(func=cmd_list_projects)

    p = sub.add_parser("new-project")
    p.add_argument("--name", required=True)
    p.add_argument("--target", default="unknown")
    p.set_defaults(func=cmd_new_project)

    p = sub.add_parser("import-frames")
    p.add_argument("project_id")
    p.add_argument("--type", default="light", choices=["light", "dark", "flat", "bias", "flat_dark"])
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=cmd_import_frames)

    p = sub.add_parser("stack")
    p.add_argument("project_id")
    p.add_argument("--method", default="average")
    p.add_argument("--weighting", default="equal")
    p.add_argument("--align", action="store_true", default=True)
    p.add_argument("--no-align", dest="align", action="store_false")
    p.add_argument("--calibrate", action="store_true", default=False)
    p.set_defaults(func=cmd_stack)

    p = sub.add_parser("stretch")
    p.add_argument("project_id")
    p.add_argument("--method", default="asinh")
    p.set_defaults(func=cmd_stretch)

    p = sub.add_parser("export")
    p.add_argument("project_id")
    p.add_argument("--format", default="png")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("run-recipe")
    p.add_argument("project_id")
    p.add_argument("--recipe", required=True)
    p.set_defaults(func=cmd_run_recipe)

    p = sub.add_parser("dump-recipe")
    p.add_argument("project_id")
    p.set_defaults(func=cmd_dump_recipe)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
