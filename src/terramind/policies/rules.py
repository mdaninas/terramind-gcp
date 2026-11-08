"""The four MVP rules; functions use only sanitized, observable plan facts."""

from terramind.schemas.normalized import Change, ResourceType
from terramind.schemas.report import Finding

OBJECT_READ_ROLES = frozenset(
    {
        "roles/storage.objectViewer",
        "roles/storage.objectAdmin",
        "roles/storage.admin",
        "roles/storage.objectUser",
        "roles/storage.legacyObjectReader",
    }
)
PERSISTENT = frozenset(
    {
        ResourceType.BUCKET,
        ResourceType.SQL,
        ResourceType.SQL_DATABASE,
        ResourceType.DISK,
        ResourceType.REGION_DISK,
        ResourceType.FIRESTORE,
        ResourceType.BIGTABLE,
        ResourceType.SPANNER,
        ResourceType.SPANNER_DATABASE,
        ResourceType.FILESTORE,
    }
)


def _proposed(change: Change) -> bool:
    return "create" in change.actions or "update" in change.actions


def public_bucket(change: Change) -> tuple[Finding, ...]:
    if not change.type.startswith("google_storage_bucket_iam_") or not _proposed(change):
        return ()
    grants = tuple(
        grant
        for grant in change.attributes.grants
        if grant.principal in ("allUsers", "allAuthenticatedUsers")
        and grant.role in OBJECT_READ_ROLES
        and grant.newly_granted is not False
    )
    if not grants:
        return ()
    enforced = change.attributes.public_access_prevention == "enforced"
    conditional = "conditional_iam" in change.notes or any(
        grant.newly_granted is None for grant in grants
    )
    evidence = tuple(sorted({f"{grant.role} -> {grant.principal}" for grant in grants}))
    return (
        Finding(
            rule_id="TM-GCP-001",
            resource=change.address,
            title="Proposed public Cloud Storage object-read grant",
            rationale=(
                "Verified planned public access prevention blocks this public grant; "
                "review the intent."
                if enforced
                else "Public principals receive object-read permissions; exposure depends on "
                "prevention policies and any IAM conditions."
            ),
            evidence=(
                *evidence,
                f"public_access_prevention={change.attributes.public_access_prevention}",
            ),
            remediation="Remove public principals; use scoped identities and enforce "
            "public access prevention.",
            status="REVIEW" if enforced or conditional else "FAIL",
        ),
    )


def _includes(ports: tuple[str, ...], target: int) -> bool:
    # In an explicit protocol allow entry, omitted ports mean all ports.
    if not ports:
        return True
    for port in ports:
        parts = [int(value) for value in port.split("-")]
        if parts[0] <= target <= parts[-1]:
            return True
    return False


def open_admin_ports(change: Change) -> tuple[Finding, ...]:
    attrs = change.attributes
    if (
        change.type != ResourceType.FIREWALL
        or not _proposed(change)
        or attrs.direction != "INGRESS"
        or attrs.disabled is not False
        or not attrs.source_ranges
    ):
        return ()
    exposed: set[int] = set()
    for allow in attrs.allow:
        if allow.protocol in ("tcp", "all") and _includes(allow.ports, 22):
            exposed.add(22)
        if allow.protocol in ("tcp", "udp", "all") and _includes(allow.ports, 3389):
            exposed.add(3389)
    if not exposed:
        return ()
    return (
        Finding(
            rule_id="TM-GCP-002",
            resource=change.address,
            title="Firewall permits world-sourced administrative traffic",
            rationale="The ingress allow rule includes SSH or RDP ports from a world CIDR. "
            "This does not establish the presence or reachability of a target VM.",
            evidence=(
                f"sources={','.join(attrs.source_ranges)}",
                f"administrative_ports={','.join(map(str, sorted(exposed)))}",
            ),
            remediation="Restrict source ranges and target scope; use IAP or an approved "
            "private access path.",
            status="FAIL",
        ),
    )


def project_basic_roles(change: Change) -> tuple[Finding, ...]:
    if not change.type.startswith("google_project_iam_") or not _proposed(change):
        return ()
    grants = tuple(
        grant
        for grant in change.attributes.grants
        if grant.role in ("roles/owner", "roles/editor") and grant.newly_granted is not False
    )
    if not grants:
        return ()
    return (
        Finding(
            rule_id="TM-GCP-003",
            resource=change.address,
            title="Proposed project-level basic role grant",
            rationale="Owner and editor grant broad project permissions. This is a least-privilege "
            "review, not evidence of internet exposure.",
            evidence=tuple(sorted({f"project role={grant.role}" for grant in grants})),
            remediation="Replace basic roles with narrowly scoped predefined or reviewed "
            "custom roles.",
            status="REVIEW"
            if "conditional_iam" in change.notes
            or any(grant.newly_granted is None for grant in grants)
            else "FAIL",
        ),
    )


def persistent_deletion(change: Change) -> tuple[Finding, ...]:
    if change.type not in PERSISTENT or "delete" not in change.actions:
        return ()
    return (
        Finding(
            rule_id="TM-GCP-004",
            resource=change.address,
            title="Planned deletion of a persistent resource",
            rationale="Deletion or replacement can disrupt service or remove data; backup state "
            "and recovery readiness are not established by this plan.",
            evidence=(f"resource_type={change.type.value}", f"actions={','.join(change.actions)}"),
            remediation="Require human review of ownership, dependencies, backups and a "
            "tested recovery plan.",
            status="REVIEW",
        ),
    )
