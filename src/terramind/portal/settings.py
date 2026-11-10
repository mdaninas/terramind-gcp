"""Explicit portal configuration; OAuth secrets never enter public settings or repr."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit


@dataclass(frozen=True)
class PortalSettings:
    origin: str = "http://127.0.0.1:8080"
    database: Path = Path("artifacts/portal.sqlite3")
    auth_mode: Literal["demo", "google"] = "demo"
    analysis_mode: Literal["offline", "cloud"] = "offline"
    storage_backend: Literal["sqlite", "firestore"] = "sqlite"
    project: str = ""
    firestore_database: str = ""
    transport_host: str = ""
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    allowed_emails: tuple[str, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        if not self.origin.isascii() or any(ord(character) <= 32 for character in self.origin):
            raise ValueError("Portal origin must be a canonical URL")
        parsed = urlsplit(self.origin)
        local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or (parsed.scheme == "http" and not local)
        ):
            raise ValueError("Use an HTTPS portal origin or an explicit loopback HTTP origin")
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("Invalid portal port")
        if self.auth_mode not in {"demo", "google"}:
            raise ValueError("Unsupported portal authentication mode")
        if self.analysis_mode not in {"offline", "cloud"}:
            raise ValueError("Unsupported portal analysis mode")
        if self.storage_backend not in {"sqlite", "firestore"}:
            raise ValueError("Unsupported portal storage backend")
        if self.storage_backend == "firestore" and (
            self.auth_mode != "google"
            or not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", self.project)
            or not re.fullmatch(r"[a-z][a-z0-9-]{2,61}[a-z0-9]", self.firestore_database)
        ):
            raise ValueError("Cloud portal storage requires Google login and a named database")
        if os.environ.get("K_SERVICE") and self.storage_backend != "firestore":
            raise ValueError("Cloud Run portal requires durable Firestore storage")
        if self.transport_host and (
            self.auth_mode != "google"
            or self.storage_backend != "firestore"
            or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,200}\.run\.app", self.transport_host)
        ):
            raise ValueError("Portal transport host must be an exact private Cloud Run hostname")
        if self.analysis_mode == "cloud" and self.auth_mode != "google":
            raise ValueError("Paid cloud analysis requires Google authentication")
        if self.auth_mode == "demo" and (not local or os.environ.get("K_SERVICE")):
            raise ValueError(
                "Synthetic demo accounts are restricted to a loopback development server"
            )
        if self.auth_mode == "google" and (
            not re.fullmatch(r"[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com", self.client_id)
            or len(self.client_secret) < 16
            or not self.allowed_emails
            or len(self.allowed_emails) > 100
            or any("@" not in email or len(email) > 254 for email in self.allowed_emails)
        ):
            raise ValueError(
                "Google login requires an OAuth client, secret and exact email allowlist"
            )

    @property
    def secure(self) -> bool:
        return self.origin.startswith("https://")

    @property
    def cookie_name(self) -> str:
        return "__Host-terramind_session" if self.secure else "terramind_session"

    @property
    def callback(self) -> str:
        return self.origin + "/auth/callback"

    @classmethod
    def from_env(cls) -> "PortalSettings":
        return cls(
            origin=os.environ.get(
                "PORTAL_ORIGIN", f"http://127.0.0.1:{os.environ.get('PORT', '8080')}"
            ),
            database=Path(os.environ.get("PORTAL_DATABASE", "artifacts/portal.sqlite3")),
            auth_mode=os.environ.get("PORTAL_AUTH_MODE", "demo"),  # type: ignore[arg-type]
            analysis_mode=os.environ.get("PORTAL_ANALYSIS_MODE", "offline"),  # type: ignore[arg-type]
            storage_backend=os.environ.get("PORTAL_STORAGE_BACKEND", "sqlite"),  # type: ignore[arg-type]
            project=os.environ.get("GCP_PROJECT_ID", ""),
            firestore_database=os.environ.get("PORTAL_FIRESTORE_DATABASE", ""),
            transport_host=os.environ.get("PORTAL_TRANSPORT_HOST", ""),
            client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
            client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            allowed_emails=tuple(
                email.strip().lower()
                for email in os.environ.get("PORTAL_ALLOWED_EMAILS", "").split(",")
                if email.strip()
            ),
        )
