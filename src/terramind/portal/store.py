"""Bounded SQLite sessions and owner-scoped synthetic reports for a single host."""

import base64
import hashlib
import json
import secrets
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Annotated, Literal

from pydantic import Field, model_validator

from terramind.cloud.budget import DependencyUnavailable
from terramind.incidents.search import IncidentMemory
from terramind.normalizer.io import parse_json
from terramind.reports.store import valid_id
from terramind.schemas.normalized import ClosedModel
from terramind.schemas.report import Report

Risk = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "NO_KNOWN_FINDINGS"]
Rule = Literal[
    "TM-GCP-001",
    "TM-GCP-002",
    "TM-GCP-003",
    "TM-GCP-004",
    "TM-GCP-005",
    "TM-GCP-006",
    "TM-GCP-007",
    "TM-GCP-008",
]


def owner_key(provider: str, subject: str) -> str:
    return hashlib.sha256(f"{provider}:{subject}".encode()).hexdigest()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class Session:
    token: str = field(repr=False)
    csrf: str = field(repr=False)
    owner: str | None = None
    display: str = ""


class PortalAnalysis(ClosedModel):
    report: Report
    incident_memory: IncidentMemory

    @model_validator(mode="after")
    def valid_identity(self) -> "PortalAnalysis":
        if not valid_id(self.report.analysis_id):
            raise ValueError("Portal report identity must be a generated UUID")
        return self


class HistoryFilters(ClosedModel):
    risk: Risk | None = None
    rule: Rule | None = None
    since: Annotated[int, Field(ge=0, le=4102444800000000)] | None = None
    until: Annotated[int, Field(ge=0, le=4102444800000000)] | None = None


