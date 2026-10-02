"""
Herald on the command line.

The same engine the window uses, with no Qt in sight — so it runs on a server,
in a pipe, or inside another script. Point it at an ``.eml`` file or pipe a
message into standard input; add ``--json`` for machine-readable output.

    herald message.eml
    cat message.eml | herald -
    herald message.eml --json
"""

from __future__ import annotations

import argparse
import json
import sys

from .core.grade import analyze
from .core.model import Message

_C = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "good": "\033[32m", "notice": "\033[33m", "warning": "\033[33m",
    "alert": "\033[31m", "info": "\033[90m", "brass": "\033[33m",
}


def _paint(text: str, key: str, color: bool) -> str:
    if not color:
        return text
    return f"{_C.get(key, '')}{text}{_C['reset']}"


def _report_text(msg: Message, color: bool) -> str:
    g = msg.grade
    out: list[str] = []
    out.append(_paint(f"  {g.letter}  ", "bold", color) + f" {g.headline}  "
               + _paint(f"({g.score}/100)", "dim", color))
    out.append(_paint(g.ceiling_note, "dim", color))
    out.append("")

    if msg.from_addr:
        out.append(f"From         {msg.from_addr.rendered}")
    if msg.return_path:
        out.append(f"Return-Path  {msg.return_path.full}")
    if msg.reply_to:
        out.append(f"Reply-To     {msg.reply_to.full}")
    if msg.subject:
        out.append(f"Subject      {msg.subject}")
    out.append("")

    a = msg.auth
    out.append("Authentication (as the receiver reported it)")
    for name, st, dom in (("SPF", a.spf, a.spf_domain),
                          ("DKIM", a.dkim, a.dkim_domain),
                          ("DMARC", a.dmarc, a.dmarc_domain)):
        key = "good" if st.is_good else ("alert" if st.is_bad else "notice")
        line = f"  {name:<6} {_paint(st.value, key, color)}"
        if dom:
            line += _paint(f"  {dom}", "dim", color)
        out.append(line)
    out.append("")

    if msg.hops:
        tt = msg.travel_time_seconds
        extra = f"  ({tt:.0f}s in transit)" if tt else ""
        out.append(f"Itinerary ({len(msg.hops)} hops){extra}")
        for i, h in enumerate(msg.hops):
            mark = "origin" if i == 0 else ("delivered" if i == len(msg.hops) - 1 else "")
            tag = "internal" if h.is_internal else "external"
            delay = f" +{h.delay_seconds:.0f}s" if h.delay_seconds else ""
            host = h.from_host or h.by_host or "unknown"
            out.append(f"  {i + 1}. {host}  [{h.from_ip or '-'}]  {tag}{delay}"
                       + (_paint(f"  {mark}", "brass", color) if mark else ""))
        out.append("")

    out.append(f"Findings ({len(msg.findings)})")
    for f in msg.findings:
        key = f.severity.value
        tag = _paint(f"[{f.severity.value:^7}]", key, color)
        pts = _paint(f" -{f.points}", "dim", color) if f.points else ""
        out.append(f"  {tag} {f.title}{pts}")
        out.append(_paint(f"          {f.detail}", "dim", color))
    for n in msg.parse_notes:
        out.append(_paint(f"  note: {n}", "dim", color))
    return "\n".join(out)


def _report_json(msg: Message) -> str:
    def addr(a):
        return None if a is None else {
            "display": a.display, "local": a.local, "domain": a.domain, "full": a.full}

    data = {
        "grade": {
            "letter": msg.grade.letter, "score": msg.grade.score,
            "headline": msg.grade.headline, "ceiling_note": msg.grade.ceiling_note,
        },
        "subject": msg.subject,
        "from": addr(msg.from_addr),
        "return_path": addr(msg.return_path),
        "reply_to": addr(msg.reply_to),
        "to": [addr(a) for a in msg.to_addrs],
        "authentication": {
            "spf": msg.auth.spf.value, "dkim": msg.auth.dkim.value,
            "dmarc": msg.auth.dmarc.value, "spf_domain": msg.auth.spf_domain,
            "dkim_domain": msg.auth.dkim_domain, "dmarc_domain": msg.auth.dmarc_domain,
            "authserv": msg.auth.authserv,
        },
        "itinerary": [
            {
                "from_host": h.from_host, "from_ip": h.from_ip, "by_host": h.by_host,
                "protocol": h.protocol, "tls": h.with_tls, "internal": h.is_internal,
                "delay_seconds": h.delay_seconds,
                "timestamp": h.timestamp.isoformat() if h.timestamp else None,
            }
            for h in msg.hops
        ],
        "travel_time_seconds": msg.travel_time_seconds,
        "findings": [
            {"severity": f.severity.value, "title": f.title, "detail": f.detail,
             "points": f.points, "category": f.category}
            for f in msg.findings
        ],
        "parse_notes": msg.parse_notes,
    }
    return json.dumps(data, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="herald",
        description="Read an e-mail's headers and grade what they reveal.")
    parser.add_argument("source", nargs="?", default="-",
                        help="path to an .eml file, or - for standard input")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--no-color", action="store_true", help="plain text, no ANSI")
    args = parser.parse_args(argv)

    if args.source == "-":
        raw = sys.stdin.read()
    else:
        try:
            with open(args.source, encoding="utf-8", errors="replace") as fh:
                raw = fh.read()
        except OSError as exc:
            print(f"herald: cannot read {args.source}: {exc}", file=sys.stderr)
            return 2

    if not raw.strip():
        print("herald: no message given", file=sys.stderr)
        return 2

    msg = analyze(raw)
    if args.json:
        print(_report_json(msg))
    else:
        color = sys.stdout.isatty() and not args.no_color
        print(_report_text(msg, color))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
