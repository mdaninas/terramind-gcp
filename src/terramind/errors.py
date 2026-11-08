"""Errors safe to show without echoing untrusted input or local file paths."""


class InputError(ValueError):
    """Invalid or unsupported input; messages must never include input values."""
