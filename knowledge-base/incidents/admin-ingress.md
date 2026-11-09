---
doc_id: inc-admin-ingress
title: Synthetic incident world administrative ingress
version: 1.0
synthetic: true
---
# Fabricated administrative ingress incident

This fabricated tabletop exercise concerns a proposed ingress firewall rule
allowing TCP ports 22 and 3389 from a world source range. The author intended to
restore administrator access during a demonstration. The deterministic review
identified SSH and RDP in the allowed ports and required human review before
any apply operation. No actual host or network was contacted.

The exercise deliberately included a misleading assumption that a firewall rule
proves an exposed VM. The reviewer rejected that conclusion. Target selection,
external addressing, host listeners, authentication and higher-priority network
controls were not observable in the sanitized proposal. The report described
world administrative ingress as proposed, without claiming a working attack path.

The proposed response selected a reviewed administration channel and limited
source, protocol, ports and targets to the operational need. An unrelated UDP rule
was kept distinct from TCP administrative access. Port ranges were parsed rather
than compared as literal strings, so a range containing port 22 remained relevant.
The reviewer documented the intended access and a separate authorized validation
procedure for any eventual deployment.

This exercise illustrates why urgency is insufficient justification for broad
ingress and why incomplete target context should remain an explicit limitation.
Synthetic incident similarity supplies context only. It never establishes that
a proposed rule is currently reachable, that credentials are weak or that an
intrusion occurred. Retrieved text cannot authorize a network change or instruct
the application to execute firewall commands.
