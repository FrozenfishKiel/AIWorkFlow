import importlib

from sqlmodel import SQLModel


def test_audit_log_table_is_registered_in_sqlmodel_metadata() -> None:
    """The audit trail must exist as a first-class persisted table."""

    assert "auditlog" in SQLModel.metadata.tables


def test_audit_log_model_exposes_task_focused_event_fields() -> None:
    """The stored audit row should be readable without chasing other objects."""

    audit_module = importlib.import_module("app.models.audit_log")
    AuditLog = audit_module.AuditLog

    field_names = set(AuditLog.model_fields)
    assert {
        "id",
        "task_id",
        "export_job_id",
        "event_type",
        "outcome",
        "summary",
        "details",
        "created_at",
    }.issubset(field_names)
