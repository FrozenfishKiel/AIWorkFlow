# Tests

## Directory Meaning

- `samples`: Realistic sample inputs and fixtures used by tests or manual checks.
- `acceptance`: Repo-root workflow proof for the currently implemented scope.
- `evaluation`: Quality or regression assets used to compare retrieval and workflow behavior over time.

## What "Acceptance" Means Right Now

Acceptance coverage in this repository is intentionally narrow and honest to the code that exists today.

At the moment, root acceptance tests should prove the implemented Phase 1 loop:

- Register a local knowledge document and run real indexing logic.
- Create a task through the public API.
- When password login is enabled, obtain a real operator session first and reuse it across protected API calls.
- Run the actual task pipeline logic across task, retrieval, and workflow stages.
- Assert that the completed pipeline auto-freezes a stable snapshot for downstream use.
- Create and execute export from that stable snapshot.
- Assert that the export artifact is written and downloadable through the protected API, and that visible source attribution survives into the completed task state.

These tests are allowed to simulate async queue boundaries by calling worker or service logic directly after the API has created the queued record. They should not invent unimplemented product features, broader crawl behavior, live broker requirements, or external deployment assumptions.

## Principles

- Unit tests stay close to the module they verify.
- Acceptance tests exercise the real workflow seams that matter for the current shipped scope.
- Evaluation assets support later retrieval and workflow quality review; they are not a substitute for acceptance coverage.

## Evaluation Right Now

`evaluation` 目录现在至少应该承担一件很具体的事：把检索范围和关键命中来源固定成回归样例。

目前它不追求做“大而全评测平台”，而是优先防止这些明显回退：

- `knowledge_domain` 明明传了，但检索又回到全库乱找
- 文件任务又退回到只拿文件名或占位文本做检索
- 明显该命中的核心来源，被后续改动悄悄挤掉

## Placeholder Manual Samples

为了让第一轮人工验证不用等真实业务资料，仓库里现在补了一组占位样本：

- `samples/content-ops/launch-brief.md`

它适合和 `knowledge-base/02-curated-notes/content-ops/` 下那几份占位知识文档搭配使用，先验证主链：

- 索引知识
- 创建任务
- 看理解结果
- 看检索命中
- 看工作流结果
- 看导出与审计记录
