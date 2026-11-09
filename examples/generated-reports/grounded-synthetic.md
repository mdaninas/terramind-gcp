# Terramind risk report

Analysis: `5a4a49c0-1262-4931-a57a-8fafd7a724b4`
Generated (UTC): 2026-11-09T04:22:13.780882+00:00
Overall risk: **HIGH**
Policy version: 1.0
RAG status: available; model: gemini-3.5-flash

The deterministic Terraform review identified four findings involving administrative firewall rules, project permissions, data destruction, and public access grants that require operator attention prior to deployment\.

## Changed resources

- `google_storage_bucket_iam_member.resource_0001`
- `google_compute_firewall.resource_0002`
- `google_project_iam_binding.resource_0003`
- `google_storage_bucket.resource_0004`

## Findings

### TM-GCP-002 - Firewall permits world-sourced administrative traffic

**HIGH / FAIL** - `google_compute_firewall.resource_0002`

The ingress allow rule includes SSH or RDP ports from a world CIDR. This does not establish the presence or reachability of a target VM.

Evidence:

- sources=0.0.0.0/0
- administrative_ports=22

Remediation: Restrict source ranges and target scope; use IAP or an approved private access path.

### TM-GCP-003 - Proposed project-level basic role grant

**HIGH / FAIL** - `google_project_iam_binding.resource_0003`

Owner and editor grant broad project permissions. This is a least-privilege review, not evidence of internet exposure.

Evidence:

- project role=roles/owner

Remediation: Replace basic roles with narrowly scoped predefined or reviewed custom roles.

### TM-GCP-004 - Planned deletion of a persistent resource

**HIGH / REVIEW** - `google_storage_bucket.resource_0004`

Deletion or replacement can disrupt service or remove data; backup state and recovery readiness are not established by this plan.

Evidence:

- resource_type=google_storage_bucket
- actions=delete

Remediation: Require human review of ownership, dependencies, backups and a tested recovery plan.

### TM-GCP-001 - Proposed public Cloud Storage object-read grant

**HIGH / FAIL** - `google_storage_bucket_iam_member.resource_0001`

Public principals receive object-read permissions; exposure depends on prevention policies and any IAM conditions.

Evidence:

- roles/storage.objectViewer -> allUsers
- public_access_prevention=unknown

Remediation: Remove public principals; use scoped identities and enforce public access prevention.

## AI advisory

Advisory text does not change policy findings.

- TM\-GCP\-002:google\_compute\_firewall\.resource\_0002: The proposed configuration allows SSH administrative traffic \(port 22\) from any IP address \(0\.0\.0\.0/0\)\. This represents an administrative ingress path, although the actual presence or reachability of a target VM cannot be established from the plan alone\.
  Sources: rb-firewall-hardening:administrative-ingress-000, inc-admin-ingress:fabricated-administrative-ingress-incident-000, rb-review-checklist:deployment-review-checklist-000
- TM\-GCP\-003:google\_project\_iam\_binding\.resource\_0003: The proposed grant assigns a basic project role \(roles/owner\) which expands administrative capabilities\. This represents an authorization risk rather than direct proof of internet exposure\.
  Sources: rb-iam-least-privilege:project-basic-roles-000, inc-basic-role-expansion:fabricated-basic-role-expansion-incident-000, rb-public-bucket:public-bucket-access-000
- TM\-GCP\-004:google\_storage\_bucket\.resource\_0004: The plan requests the deletion of a persistent Cloud Storage bucket\. A destructive action presents a service disruption or data loss risk; backup readiness and recovery capabilities are not verified by this plan\.
  Sources: rb-backup-deletion:persistent-resource-deletion-000, inc-destructive-replacement:fabricated-destructive-replacement-incident-000, rb-public-bucket:public-bucket-access-000
- TM\-GCP\-001:google\_storage\_bucket\_iam\_member\.resource\_0001: The plan proposes granting object\-read access \(roles/storage\.objectViewer\) to allUsers\. This public principal grant conflicts with private access goals, though effective exposure depends on bucket\-level and organizational prevention policies\.
  Sources: rb-public-bucket:public-bucket-access-000, inc-public-exposure:fabricated-public-object-grant-incident-000, rb-access-prevention:public-access-prevention-interpretation-000

### Recommendations

- Restrict firewall ingress rules to validated, scoped private networks or use an access proxy such as IAP\.
- Replace broad project roles with narrowly scoped, predefined or custom IAM roles mapped to operational needs\.
- Verify database and bucket backup retention, integrity, and restore procedures locally before applying deletions\.
- Remove allUsers from object\-read permissions and configure public access prevention on the bucket\.

