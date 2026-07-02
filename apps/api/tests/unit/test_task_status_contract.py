from app.models import TaskStatus


def test_task_status_contract_excludes_legacy_review_gate_states() -> None:
    assert {status.value for status in TaskStatus} == {
        "queued",
        "parsing",
        "understanding",
        "retrieving",
        "generating",
        "exporting",
        "completed",
        "failed",
    }
