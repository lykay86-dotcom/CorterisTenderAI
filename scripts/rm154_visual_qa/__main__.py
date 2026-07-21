"""Command-line entry point for governed RM-154 visual QA."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from .workflow import (  # noqa: E402
    APPROVAL_PHRASE,
    VisualWorkflowError,
    compare_baseline,
    generate_candidate,
    import_candidate,
    validate_baseline,
    validate_candidate,
)
from .environment import RendererEnvironmentError  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    candidate = subparsers.add_parser("candidate")
    candidate.add_argument("--artifact-root", type=Path, required=True)

    compare = subparsers.add_parser("compare")
    compare.add_argument(
        "--baseline-root", type=Path, default=ROOT / "tests" / "visual" / "baselines" / "rm154-v1"
    )
    compare.add_argument("--artifact-root", type=Path, required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("kind", choices=("candidate", "baseline"))
    validate.add_argument("path", type=Path)

    importer = subparsers.add_parser("import")
    importer.add_argument("--candidate-root", type=Path, required=True)
    importer.add_argument(
        "--baseline-root", type=Path, default=ROOT / "tests" / "visual" / "baselines" / "rm154-v1"
    )
    importer.add_argument("--approve", required=True, help=f"must equal {APPROVAL_PHRASE}")
    importer.add_argument("--reviewer", required=True)
    importer.add_argument("--reason", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "candidate":
            result = generate_candidate(root=ROOT, artifact_root=args.artifact_root)
        elif args.command == "compare":
            result = compare_baseline(
                root=ROOT,
                baseline_root=args.baseline_root,
                artifact_root=args.artifact_root,
            )
        elif args.command == "validate":
            result = (
                validate_candidate(args.path)
                if args.kind == "candidate"
                else validate_baseline(args.path)
            )
        else:
            result = import_candidate(
                candidate_root=args.candidate_root,
                baseline_root=args.baseline_root,
                approval=args.approve,
                reviewer=args.reviewer,
                reason=args.reason,
            )
    except (OSError, ValueError, RendererEnvironmentError, VisualWorkflowError) as exc:
        print(json.dumps({"outcome": "BLOCKED_OR_FAILED", "detail": str(exc)}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                "outcome": "PASS",
                "case_count": len(result.get("cases", result.get("results", ()))),
                "renderer_sha256": result.get("renderer_sha256"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
