#!/usr/bin/env python3
"""Validate Helm chart renders ingress TLS and Qdrant PVC (helm CLI or static fallback)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

CHART = Path(__file__).resolve().parents[1] / "helm" / "opencivic"
REQUIRED_STATIC = (
    ("templates/ingress.yaml", "secretName: {{ .Values.ingress.tlsSecret }}"),
    ("templates/qdrant.yaml", "kind: StatefulSet"),
    ("templates/qdrant.yaml", "volumeClaimTemplates:"),
    ("templates/pgbackrest-backup.yaml", "kind: CronJob"),
    ("templates/pgbackrest-verify.yaml", "pgbackrest verify"),
    ("templates/pgbackrest-configmap.yaml", "pgbackrest.conf"),
)
REQUIRED_RENDERED = (
    "kind: Ingress",
    "secretName: opencivic-tls",
    "kind: StatefulSet",
    "volumeClaimTemplates:",
    "opencivic-smoke-opencivic-pgbackrest-backup",
    "opencivic-smoke-opencivic-pgbackrest-verify",
    "pgbackrest-config",
)


def _static_checks() -> list[str]:
    missing: list[str] = []
    for rel_path, snippet in REQUIRED_STATIC:
        content = (CHART / rel_path).read_text(encoding="utf-8")
        if snippet not in content:
            missing.append(f"{rel_path}: {snippet}")
    return missing


def _helm_render() -> tuple[int, str]:
    helm = shutil.which("helm")
    if helm is None:
        return 127, ""
    result = subprocess.run(
        [
            helm,
            "template",
            "opencivic-smoke",
            str(CHART),
            "--set",
            "ingress.enabled=true",
            "--set",
            "ingress.tls=true",
            "--set",
            "postgres.backup.enabled=true",
            "--set",
            "postgres.backup.verify.enabled=true",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout if result.returncode == 0 else result.stderr


def main() -> int:
    missing_static = _static_checks()
    if missing_static:
        print("helm_smoke_failed static:", ", ".join(missing_static), file=sys.stderr)
        return 1

    code, rendered = _helm_render()
    if code == 127:
        print("helm_smoke_ok static")
        return 0
    if code != 0:
        print(rendered, file=sys.stderr)
        return code

    missing_rendered = [snippet for snippet in REQUIRED_RENDERED if snippet not in rendered]
    if missing_rendered:
        print("helm_smoke_failed render:", ", ".join(missing_rendered), file=sys.stderr)
        return 1

    print("helm_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
