"""The hosted demo accepts only the synthetic subset of the normalized contract."""

from typing import Literal

from terramind.schemas.normalized import NormalizedPlan


class AnalysisRequest(NormalizedPlan):
    source: Literal["synthetic-demo"]
