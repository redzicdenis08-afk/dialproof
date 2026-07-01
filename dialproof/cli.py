"""Command-line interface.

::

    dialproof audit <file-or-dir> [...] [--json] [--checks a,b] [--fail-under N]
    dialproof report <file-or-dir> [...] [--json]

``audit`` prints per-call detail with receipts; ``report`` prints the
aggregate roll-up. Both read the same inputs (JSON or plain-text transcripts,
files or directories) and both support ``--json`` for machine consumption.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from dialproof import __version__
from dialproof.auditor import Auditor
from dialproof.checks import CHECKS, AuditConfig
from dialproof.parser import ParseError
from dialproof.report import AggregateReport, render_call_text, render_summary_text

EXIT_OK = 0
EXIT_FAIL_UNDER = 1
EXIT_ERROR = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dialproof",
        description="Receipt-backed QA audits for AI voice-agent call transcripts.",
    )
    parser.add_argument("--version", action="version", version=f"dialproof {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("paths", nargs="+", help="transcript files or directories (.json / .txt)")
    common.add_argument("--json", action="store_true", help="emit JSON instead of text")
    common.add_argument(
        "--checks",
        default=None,
        metavar="NAMES",
        help=f"comma-separated subset of checks (available: {', '.join(sorted(CHECKS))})",
    )
    common.add_argument(
        "--forbidden",
        action="append",
        default=None,
        metavar="PHRASE",
        help="extra forbidden phrase (repeatable); replaces nothing, adds to defaults",
    )
    common.add_argument(
        "--dead-air",
        type=float,
        default=None,
        metavar="SECONDS",
        help="dead-air threshold in seconds (default 6.0)",
    )

    audit_p = sub.add_parser(
        "audit", parents=[common], help="audit calls and print findings with receipts"
    )
    audit_p.add_argument(
        "--fail-under",
        type=int,
        default=None,
        metavar="SCORE",
        help="exit non-zero if any call scores below this (CI-friendly)",
    )

    sub.add_parser("report", parents=[common], help="aggregate roll-up across calls")
    return parser


def _make_auditor(args: argparse.Namespace) -> Auditor:
    config = AuditConfig()
    if args.forbidden:
        config.forbidden_phrases = tuple(config.forbidden_phrases) + tuple(args.forbidden)
    if args.dead_air is not None:
        config.dead_air_seconds = args.dead_air
    checks = [c.strip() for c in args.checks.split(",") if c.strip()] if args.checks else None
    return Auditor(config=config, checks=checks)


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        auditor = _make_auditor(args)
        audits = auditor.audit_paths(args.paths)
    except (FileNotFoundError, ParseError, KeyError, ValueError) as exc:
        print(f"dialproof: error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not audits:
        print("dialproof: error: no transcript files found", file=sys.stderr)
        return EXIT_ERROR

    report = AggregateReport(audits)

    if args.command == "audit":
        if args.json:
            print(json.dumps([a.to_dict() for a in audits], indent=2))
        else:
            print("\n\n".join(render_call_text(a) for a in audits))
            print()
            print(render_summary_text(report))
        if args.fail_under is not None:
            worst = min(a.score for a in audits)
            if worst < args.fail_under:
                print(
                    f"dialproof: fail-under: lowest score {worst} < {args.fail_under}",
                    file=sys.stderr,
                )
                return EXIT_FAIL_UNDER
        return EXIT_OK

    # report
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_summary_text(report))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
