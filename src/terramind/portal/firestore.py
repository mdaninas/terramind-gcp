"""Durable private portal storage, with transactional sessions and owned reports."""

import base64
import json
import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar, cast

from terramind.cloud.budget import DependencyUnavailable
from terramind.normalizer.io import parse_json
from terramind.portal.store import HistoryFilters, PortalAnalysis, Session, token_hash
from terramind.reports.store import valid_id

T = TypeVar("T")
SUMMARY_FIELDS = ("owner", "created", "expires_at", "risk", "findings", "rules")


class FirestorePortalStore:
    def __init__(
        self,
        project: str,
        database: str,
        *,
        client: Any = None,
        clock: Callable[[], float] = time.time,
    ):
        from google.cloud import firestore

        self.client = (
            client if client is not None else firestore.Client(project=project, database=database)
        )
        self.clock = clock

    def close(self) -> None:
        self.client.close()

    def _now(self) -> datetime:
        return datetime.fromtimestamp(self.clock(), UTC)

    def _run(self, operation: Callable[[Any], T]) -> T:
        from google.cloud import firestore

        try:
            return cast(
                T, firestore.transactional(operation)(self.client.transaction(max_attempts=3))
            )
        except DependencyUnavailable:
            raise
        except Exception:
            raise DependencyUnavailable("Portal transaction unavailable") from None

    def _doc(self, collection: str, key: str) -> Any:
        return self.client.collection(collection).document(key)

    def _active(self, collection: str, now: datetime, limit: int) -> Any:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return (
            self.client.collection(collection)
            .where(filter=FieldFilter("expires_at", ">", now))
            .limit(limit)
        )

    def new_session(
        self, owner: str | None = None, display: str = "", *, previous: str = ""
    ) -> Session:
        result = Session(secrets.token_urlsafe(32), secrets.token_urlsafe(32), owner, display)
        now = self._now()
        previous_hash = token_hash(previous) if previous else ""

        def create(transaction: Any) -> None:
            # Count only projected metadata, never reports or provider credentials.
            rows = (
                self._active("portal_sessions", now, 513)
                .select(("seen",))
                .stream(transaction=transaction, timeout=5, retry=None)
            )
            if sum(row.id != previous_hash for row in rows) >= 512:
                raise DependencyUnavailable("Portal session capacity exhausted")
            if previous_hash:
                transaction.delete(self._doc("portal_sessions", previous_hash))
                transaction.delete(self._doc("portal_flows", previous_hash))
            transaction.create(
                self._doc("portal_sessions", token_hash(result.token)),
                {
                    "csrf": result.csrf,
                    "owner": owner,
                    "display": display,
                    "seen": now,
                    "expires_at": now + timedelta(hours=4),
                },
            )

        self._run(create)
        return result

    def session(self, token: str) -> Session | None:
        if not 40 <= len(token) <= 64 or not token.isascii():
            return None
        reference = self._doc("portal_sessions", token_hash(token))
        now = self._now()

        def read(transaction: Any) -> Session | None:
            value = reference.get(transaction=transaction, timeout=5, retry=None).to_dict()
            if (
                value is None
                or value["expires_at"] <= now
                or value["seen"] <= now - timedelta(minutes=30)
            ):
                return None
            transaction.update(reference, {"seen": now})
            return Session(token, value["csrf"], value["owner"], value["display"])

        return self._run(read)

    def logout(self, token: str) -> None:
        def remove(transaction: Any) -> None:
            transaction.delete(self._doc("portal_sessions", token_hash(token)))
            transaction.delete(self._doc("portal_flows", token_hash(token)))

        self._run(remove)

    def begin_flow(self, session: Session) -> tuple[str, str, str]:
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        self._run(
            lambda transaction: transaction.set(
                self._doc("portal_flows", token_hash(session.token)),
                {
                    "state": token_hash(state),
                    "nonce": nonce,
                    "verifier": verifier,
                    "expires_at": self._now() + timedelta(minutes=5),
                },
            )
        )
        return state, nonce, verifier

    def consume_flow(self, session: Session, state: str) -> tuple[str, str] | None:
        if not 40 <= len(state) <= 64:
            return None
        reference = self._doc("portal_flows", token_hash(session.token))
        now = self._now()

        def consume(transaction: Any) -> tuple[str, str] | None:
            value = reference.get(transaction=transaction, timeout=5, retry=None).to_dict()
            if (
                value is None
                or value["expires_at"] <= now
                or not secrets.compare_digest(value["state"], token_hash(state))
            ):
                return None
            transaction.delete(reference)
            return value["nonce"], value["verifier"]

        return self._run(consume)

    def save(self, owner: str, analysis: PortalAnalysis) -> None:
        raw = analysis.model_dump_json()
        if len(raw.encode()) > 600 * 1024:
            raise DependencyUnavailable("Portal report exceeds its storage bound")
        now, report = self._now(), analysis.report

        def create(transaction: Any) -> None:
            rows = tuple(
                self._active("portal_reports", now, 2049)
                .select(("owner",))
                .stream(transaction=transaction, timeout=5, retry=None)
            )
            if len(rows) >= 2048 or sum(row.to_dict()["owner"] == owner for row in rows) >= 512:
                raise DependencyUnavailable("Portal report capacity exhausted")
            transaction.create(
                self._doc("portal_reports", report.analysis_id),
                {
                    "owner": owner,
                    "created": int(self.clock() * 1000000),
                    "expires_at": now + timedelta(hours=24),
                    "risk": report.overall_risk,
                    "findings": len(report.findings),
                    "rules": sorted({finding.rule_id for finding in report.findings}),
                    "bundle": raw,
                },
            )

        self._run(create)

    def get(self, owner: str, report_id: str) -> PortalAnalysis | None:
        if not valid_id(report_id):
            return None
        try:
            row = self._doc("portal_reports", report_id).get(timeout=5, retry=None).to_dict()
            if row is None or row["owner"] != owner or row["expires_at"] <= self._now():
                return None
            result = PortalAnalysis.model_validate_json(row["bundle"])
            if result.report.analysis_id != report_id:
                raise ValueError("Stored report identity mismatch")
            return result
        except Exception:
            raise DependencyUnavailable("Portal report unavailable") from None

    def history(self, owner: str, filters: HistoryFilters, cursor: str = "") -> dict[str, object]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        boundary = _cursor(cursor) if cursor else None
        if (
            filters.since is not None
            and filters.until is not None
            and filters.since >= filters.until
        ):
            raise ValueError("Invalid history date range")
        try:
            snapshots = (
                self._active("portal_reports", self._now(), 513)
                .where(filter=FieldFilter("owner", "==", owner))
                .select(SUMMARY_FIELDS)
                .stream(timeout=5, retry=None)
            )
            rows = [{**row.to_dict(), "id": row.id} for row in snapshots]
            if len(rows) > 512 or any(
                not valid_id(row["id"]) or row["owner"] != owner for row in rows
            ):
                raise ValueError("Portal history capacity exceeded")
            rows = [
                row
                for row in rows
                if (
                    (filters.risk is None or row["risk"] == filters.risk)
                    and (filters.rule is None or filters.rule in row["rules"])
                    and (filters.since is None or row["created"] >= filters.since)
                    and (filters.until is None or row["created"] < filters.until)
                )
            ]
            rows.sort(key=lambda row: (row["created"], row["id"]), reverse=True)
            totals = {
                "reports": len(rows),
                "high_risk": sum(row["risk"] in ("HIGH", "CRITICAL") for row in rows),
                "findings": sum(row["findings"] for row in rows),
            }
            page = [
                row for row in rows if boundary is None or (row["created"], row["id"]) < boundary
            ]
            next_cursor = ""
            if len(page) > 20:
                next_cursor = (
                    base64.urlsafe_b64encode(
                        json.dumps(
                            {
                                "at": page[19]["created"],
                                "id": page[19]["id"],
                            }
                        ).encode()
                    )
                    .decode()
                    .rstrip("=")
                )
            return {
                "items": [
                    {
                        "analysis_id": row["id"],
                        "created_at": datetime.fromtimestamp(
                            row["created"] / 1000000, UTC
                        ).isoformat(),
                        "risk": row["risk"],
                        "findings": row["findings"],
                        "rules": row["rules"],
                    }
                    for row in page[:20]
                ],
                "next_cursor": next_cursor,
                "totals": totals,
            }
        except Exception:
            raise DependencyUnavailable("Portal history unavailable") from None


def _cursor(value: str) -> tuple[int, str]:
    if len(value) > 256:
        raise ValueError("Invalid history cursor")
    data = parse_json(
        base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True), 256
    )
    if (
        set(data) != {"at", "id"}
        or type(data["at"]) is not int
        or not 0 <= data["at"] <= 4102444800000000
        or not isinstance(data["id"], str)
        or not valid_id(data["id"])
    ):
        raise ValueError("Invalid history cursor")
    return data["at"], data["id"]
