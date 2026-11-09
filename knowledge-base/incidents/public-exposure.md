---
doc_id: inc-public-exposure
title: Synthetic incident public object grant
version: 1.0
synthetic: true
---
# Fabricated public object grant incident

This is a fabricated tabletop incident, not evidence about a real organization.
In the exercise, a proposed Cloud Storage binding added allUsers with an
object-view role while a team intended the content for a private application.
The review found the permission change before deployment. No claim is made that
any real object was accessible or read.

The exercise distinguished two variants. In the first, public access prevention
was verifiably enforced, so the reviewer documented conflicting access intent and
a conditional review finding. In the second, prevention could not be established
from the plan facts. The reviewer retained the public-grant risk and the uncertainty
instead of fabricating effective-access evidence. Neither variant changed policy
severity based on a persuasive model explanation.

The proposed correction removed the public principal and selected a scoped
application identity for object reads. The review also retained uniform access,
confirmed prevention intent and checked that unrelated memberships did not hide
the newly added grant. The owner used the original local plan to identify the
resource; only anonymous facts entered the demonstration report.

Lessons from the fabricated exercise: distinguish proposal from deployed exposure,
separate prevention from membership intent, preserve citations to the relevant
runbook and never use an AI statement as approval. A similar retrieved incident
is contextual training material, not proof that a new change will have the same
outcome. Real incident investigation would require separately authorized logs and
effective-policy evidence that are outside this synthetic demonstration.
