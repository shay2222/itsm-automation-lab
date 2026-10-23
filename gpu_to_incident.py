#!/usr/bin/env python3
"""
Turn GPU health-check output into ServiceNow incidents.

Accepts the JSON written by either health checker in this portfolio:
  - gpu-ops-portfolio format:  status = OK | WARN | CRIT,  issues = [...]
  - gpu-ops-toolkit format:    status = pass | fail,      problems = [...]

Rules:
  - OK / pass produces nothing.
  - WARN produces an incident with urgency 2, impact 2 (moderate).
  - CRIT / fail produces an incident with urgency 1, impact 1 (high).
  - If an active incident already exists for the same host and GPU, nothing is created.
    The existing number is reported instead, so one failing GPU does not flood the queue.

Usage:
  python3 gpu_to_incident.py sample/gpu_report.json --host dgx-01 --dry-run
  python3 gpu_to_incident.py sample/gpu_report.json --host dgx-01
"""
import argparse
import json
import sys

from snow_client import SnowClient

# severity -> (urgency, impact); ServiceNow derives priority from these two.
SEVERITY_TO_UA = {"warn": ("2", "2"), "crit": ("1", "1")}


def normalize_status(gpu):
    """Map either checker's status vocabulary to 'ok', 'warn', or 'crit'."""
    raw = str(gpu.get("status", "")).strip().lower()
    if raw in ("ok", "pass"):
        return "ok"
    if raw == "warn":
        return "warn"
    if raw in ("crit", "fail"):
        return "crit"
    raise ValueError(f"unknown status {gpu.get('status')!r} for GPU {gpu.get('index')}")


def problems_of(gpu):
    return gpu.get("issues") or gpu.get("problems") or []


def dedup_key(host, gpu):
    return f"[{host}] GPU {gpu['index']} ({gpu['name']})"


def build_payload(host, gpu, severity):
    urgency, impact = SEVERITY_TO_UA[severity]
    details = "\n".join(f"- {p}" for p in problems_of(gpu)) or "- no detail provided"
    return {
        "short_description": f"{dedup_key(host, gpu)} health {severity.upper()}",
        "description": f"Automated report from GPU health check.\n{details}",
        "urgency": urgency,
        "impact": impact,
        "category": "hardware",
    }


def plan_actions(report, host, client):
    """Decide what to do for each GPU. Returns a list of (action, gpu_index, detail)."""
    actions = []
    for gpu in report:
        severity = normalize_status(gpu)
        if severity == "ok":
            actions.append(("skip_ok", gpu["index"], ""))
            continue
        key = dedup_key(host, gpu)
        existing = client.find("incident", f"active=true^short_descriptionSTARTSWITH{key}")
        if existing:
            actions.append(("skip_existing", gpu["index"], existing[0]["number"]))
        else:
            actions.append(("create", gpu["index"], severity))
    return actions


def run(report, host, client, dry_run=False):
    results = []
    for action, index, detail in plan_actions(report, host, client):
        if action == "create" and not dry_run:
            gpu = next(g for g in report if g["index"] == index)
            created = client.create("incident", build_payload(host, gpu, detail))
            results.append(("created", index, created["number"]))
        elif action == "create":
            results.append(("would_create", index, detail))
        else:
            results.append((action, index, detail))
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", help="JSON file from a GPU health checker")
    ap.add_argument("--host", required=True, help="host name used in incident titles")
    ap.add_argument("--dry-run", action="store_true", help="show actions, create nothing")
    args = ap.parse_args(argv)

    with open(args.report) as fh:
        report = json.load(fh)

    import os
    missing = [v for v in ("SNOW_INSTANCE_URL", "SNOW_USER", "SNOW_PASSWORD") if not os.environ.get(v)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}. See README.", file=sys.stderr)
        return 2

    client = SnowClient()
    for action, index, detail in run(report, args.host, client, dry_run=args.dry_run):
        print(f"GPU {index}: {action} {detail}".rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
