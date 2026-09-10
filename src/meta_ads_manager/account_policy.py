"""Project-wide account rules; only approved creation through the wizard is supported."""

from meta_ads_manager.errors import AppError


def account_change_policy() -> dict:
    return {
        "version": "2026-09-10",
        "deletion_allowed": False,
        "user_approval_required_for_every_change": True,
        "approval_scope": "exact_plan",
        "autonomous_writes_allowed": False,
        "write_executor_implemented": True,
        "write_scope": "create_paused_only",
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
