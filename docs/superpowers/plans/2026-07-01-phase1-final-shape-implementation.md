# Phase 1 Final Shape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining five Phase 1 product-shape slices, continuously absorb scattered issues, and leave only two explicit post-Phase-1 items: real audit logging and next-stage model/RAG/auth upgrades.

**Architecture:** Keep Phase 1 inside the existing single-task workflow boundary. Prefer narrow API/schema extensions, reviewer-visible UI improvements, and regression tests over new subsystems. Every slice must close code, tests, and docs together so small issues do not accumulate outside the two approved post-Phase-1 buckets.

**Tech Stack:** `FastAPI`, `SQLModel`, `React`, `TypeScript`, `Vitest`, `pytest`

---

## File Structure

- Modify: `apps/api/app/api/routes_knowledge.py`
- Modify: `apps/api/app/repositories/knowledge_repository.py`
- Modify: `apps/api/app/schemas/knowledge.py`
- Modify: `apps/api/tests/integration/test_tasks_api.py`
- Modify: `apps/web/src/features/knowledge-index/KnowledgeIndexPanel.tsx`
- Modify: `apps/web/src/pages/TaskConsolePage.tsx`
- Modify: `apps/web/src/services/knowledge.ts`
- Modify: `apps/web/src/services/tasks.ts`
- Modify: `apps/web/src/types/knowledge.ts`
- Modify: `apps/web/src/types/task.ts`
- Modify: `apps/web/src/features/task-detail/TaskDetailView.tsx`
- Modify: `apps/web/tests/unit/knowledgeApi.test.ts`
- Modify: `apps/web/tests/unit/reviewApi.test.ts`
- Modify: `apps/web/tests/unit/taskAdapters.test.ts`
- Modify: `README.md`
- Modify: `docs/02-architecture/2026-06-29-项目正式技术方案.md`

## Task 1: Knowledge Detail Visibility

**Files:**
- Modify: `apps/api/app/api/routes_knowledge.py`
- Modify: `apps/api/app/repositories/knowledge_repository.py`
- Modify: `apps/api/app/schemas/knowledge.py`
- Modify: `apps/api/tests/integration/test_tasks_api.py`
- Modify: `apps/web/src/features/knowledge-index/KnowledgeIndexPanel.tsx`
- Modify: `apps/web/src/pages/TaskConsolePage.tsx`
- Modify: `apps/web/src/services/knowledge.ts`
- Modify: `apps/web/src/types/knowledge.ts`
- Modify: `apps/web/tests/unit/knowledgeApi.test.ts`

- [ ] **Step 1: Write failing API and web tests for knowledge detail**

