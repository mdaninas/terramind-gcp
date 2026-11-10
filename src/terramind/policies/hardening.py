"""Optional storage and database hardening checks over closed projected facts."""

from terramind.schemas.normalized import Change, ResourceType
from terramind.schemas.report import Finding


def storage(change: Change) -> tuple[Finding, ...]:
    if change.type != ResourceType.BUCKET or not {"create", "update"}.intersection(change.actions):
        return ()
    attrs = change.attributes
    findings = []
    if (
        attrs.uniform_bucket_level_access is False
        and attrs.newly_disabled_uniform_access is not False
    ):
        findings.append(
            Finding(
                rule_id="TM-GCP-005",
                resource=change.address,
                severity="MEDIUM",
                title="Uniform bucket-level access is disabled",
                rationale="Object ACLs can participate in access control when uniform bucket-level "
                "access is disabled. This setting alone does not establish public access.",
                evidence=(
                    "uniform_bucket_level_access=false",
                    f"newly_disabled={attrs.newly_disabled_uniform_access}",
                ),
                remediation="Enable uniform bucket-level access after reviewing existing "
                "ACL dependencies.",
                status="REVIEW" if attrs.newly_disabled_uniform_access is None else "FAIL",
            )
        )
    if (
        attrs.public_access_prevention == "inherited"
        and attrs.newly_inherited_prevention is not False
    ):
        findings.append(
            Finding(
                rule_id="TM-GCP-006",
                resource=change.address,
                severity="MEDIUM",
                title="Bucket public access prevention depends on inherited policy",
                rationale="The bucket does not explicitly enforce public access prevention. "
                "An organization policy may still enforce it; public exposure is not established.",
                evidence=(
                    "public_access_prevention=inherited",
                    f"newly_inherited={attrs.newly_inherited_prevention}",
                ),
                remediation="Enforce bucket public access prevention or verify and document "
                "the inherited organization policy.",
                status="REVIEW",
            )
        )
    return tuple(findings)


def database(change: Change) -> tuple[Finding, ...]:
    if change.type != ResourceType.SQL or not {"create", "update"}.intersection(change.actions):
        return ()
    attrs = change.attributes
    findings = []
    if (
        attrs.ipv4_enabled is True
        and attrs.world_authorized_network is True
        and attrs.newly_world_accessible is not False
    ):
        findings.append(
            Finding(
                rule_id="TM-GCP-007",
                resource=change.address,
                severity="HIGH",
                title="Cloud SQL public IPv4 authorizes a world source range",
                rationale="The proposed public IPv4 configuration authorizes 0.0.0.0/0. "
                "Database authentication and actual deployed reachability are not "
                "established by this plan.",
                evidence=(
                    "ipv4_enabled=true",
                    "authorized_network=0.0.0.0/0",
                    f"newly_enabled={attrs.newly_world_accessible}",
                ),
                remediation="Remove the world authorized network; prefer private connectivity "
                "or restrict approved direct-client source ranges.",
                status="REVIEW" if attrs.newly_world_accessible is None else "FAIL",
            )
        )
    if attrs.ssl_mode == "ALLOW_UNENCRYPTED_AND_ENCRYPTED" and attrs.newly_unencrypted is not False:
        findings.append(
            Finding(
                rule_id="TM-GCP-008",
                resource=change.address,
                severity="MEDIUM",
                title="Cloud SQL permits unencrypted connections",
                rationale="The explicit SSL mode permits unencrypted direct database connections. "
                "This is a configuration finding, not evidence that a client sent "
                "unencrypted traffic.",
                evidence=(
                    "ssl_mode=ALLOW_UNENCRYPTED_AND_ENCRYPTED",
                    f"newly_unencrypted={attrs.newly_unencrypted}",
                ),
                remediation="Require ENCRYPTED_ONLY or TRUSTED_CLIENT_CERTIFICATE_REQUIRED "
                "where supported, and verify client compatibility before rollout.",
                status="REVIEW" if attrs.newly_unencrypted is None else "FAIL",
            )
        )
    return tuple(findings)
