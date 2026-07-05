# System Report

这份目录用于补 Phase 1 收尾所需的最小系统级测试证据，重点回答三件事：

- 同一商品请求重复提交时，系统是否会创建新的独立 job。
- 主链失败时，API 是否能把 failure reason 和关键 diagnostics 暴露出来。
- 正式联测时，是否能用统一字段查看 provider、top-k、selected hits、weak retrieval、最终状态和导出状态。

## 怎么跑

只跑这次补的高信号测试：

```powershell
cd D:\Projects\ai-content-production-ops-workflow\apps\api
D:\Anaconda3\envs\ai-content-ops\python.exe -m pytest tests/integration/test_system_observability.py tests/evaluation/test_bad_sample_regression.py -q

cd D:\Projects\ai-content-production-ops-workflow
D:\Anaconda3\envs\ai-content-ops\python.exe -m pytest tests/acceptance/test_system_report_acceptance.py -q
```

按仓库统一入口跑 API 范围校验：

```powershell
cd D:\Projects\ai-content-production-ops-workflow
powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope api
```

## 看什么

`integration`

- `test_duplicate_product_content_submissions_create_distinct_jobs`
  - 同 payload 二次提交返回不同 `job.id`
- `test_failed_product_content_job_exposes_diagnostics_and_failure_reason`
  - 失败任务详情里可见 `failure_reason`
  - 同时可见 `generation_provider`、`retrieval_provider`、`retrieval_top_k_requested`、`selected_hit_count`、`weak_retrieval` 等诊断字段

`evaluation`

- `test_bad_product_samples_keep_weak_retrieval_visible_and_outputs_conservative`
  - 坏样本应稳定表现为弱召回或零选中证据
  - 风险提示里要明确暴露“输入信息仍有缺口”和“当前没有命中业务参考资料”这类保守信号

`acceptance`

- `test_system_report_acceptance_captures_success_and_failure_rows`
  - 成功与失败场景都要能整理成统一 report row
  - report row 至少包含：
    - `provider`
    - `top_k`
    - `selected_hits`
    - `weak_retrieval`
    - `final_status`
    - `export_status`
    - `failure_reason`

## Go / No-Go

`Go`

- 三组测试都通过
- 成功场景的 report row 中：
  - `provider` 非空
  - `top_k` 为正整数
  - `selected_hits` 非空
  - `weak_retrieval` 为 `False`
  - `final_status=completed`
  - `export_status=completed`
- 失败场景的 report row 中：
  - `final_status=failed`
  - `failure_reason` 非空
  - `weak_retrieval` 能正确反映失败前的检索质量

`No-Go`

- 重复提交复用了同一个 job
- 失败详情里缺少 `failure_reason` 或关键 diagnostics
- 坏样本没有暴露保守提示，反而表现得像正常高置信成功
- 联测 report row 缺字段，或者成功/失败状态无法统一比较
