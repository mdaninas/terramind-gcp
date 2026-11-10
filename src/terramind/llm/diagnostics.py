"""Content-free advisory outcomes shared by adapters and verification tools."""

from enum import StrEnum


class AdvisoryReason(StrEnum):
    VALIDATED = "validated"
    NOT_REQUESTED = "not_requested"
    DEPENDENCY = "dependency_unavailable"
    DEADLINE = "deadline_exceeded"
    CALL_LIMIT = "call_limit_exceeded"
    TIMEOUT = "provider_timeout"
    REJECTED = "provider_rejected"
    RATE_LIMIT = "provider_rate_limited"
    INCOMPLETE = "generation_incomplete"
    EMPTY = "generation_empty"
    RETRIEVAL = "retrieval_unavailable"
    INPUT_LIMIT = "input_limit"
    RESPONSE_SIZE = "response_size"
    RESPONSE_CONTRACT = "response_contract"
    FINDING_COVERAGE = "finding_coverage"
    CITATION_COVERAGE = "citation_coverage"
    ADVISORY_CONTRACT = "advisory_contract"


LIMITATIONS = {
    AdvisoryReason.DEPENDENCY: "Advisory dependency unavailable; policy findings retained.",
    AdvisoryReason.DEADLINE: "Advisory deadline exceeded; policy findings retained.",
    AdvisoryReason.CALL_LIMIT: "Advisory call limit reached; policy findings retained.",
    AdvisoryReason.TIMEOUT: "Advisory provider timed out; policy findings retained.",
    AdvisoryReason.REJECTED: "Advisory provider rejected the request; policy findings retained.",
    AdvisoryReason.RATE_LIMIT: "Advisory provider rate limit reached; policy findings retained.",
    AdvisoryReason.INCOMPLETE: "Advisory generation did not complete; policy findings retained.",
    AdvisoryReason.EMPTY: "Advisory generation returned no text; policy findings retained.",
    AdvisoryReason.RETRIEVAL: "Knowledge empty, invalid or unavailable for some findings.",
    AdvisoryReason.INPUT_LIMIT: "Advisory input limit exceeded; policy findings retained.",
    AdvisoryReason.RESPONSE_SIZE: (
        "Advisory response exceeded its size limit; policy findings retained."
    ),
    AdvisoryReason.RESPONSE_CONTRACT: (
        "Advisory response failed validation; policy findings retained."
    ),
    AdvisoryReason.FINDING_COVERAGE: (
        "Advisory finding coverage was invalid; policy findings retained."
    ),
    AdvisoryReason.CITATION_COVERAGE: (
        "Advisory lacked grounded citations; policy findings retained."
    ),
    AdvisoryReason.ADVISORY_CONTRACT: "Final advisory failed validation; policy findings retained.",
}


class AdvisoryUnavailable(RuntimeError):
    """Classified failure; exception text must never be logged or returned."""

    def __init__(self, message: str, *, reason: AdvisoryReason = AdvisoryReason.DEPENDENCY):
        super().__init__(message)
        self.reason = AdvisoryReason(reason)
        if self.reason not in LIMITATIONS:
            raise ValueError("Invalid advisory failure reason")
