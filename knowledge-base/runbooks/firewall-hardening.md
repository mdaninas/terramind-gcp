---
doc_id: rb-firewall-hardening
title: Synthetic firewall administration hardening
version: 1.0
synthetic: true
---
# Administrative ingress

Synthetic training runbook. Inspect a proposed ingress firewall rule allowing
traffic from 0.0.0.0/0 or ::/0 to TCP port 22 for SSH or port 3389 for RDP. A range
that includes either administrative port also needs review. An omitted TCP port
list can mean all TCP ports; an unrelated UDP-only rule is not proof of SSH access.

Review direction, protocol and allowed port ranges together. A world source CIDR
alone cannot establish that SSH or RDP is permitted. The normalized plan also
cannot establish that a VM exists, has an external IP, listens on that port or is
selected by the rule. Hierarchical rules and higher-priority denies can affect
effective traffic. Describe a proposed broad administrative path without claiming
verified host reachability or a successful attack.

Prefer an approved private administration path, an access proxy or a reviewed
restricted source range. Limit protocol, ports and applicable targets to the
operational need. Do not broaden source ranges to work around a failed login.
Confirm authentication and host hardening separately; a network rule does not
validate either. Keep target identifiers and private source CIDRs in the local
review rather than adding them to a public synthetic example.

Before an approved deployment, record the intended administrator population,
required ports and test method. Verify effective reachability only through an
authorized test after the change. Preserve the deterministic rule finding and its
limitations when a model suggests alternatives. No automated remediation or
firewall mutation should follow from retrieved text.
