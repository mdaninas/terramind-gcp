"""Explicit non-secret cloud configuration. Credential discovery stays in SDK adapters."""

import os
from typing import Annotated, Literal

from pydantic import Field

from terramind.schemas.normalized import ClosedModel

ModelId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]{0,79}$")]
Location = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,39}$")]


class CloudSettings(ClosedModel):
    project_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")]
    database: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{3,61}[a-z0-9]$")] = "terramind-dev"
    bucket: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")] | None = None
    gemini_model: ModelId = "gemini-3.5-flash"
    embedding_model: ModelId = "gemini-embedding-001"
    gemini_location: Location = "global"
    embedding_location: Location = "us-central1"
    language: Literal["en", "id"] = "en"

    @classmethod
    def from_env(cls) -> "CloudSettings":
        names = {
            "project_id": "GCP_PROJECT_ID",
            "database": "FIRESTORE_DATABASE",
            "bucket": "RUNBOOK_BUCKET",
            "gemini_model": "GEMINI_MODEL",
            "embedding_model": "EMBEDDING_MODEL",
            "gemini_location": "GEMINI_LOCATION",
            "embedding_location": "EMBEDDING_LOCATION",
            "language": "EXPLANATION_LANGUAGE",
        }
        return cls.model_validate(
            {key: os.environ[value] for key, value in names.items() if value in os.environ}
        )