### Cited synthetic sources

- `rb-firewall-hardening:administrative-ingress-000`: Synthetic firewall administration hardening (rb\-firewall\-hardening, administrative\-ingress\-000, version 1\.0, runbooks/firewall\-hardening\.md); content SHA-256 `8121efd1178c656609df429ae5b41899248f93266566206748ea6ff0c7582e5d`
- `inc-admin-ingress:fabricated-administrative-ingress-incident-000`: Synthetic incident world administrative ingress (inc\-admin\-ingress, fabricated\-administrative\-ingress\-incident\-000, version 1\.0, incidents/admin\-ingress\.md); content SHA-256 `258d33a0462e48ef2f3545ceba088d079572a4836e5f1702995fa400aee9df3a`
- `rb-review-checklist:deployment-review-checklist-000`: Synthetic deployment review checklist (rb\-review\-checklist, deployment\-review\-checklist\-000, version 1\.0, runbooks/review\-checklist\.md); content SHA-256 `e8a17fd44c20532b602bcdbe7bb8770486b841fc213aebca7abcaec159d3ba38`
- `rb-iam-least-privilege:project-basic-roles-000`: Synthetic project IAM least privilege review (rb\-iam\-least\-privilege, project\-basic\-roles\-000, version 1\.0, runbooks/iam\-least\-privilege\.md); content SHA-256 `e2206dc00c64af5e0b192cd18139aec40f790f32b40ecfe03d3173faf6232489`
- `inc-basic-role-expansion:fabricated-basic-role-expansion-incident-000`: Synthetic incident excessive project permissions (inc\-basic\-role\-expansion, fabricated\-basic\-role\-expansion\-incident\-000, version 1\.0, incidents/basic\-role\-expansion\.md); content SHA-256 `5253109d44ca436630dfa39559d88836b173c9d5824bc4874709dd2b69b075f2`
- `rb-public-bucket:public-bucket-access-000`: Synthetic public bucket access review (rb\-public\-bucket, public\-bucket\-access\-000, version 1\.0, runbooks/public\-bucket\.md); content SHA-256 `9b00d628ae0d1ee59c8f1b469965b3f26494184a64f16039a47ed0ab499db3ab`
- `rb-backup-deletion:persistent-resource-deletion-000`: Synthetic persistent data deletion review (rb\-backup\-deletion, persistent\-resource\-deletion\-000, version 1\.0, runbooks/backup\-deletion\.md); content SHA-256 `d9ecd779e9af8816e74df06cac4927a94ce44db24090ec33484641a51ba3f0f5`
- `inc-destructive-replacement:fabricated-destructive-replacement-incident-000`: Synthetic incident destructive database replacement (inc\-destructive\-replacement, fabricated\-destructive\-replacement\-incident\-000, version 1\.0, incidents/destructive\-replacement\.md); content SHA-256 `d8e95937b783101c6451454623b5713bf5f947ddc06b9c7a52c23242956f8564`
- `inc-public-exposure:fabricated-public-object-grant-incident-000`: Synthetic incident public object grant (inc\-public\-exposure, fabricated\-public\-object\-grant\-incident\-000, version 1\.0, incidents/public\-exposure\.md); content SHA-256 `e9020c7badeeb1be43ba4e285e2ca96249435a7b48fec87d25f93ff040ee36f5`
- `rb-access-prevention:public-access-prevention-interpretation-000`: Synthetic public access prevention interpretation (rb\-access\-prevention, public\-access\-prevention\-interpretation\-000, version 1\.0, runbooks/access\-prevention\.md); content SHA-256 `79e12fe650818a1641fec3905c7ef8c12ea4f54e01a8b79e628d1fa4cc28f277`

## Limitations

- Terramind checks four specific policies; no known findings is not a guarantee of safety\.
- Findings describe proposed changes, not verified deployed exposure or backup status\.
- Resource aliases conceal original identifiers; correlate by input order locally\.
- AI text is advisory and can be incorrect\.
- The plan facts do not establish if a VM exists, listens on the target port, or has a public IP assigned\.
- Sanitized payloads omit IAM conditions and parent organization policies, leaving effective permission states uncertain\.
- The proposed actions do not verify whether backup copies exist, are valid, or have been successfully tested\.
- A model explanation is supporting guidance and does not constitute authorization to modify or apply infrastructure\.
