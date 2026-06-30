# API Area Rules

- Use `D:\Anaconda3\envs\ai-content-ops\python.exe` for project Python commands.
- Keep FastAPI request handlers thin.
- Put business rules in `services`, persistence in `repositories`, and async
  orchestration entrypoints outside request handlers.
- Do not let long-running parsing, retrieval, generation, or export work block
  request threads once the async path exists.
- Keep structured schemas explicit. Prefer clear Pydantic or SQLModel models
  over ad hoc dictionaries.
- If you change API behavior, update verification notes or docs when needed.
- Verify API-side changes with:
  `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope api`