Add API coverage that proves `GET /knowledge/documents/{document_id}` returns richer detail for one document, including document metadata and chunk preview content when indexed. Add web coverage that proves the frontend calls the detail endpoint and understands the richer shape.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
cd D:\Projects\ai-content-production-ops-workflow
D:\Anaconda3\envs\ai-content-ops\python.exe -m pytest apps/api/tests/integration/test_tasks_api.py -q
cd apps/web
npm run test -- --run tests/unit/knowledgeApi.test.ts
```

Expected:
- API test fails because detail payload does not yet include richer document detail
- Web test fails because the frontend types/service do not yet cover the richer shape

- [ ] **Step 3: Implement minimal knowledge detail support**

Implement:
- repository helper to list chunks for a document
- detailed knowledge schema with optional chunk preview
- detail route using the richer schema
- frontend types/service updates for detail records
- knowledge panel support for selecting a document and showing its detail/error/chunk preview

- [ ] **Step 4: Re-run targeted tests to verify green**

Run:

```powershell
cd D:\Projects\ai-content-production-ops-workflow
D:\Anaconda3\envs\ai-content-ops\python.exe -m pytest apps/api/tests/integration/test_tasks_api.py -q
cd apps/web
npm run test -- --run tests/unit/knowledgeApi.test.ts
```

Expected:
- Knowledge API and frontend service tests pass

## Task 2: Export History Refinement

**Files:**
- Modify: `apps/web/src/pages/TaskConsolePage.tsx`
- Modify: `apps/web/src/features/task-detail/TaskDetailView.tsx`
- Modify: `apps/web/src/services/tasks.ts`
- Modify: `apps/web/src/types/task.ts`
- Modify: `apps/web/tests/unit/reviewApi.test.ts`
- Modify: `apps/web/tests/unit/taskAdapters.test.ts`

- [ ] **Step 1: Write failing tests for export history usability**

Add tests that prove:
- completed export jobs expose a frontend-friendly download affordance
- export history can be rendered from normalized job data without depending only on `latestExportJob`

- [ ] **Step 2: Run targeted web tests to verify red**

Run:

```powershell
cd D:\Projects\ai-content-production-ops-workflow\apps\web
npm run test -- --run tests/unit/reviewApi.test.ts tests/unit/taskAdapters.test.ts
```

Expected:
- At least one new assertion fails because export history refinement is not implemented yet

- [ ] **Step 3: Implement minimal export-history improvements**

Implement:
- per-job download affordance for completed jobs
- clearer export status metadata for list/history rendering
- polling refresh based on active jobs in history, not only one latest job

- [ ] **Step 4: Re-run targeted web tests**

Run:

```powershell
cd D:\Projects\ai-content-production-ops-workflow\apps\web
npm run test -- --run tests/unit/reviewApi.test.ts tests/unit/taskAdapters.test.ts
```

Expected:
- Export-related tests pass

## Task 3: Reviewer-Visible Traceability

**Files:**
- Modify: `apps/web/src/features/task-detail/TaskDetailView.tsx`
- Modify: `apps/web/src/pages/TaskConsolePage.tsx`
- Modify: `apps/web/src/types/task.ts`
- Modify: `apps/web/tests/unit/taskAdapters.test.ts`

- [ ] **Step 1: Write failing tests for visible trace/timeline fields**

Add tests for derived UI-facing traceability helpers covering:
- task source visibility
- stage/status summary
- workflow evidence/uncertainty visibility
- export/review state summary

- [ ] **Step 2: Run targeted web tests to verify red**

Run:

```powershell
cd D:\Projects\ai-content-production-ops-workflow\apps\web
npm run test -- --run tests/unit/taskAdapters.test.ts
```

Expected:
- New traceability assertions fail

- [ ] **Step 3: Implement minimal reviewer-visible traceability**

Implement:
- derived task trace/timeline helpers in the frontend type layer
- task detail panels for pipeline trace, review trace, failure/export visibility
- clearer empty/error messaging where reviewer evidence is missing

- [ ] **Step 4: Re-run targeted web tests**

Run:

```powershell
cd D:\Projects\ai-content-production-ops-workflow\apps\web
npm run test -- --run tests/unit/taskAdapters.test.ts
```

Expected:
- Traceability tests pass

## Task 4: Failure-State and Small-Issue Cleanup

**Files:**
- Modify: `apps/web/src/features/knowledge-index/KnowledgeIndexPanel.tsx`
- Modify: `apps/web/src/features/task-detail/TaskDetailView.tsx`
- Modify: `apps/web/src/pages/TaskConsolePage.tsx`
- Modify: `apps/api/tests/integration/test_tasks_api.py`
- Modify: `apps/web/tests/unit/knowledgeApi.test.ts`
- Modify: `apps/web/tests/unit/taskAdapters.test.ts`

- [ ] **Step 1: Write failing tests for failure-state visibility**

Add coverage for:
- knowledge indexing failure detail visibility
- task failure/error message visibility
- empty-state behavior where no chunks/evidence/export artifacts exist yet

- [ ] **Step 2: Run focused tests to confirm failure**

Run:

```powershell
cd D:\Projects\ai-content-production-ops-workflow
D:\Anaconda3\envs\ai-content-ops\python.exe -m pytest apps/api/tests/integration/test_tasks_api.py -q
cd apps/web
npm run test -- --run tests/unit/knowledgeApi.test.ts tests/unit/taskAdapters.test.ts
```

Expected:
- New failure-state expectations fail

- [ ] **Step 3: Implement minimal cleanup line fixes**

Implement only bounded cleanup that supports the five slices:
- clearer failure state copy/fields
- manual refresh hooks where polling is intentionally stopped
- removal of newly discovered scattered UX/API inconsistencies that do not belong in the two post-Phase-1 buckets

- [ ] **Step 4: Re-run focused tests**

Run:

```powershell
cd D:\Projects\ai-content-production-ops-workflow
D:\Anaconda3\envs\ai-content-ops\python.exe -m pytest apps/api/tests/integration/test_tasks_api.py -q
cd apps/web
npm run test -- --run tests/unit/knowledgeApi.test.ts tests/unit/taskAdapters.test.ts
```

Expected:
- Failure-state and cleanup tests pass

## Task 5: Docs and Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/02-architecture/2026-06-29-项目正式技术方案.md`

- [ ] **Step 1: Update docs to match the real final Phase 1 shape**

Document:
- richer knowledge detail visibility
- refined export history/download behavior
- improved reviewer-visible traceability/failure visibility
- explicit statement that only two post-Phase-1 big items remain

- [ ] **Step 2: Run full repository verification**

Run:

```powershell
cd D:\Projects\ai-content-production-ops-workflow
powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope all
```

Expected:
- API tests pass
- web tests pass
- web build passes
- any intentional xfail remains clearly explained

- [ ] **Step 3: Audit leftovers against the approved boundary**

Create a short completion checklist:
- no scattered knowledge/export/reviewer-visibility TODOs remain from this slice
- only two post-Phase-1 buckets remain:
  - real audit logging
  - next-stage model/RAG/auth upgrades
