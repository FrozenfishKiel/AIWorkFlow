# Web Area Rules

- This app is the task console, not a broad platform shell.
- Keep the UI focused on task creation, status, review, and export flows.
- Preserve the existing `src/app`, `src/pages`, `src/components`,
  `src/features`, `src/services`, and `src/types` structure.
- Prefer straightforward state flow and task polling for Phase 1.
- Avoid speculative abstractions until the core workflow exists.
- Verify web-side changes with:
  `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope web`
