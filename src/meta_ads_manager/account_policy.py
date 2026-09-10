"""Project-wide account rules; writes remain unavailable in this release."""

from meta_ads_manager.errors import AppError


def account_change_policy() -> dict:
    return {
        "version": "2026-09-10",
        "deletion_allowed": False,
        "user_approval_required_for_every_change": True,
        "approval_scope": "exact_plan",
        "autonomous_writes_allowed": False,
        "write_executor_implemented": False,
    }


def validate_read_params(params: dict) -> None:
    """Do not allow Graph method overrides or embedded batch operations in a read."""
    blocked = {"method", "_method", "http_method", "x-http-method-override", "batch"}
    if any(str(key).strip().lower() in blocked for key in params):
        raise AppError(
            "READ_ONLY_VIOLATION",
            "Odczyt nie dopuszcza zmiany metody ani operacji zbiorczych.",
            2,
        )
