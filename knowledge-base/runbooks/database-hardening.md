---
doc_id: rb-database-hardening
title: Synthetic Cloud SQL connectivity and TLS hardening
version: 1.0
synthetic: true
---
# Cloud SQL connectivity and TLS hardening

Synthetic training runbook. No real database or incident is described.
For TM-GCP-007, public IPv4 enabled together with a world authorized network
0.0.0.0/0 permits broad direct-client source authorization. Prefer private
connectivity or restrict authorized networks to approved source ranges. This plan
does not establish deployed reachability, a successful login or a data breach.
Database credentials and effective runtime controls still matter.

For TM-GCP-008, the explicit SSL mode ALLOW_UNENCRYPTED_AND_ENCRYPTED permits
unencrypted direct database connections. Choose ENCRYPTED_ONLY to require TLS,
or TRUSTED_CLIENT_CERTIFICATE_REQUIRED where supported to also require trusted
client certificates. Verify engine support, client compatibility and certificate
rotation before rollout. Cloud SQL Auth Proxy and connectors use secure transport;
their presence does not change the direct-connection setting checked here.

Review newly enabled weak settings and creates. A label-only update with unchanged
weak settings is outside these change rules. Unknown or sensitive network and TLS
fields must remain uncertain. Do not infer ssl_mode from a legacy require_ssl flag.
Never upload database names, private CIDRs, credentials or raw plans. Preserve
deterministic severity and record a human review before deployment.
