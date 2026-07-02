from app.tasks.celery_app import celery_app


def test_celery_app_registers_all_local_async_tasks() -> None:
    assert "app.tasks.run_task_pipeline" in celery_app.tasks
    assert "app.tasks.run_export_job" in celery_app.tasks
    assert "app.tasks.index_knowledge_document" in celery_app.tasks
