from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]


def read_doc(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_current_docs_do_not_reintroduce_legacy_review_gate_contract() -> None:
    checks = {
        "docs/01-project-specs/2026-06-29-项目需求与环境准备方案.md": [
            "内容输入 -> 内容理解与抽取 -> RAG 检索参考 -> 工作流生成 -> 人工审核 -> 结果导出",
            "人工审核必须是主链路里的硬节点",
            "审核链路完整，支持通过、修改、驳回和导出",
        ],
        "docs/02-architecture/2026-06-29-项目正式技术方案.md": [
            "内容输入 -> 异步处理 -> 结构化理解 -> 检索参考 -> 工作流结果 -> 人工审核 -> 导出",
            "review_pending -> reviewing -> approved / rejected",
            "审核中可编辑",
        ],
        "docs/04-development-guides/2026-06-30-冷启动与操作员验证清单.md": [
            "review_pending",
            "reviewing",
            "对已批准任务发起 markdown 导出。",
        ],
        "docs/04-development-guides/2026-07-01-AI交接与持续开发工作流.md": [
            "内容输入 -> 异步处理 -> 结构化理解 -> 检索参考 -> 工作流结果 -> 人工审核 -> 导出",
            "审核有没有形成硬门",
            "真审核门",
        ],
    }

    for relative_path, forbidden_phrases in checks.items():
        content = read_doc(relative_path)
        for phrase in forbidden_phrases:
            assert phrase not in content, f"{relative_path} still contains legacy review-gate phrase: {phrase}"
