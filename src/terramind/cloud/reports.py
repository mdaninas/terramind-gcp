"""Create-only reports in the fixed analyses collection; TTL is also enforced on reads."""

from datetime import UTC, datetime
from typing import Any

from google.cloud import firestore

from terramind.cloud.budget import CallBudget, DependencyUnavailable
from terramind.cloud.google import is_transient
from terramind.cloud.settings import CloudSettings
from terramind.reports.store import StoredAnalysis, valid_id


class FirestoreReportStore:
    def __init__(self, settings: CloudSettings, client: Any = None):
        self.client = client or firestore.Client(
            project=settings.project_id, database=settings.database
        )
        self.collection = self.client.collection("analyses")

    def save(self, record: StoredAnalysis) -> None:
        # Do not retry an ambiguous write or overwrite an existing report.
        CallBudget(seconds=3, max_calls=1, per_call=3).run(
            lambda timeout: self.collection.document(record.analysis_id).create(
                record.model_dump(), retry=None, timeout=timeout
            ),
            transient=lambda _: False,
        )

    def get(self, analysis_id: str) -> StoredAnalysis | None:
        if not valid_id(analysis_id):
            return None
        snapshot = CallBudget(seconds=4, max_calls=3, per_call=2).run(
            lambda timeout: self.collection.document(analysis_id).get(retry=None, timeout=timeout),
            transient=is_transient,
        )
        if not snapshot.exists:
            return None
        try:
            record = StoredAnalysis.model_validate(snapshot.to_dict())
            if record.analysis_id != analysis_id:
                raise ValueError("Report identity mismatch")
        except Exception:
            raise DependencyUnavailable("Stored report invalid") from None
        # Firestore TTL deletion is asynchronous; expired records are never served.
        return record if record.expires_at > datetime.now(UTC) else None