class PortalStore:
    def __init__(self, path: Path, *, clock: Callable[[], float] = time.time):
        self.clock, self.lock = clock, RLock()
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(
            str(path), check_same_thread=False, isolation_level=None, timeout=3
        )
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS sessions (
                digest TEXT PRIMARY KEY, csrf TEXT NOT NULL, owner TEXT, display TEXT NOT NULL,
                created INTEGER NOT NULL, seen INTEGER NOT NULL, expires INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS flows (
                digest TEXT PRIMARY KEY, session TEXT NOT NULL, nonce TEXT NOT NULL,
                verifier TEXT NOT NULL, expires INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, created INTEGER NOT NULL,
                expires INTEGER NOT NULL, risk TEXT NOT NULL, findings INTEGER NOT NULL,
                rules TEXT NOT NULL, bundle TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS reports_owner_time ON reports(owner, created DESC, id DESC);
        """)

    def close(self) -> None:
        with self.lock:
            self.db.close()

    def _now(self) -> int:
        return int(self.clock() * 1000000)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def _prune(self, now: int) -> None:
        self.db.execute(
            "DELETE FROM sessions WHERE expires<=? OR seen<=?", (now, now - 1800_000000)
        )
        self.db.execute("DELETE FROM flows WHERE expires<=?", (now,))
        self.db.execute("DELETE FROM reports WHERE expires<=?", (now,))

    def new_session(
        self, owner: str | None = None, display: str = "", *, previous: str = ""
    ) -> Session:
        session = Session(secrets.token_urlsafe(32), secrets.token_urlsafe(32), owner, display)
        now = self._now()
        with self._transaction():
            self._prune(now)
            if previous:
                self.db.execute("DELETE FROM sessions WHERE digest=?", (token_hash(previous),))
                self.db.execute("DELETE FROM flows WHERE session=?", (token_hash(previous),))
            if self.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] >= 512:
                raise DependencyUnavailable("Session capacity exhausted")
            self.db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    token_hash(session.token),
                    session.csrf,
                    owner,
                    display,
                    now,
                    now,
                    now + 14400_000000,
                ),
            )
        return session

    def session(self, token: str) -> Session | None:
        if not 40 <= len(token) <= 64 or not token.isascii():
            return None
        with self._transaction():
            now = self._now()
            self._prune(now)
            row = self.db.execute(
                "SELECT * FROM sessions WHERE digest=?", (token_hash(token),)
            ).fetchone()
            if row is None:
                return None
            self.db.execute("UPDATE sessions SET seen=? WHERE digest=?", (now, token_hash(token)))
            return Session(token, row["csrf"], row["owner"], row["display"])

    def logout(self, token: str) -> None:
        with self._transaction():
            self.db.execute("DELETE FROM sessions WHERE digest=?", (token_hash(token),))
            self.db.execute("DELETE FROM flows WHERE session=?", (token_hash(token),))

    def begin_flow(self, session: Session) -> tuple[str, str, str]:
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        with self._transaction():
            self._prune(self._now())
            self.db.execute("DELETE FROM flows WHERE session=?", (token_hash(session.token),))
            self.db.execute(
                "INSERT INTO flows VALUES (?, ?, ?, ?, ?)",
                (
                    token_hash(state),
                    token_hash(session.token),
                    nonce,
                    verifier,
                    self._now() + 300_000000,
                ),
            )
        return state, nonce, verifier

    def consume_flow(self, session: Session, state: str) -> tuple[str, str] | None:
        if not 40 <= len(state) <= 64:
            return None
        with self._transaction():
            self._prune(self._now())
            row = self.db.execute(
                "SELECT * FROM flows WHERE digest=? AND session=?",
                (
                    token_hash(state),
                    token_hash(session.token),
                ),
            ).fetchone()
            if row is None:
                return None
            self.db.execute("DELETE FROM flows WHERE digest=?", (token_hash(state),))
            return row["nonce"], row["verifier"]

    def save(self, owner: str, analysis: PortalAnalysis) -> None:
        raw = analysis.model_dump_json()
        if len(raw.encode()) > 600 * 1024:
            raise DependencyUnavailable("Portal report exceeds its storage bound")
        with self._transaction():
            now = self._now()
            self._prune(now)
            if (
                self.db.execute("SELECT COUNT(*) FROM reports").fetchone()[0] >= 2048
                or self.db.execute(
                    "SELECT COUNT(*) FROM reports WHERE owner=?", (owner,)
                ).fetchone()[0]
                >= 512
            ):
                raise DependencyUnavailable("Portal report capacity exhausted")
            report = analysis.report
            self.db.execute(
                "INSERT INTO reports VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    report.analysis_id,
                    owner,
                    now,
                    now + 86400_000000,
                    report.overall_risk,
                    len(report.findings),
                    json.dumps(sorted({finding.rule_id for finding in report.findings})),
                    raw,
                ),
            )

    def get(self, owner: str, report_id: str) -> PortalAnalysis | None:
        if not valid_id(report_id):
            return None
        with self.lock:
            row = self.db.execute(
                "SELECT bundle FROM reports WHERE id=? AND owner=? AND expires>?",
                (
                    report_id,
                    owner,
                    self._now(),
                ),
            ).fetchone()
            if row is None:
                return None
            try:
                result = PortalAnalysis.model_validate_json(row[0])
                if result.report.analysis_id != report_id:
                    raise ValueError("Stored report identity mismatch")
                return result
            except ValueError:
                raise DependencyUnavailable("Stored portal report invalid") from None

    def history(self, owner: str, filters: HistoryFilters, cursor: str = "") -> dict[str, object]:
        where, params = ["owner=?", "expires>?"], [owner, self._now()]
        if filters.risk:
            where.append("risk=?")
            params.append(filters.risk)
        if filters.rule:
            where.append("EXISTS (SELECT 1 FROM json_each(reports.rules) WHERE value=?)")
            params.append(filters.rule)
        if filters.since is not None:
            where.append("created>=?")
            params.append(filters.since)
        if filters.until is not None:
            where.append("created<?")
            params.append(filters.until)
        if (
            filters.since is not None
            and filters.until is not None
            and filters.since >= filters.until
        ):
            raise ValueError("Invalid history date range")
        with self.lock:
            stats = self.db.execute(
                "SELECT COUNT(*), COALESCE(SUM(risk IN ('HIGH','CRITICAL')),0), "
                "COALESCE(SUM(findings),0) FROM reports WHERE " + " AND ".join(where),
                params,
            ).fetchone()
            if cursor:
                if len(cursor) > 256:
                    raise ValueError("Invalid history cursor")
                data = parse_json(
                    base64.b64decode(
                        cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True
                    ),
                    256,
                )
                if (
                    set(data) != {"at", "id"}
                    or type(data["at"]) is not int
                    or data["at"] < 0
                    or data["at"] > 4102444800000000
                    or not isinstance(data["id"], str)
                    or not valid_id(data["id"])
                ):
                    raise ValueError("Invalid history cursor")
                where.append("(created<? OR (created=? AND id<?))")
                params.extend((data["at"], data["at"], data["id"]))
            rows = self.db.execute(
                "SELECT id, created, risk, findings, rules FROM reports WHERE "
                + " AND ".join(where)
                + " ORDER BY created DESC, id DESC LIMIT 21",
                params,
            ).fetchall()
            more = len(rows) > 20
            items = [
                {
                    "analysis_id": row["id"],
                    "created_at": datetime.fromtimestamp(row["created"] / 1000000, UTC).isoformat(),
                    "risk": row["risk"],
                    "findings": row["findings"],
                    "rules": json.loads(row["rules"]),
                }
                for row in rows[:20]
            ]
            next_cursor = ""
            if more:
                last = rows[19]
                next_cursor = (
                    base64.urlsafe_b64encode(
                        json.dumps({"at": last["created"], "id": last["id"]}).encode()
                    )
                    .decode()
                    .rstrip("=")
                )
            return {
                "items": items,
                "next_cursor": next_cursor,
                "totals": {"reports": stats[0], "high_risk": stats[1], "findings": stats[2]},
            }
