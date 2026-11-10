import copy
import re
from pathlib import Path

import pytest
import yaml

from scripts.check_deployment_environment import immutable_subject, protected
from scripts.check_runtime import ready


def test_pull_requests_have_no_cloud_privileges():
    ci = yaml.load(Path(".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    assert "pull_request" in ci["on"]
    assert "pull_request_target" not in ci["on"]
    assert ci["permissions"] == {"contents": "read"}
    for job in ci["jobs"].values():
        assert "environment" not in job
        assert "permissions" not in job
        for step in job["steps"]:
            assert "google-github-actions/" not in step.get("uses", "")
    text = Path(".github/workflows/ci.yml").read_text()
    assert "id-token" not in text
    assert "secrets." not in text
    assert "terraform apply" not in text


def test_deployment_requires_trusted_manual_context_and_protected_environment():
    deploy = yaml.load(Path(".github/workflows/deploy.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(deploy["on"]) == {"workflow_dispatch"}
    assert deploy["permissions"] == {"contents": "read"}
    build, delivery = deploy["jobs"]["build"], deploy["jobs"]["deploy"]
    assert "id-token" not in build["permissions"]
    assert delivery["permissions"] == {"contents": "read", "id-token": "write"}
    assert delivery["environment"] == "development"
    assert delivery["needs"] == "build"
    for job in (build, delivery):
        assert "refs/heads/main" in job["if"]
        assert "workflow_dispatch" in job["if"]
    text = Path(".github/workflows/deploy.yml").read_text()
    assert '--image "$IMAGE@$DIGEST"' in text
    assert "terraform apply" not in text
    assert "--allow-unauthenticated" not in text
    assert "workload_identity_provider:" in text


def test_all_actions_are_pinned_to_full_commit_hashes():
    for path in Path(".github/workflows").glob("*.yml"):
        workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        for job in workflow["jobs"].values():
            for step in job["steps"]:
                if "uses" in step:
                    assert re.fullmatch(
                        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[a-f0-9]{40}", step["uses"]
                    )
                if step.get("uses", "").startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] == "false"


def test_extended_advisory_smoke_is_explicit_and_preserves_failed_evidence():
    deploy = yaml.load(Path(".github/workflows/deploy.yml").read_text(), Loader=yaml.BaseLoader)
    option = deploy["on"]["workflow_dispatch"]["inputs"]["verify_policy_packs"]
    assert option["type"] == "boolean" and option["default"] == "false"
    steps = deploy["jobs"]["deploy"]["steps"]
    smoke = next(step for step in steps if step.get("name") == "Verify private analysis end to end")
    assert "--require-advisory" in smoke["run"] and "--all-scenarios" in smoke["run"]
    assert "continue-on-error" not in smoke and "retry" not in smoke["run"]
    artifact = next(
        step for step in steps if step.get("name") == "Retain content-free verification results"
    )
    assert artifact["if"] == "always()"
    assert artifact["with"]["path"] == "artifacts/api-demo-summary.json"
    assert artifact["with"]["retention-days"] == "1"


def protection():
    return (
        {
            "protection_rules": [{"type": "required_reviewers", "reviewers": [{"type": "User"}]}],
            "deployment_branch_policy": {
                "custom_branch_policies": True,
                "protected_branches": False,
            },
        },
        {"total_count": 1, "branch_policies": [{"name": "main", "type": "branch"}]},
    )


@pytest.mark.parametrize(
    "change", ["none", "no-review", "wildcard", "tag", "extra", "protected-only"]
)
def test_environment_guard_rejects_unprotected_or_broad_access(change):
    environment, branches = protection()
    if change == "no-review":
        environment["protection_rules"] = []
    elif change == "wildcard":
        branches["branch_policies"][0]["name"] = "*"
    elif change == "tag":
        branches["branch_policies"][0]["type"] = "tag"
    elif change == "extra":
        branches["total_count"] = 2
    elif change == "protected-only":
        environment["deployment_branch_policy"] = {"protected_branches": True}
    assert protected(environment, branches) == (change == "none")


@pytest.mark.parametrize("change", ["none", "legacy", "custom", "owner", "repository", "name"])
def test_immutable_subject_guard_requires_exact_default_identity(change):
    configuration = {
        "use_default": True,
        "use_immutable_subject": True,
        "sub_claim_prefix": "repo:synthetic@987654321/terramind@123456789",
    }
    if change == "legacy":
        configuration["use_immutable_subject"] = False
    elif change == "custom":
        configuration["use_default"] = False
    elif change == "owner":
        configuration["sub_claim_prefix"] = "repo:synthetic@1/terramind@123456789"
    elif change == "repository":
        configuration["sub_claim_prefix"] = "repo:synthetic@987654321/terramind@1"
    elif change == "name":
        configuration["sub_claim_prefix"] = "repo:synthetic@987654321/other@123456789"
    assert immutable_subject(configuration, "synthetic/terramind", 987654321, 123456789) == (
        change == "none"
    )


def runtime():
    return {
        "metadata": {"name": "terramind-dev", "annotations": {"run.googleapis.com/maxScale": "1"}},
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "autoscaling.knative.dev/maxScale": "1",
                        "run.googleapis.com/cpu-throttling": "true",
                    }
                },
                "spec": {
                    "timeoutSeconds": 30,
                    "containers": [
                        {
                            "env": [
                                {"name": "TERRAMIND_API_MODE", "value": "cloud"},
                                {"name": "GCP_PROJECT_ID", "value": "terramind-demo"},
                                {"name": "REPORT_RETENTION_HOURS", "value": "24"},
                                {"name": "ANALYSES_PER_MINUTE", "value": "6"},
                            ]
                        }
                    ],
                },
            }
        },
        "status": {"url": "https://terramind-synthetic.a.run.app"},
    }


@pytest.mark.parametrize(
    "change", ["none", "public", "auth-disabled", "warm", "scale", "offline", "url"]
)
def test_runtime_guard_requires_private_cost_bounded_cloud_mode(monkeypatch, change):
    for key, value in {
        "GCP_PROJECT_ID": "terramind-demo",
        "GCP_REGION": "us-central1",
        "CLOUD_RUN_SERVICE": "terramind-dev",
        "ARTIFACT_REPOSITORY": "terramind-dev",
        "CLOUD_RUN_URL": "https://terramind-synthetic.a.run.app",
    }.items():
        monkeypatch.setenv(key, value)
    service = copy.deepcopy(runtime())
    iam = {"bindings": []}
    if change == "public":
        iam["bindings"] = [{"members": ["allUsers"]}]
    elif change == "auth-disabled":
        service["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] = "true"
    elif change == "warm":
        service["spec"]["template"]["metadata"]["annotations"][
            "autoscaling.knative.dev/minScale"
        ] = "1"
    elif change == "scale":
        service["metadata"]["annotations"]["run.googleapis.com/maxScale"] = "3"
    elif change == "offline":
        service["spec"]["template"]["spec"]["containers"][0]["env"][0]["value"] = "offline"
    elif change == "url":
        monkeypatch.setenv("CLOUD_RUN_URL", "https://example.invalid")
    assert ready(service, iam) == (change == "none")
