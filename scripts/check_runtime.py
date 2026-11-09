"""Read-only Cloud Run preflight; deployment does not repair IAM or configuration."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def ready(service: dict[str, Any], iam: dict[str, Any]) -> bool:
    # gcloud run services describe emits the Knative v1 representation.
    spec = service.get("spec", {})
    template = spec.get("template", {}).get("spec", {})
    metadata = service.get("metadata", {}).get("annotations", {})
    revision = spec.get("template", {}).get("metadata", {}).get("annotations", {})
    containers = template.get("containers", [])
    if len(containers) != 1:
        return False
    environment = {item.get("name"): item.get("value") for item in containers[0].get("env", [])}
    project = os.environ.get("GCP_PROJECT_ID", "")
    region = os.environ.get("GCP_REGION", "")
    name = os.environ.get("CLOUD_RUN_SERVICE", "")
    repository = os.environ.get("ARTIFACT_REPOSITORY", "")
    url = os.environ.get("CLOUD_RUN_URL", "")
    return bool(
        re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project)
        and re.fullmatch(r"[a-z]+[0-9]?-?[a-z0-9-]*[0-9]", region)
        and re.fullmatch(r"[a-z][a-z0-9-]{2,61}", name)
        and re.fullmatch(r"[a-z][a-z0-9-]{2,61}", repository)
        and re.fullmatch(r"https://[a-z0-9-]+\.a\.run\.app", url)
        and service.get("status", {}).get("url") == url
        and service.get("metadata", {}).get("name") == name
        and metadata.get("run.googleapis.com/invoker-iam-disabled", "false") == "false"
        and revision.get("autoscaling.knative.dev/minScale", "0") == "0"
        and revision.get("autoscaling.knative.dev/maxScale") == "1"
        and metadata.get("run.googleapis.com/maxScale") == "1"
        and revision.get("run.googleapis.com/cpu-throttling") == "true"
        and template.get("timeoutSeconds") == 30
        and environment.get("TERRAMIND_API_MODE") == "cloud"
        and environment.get("GCP_PROJECT_ID") == project
        and environment.get("REPORT_RETENTION_HOURS") == "24"
        and environment.get("ANALYSES_PER_MINUTE") == "6"
        and not any(
            member in {"allUsers", "allAuthenticatedUsers"}
            for binding in iam.get("bindings", [])
            for member in binding.get("members", [])
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", type=Path, required=True)
    parser.add_argument("--iam", type=Path, required=True)
    args = parser.parse_args()
    try:
        verified = ready(json.loads(args.service.read_bytes()), json.loads(args.iam.read_bytes()))
    except Exception:
        verified = False
    print(
        "Private runtime preflight passed."
        if verified
        else "Deployment blocked: reconcile the approved runtime configuration using Terraform."
    )
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
