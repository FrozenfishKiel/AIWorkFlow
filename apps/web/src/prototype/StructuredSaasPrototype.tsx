import { startTransition, useEffect, useState, type FormEvent } from "react";

import { createExportJob, downloadExportArtifact, fetchExportJob, listExportJobs } from "../services/exports";
import { createProductContentJob, fetchProductContentJob, fetchProductContentJobAuditLogs } from "../services/productContent";
import {
  fetchAuthConfig,
  fetchCurrentUser,
  loginOperator,
  logoutOperator,
  readStoredAuthSession,
} from "../services/auth";
import type { AuthConfig, AuthUser } from "../types/auth";
import type { ExportJobRecord } from "../types/export";
import {
  getJobStatusLabel,
  isJobActive,
  type ProductContentAuditLog,
  type ProductContentJobDetail,
  type ProductInputFormValues,
} from "../types/productContent";
import {
  toProductInputFormValues,
  toPrototypeFormState,
  toPrototypeResultViewModel,
  type PrototypeFormState,
} from "./prototypeContentAdapter";
import { getJobLoadFailureViewState, getStoredJobRecoveryAction } from "../pages/productWorkspaceState";

type Surface = "homepage" | "workspace";
type ResultState = "loading" | "ready";

const POLLING_INTERVAL_MS = 4000;
const ACTIVE_JOB_STORAGE_KEY = "ai-content-ops.prototype.active-job-id";

const DEFAULT_FORM: PrototypeFormState = {
  name: "黑咖啡浓缩液",
  category: "冲调饮品",
  specifications: "30ml*7条\n冷水即溶\n便携小袋装",
  priceRange: "39-49元",
  feature: "冷水即溶\n0蔗糖\n便携提神\n黑咖风味纯粹",
  audience: "通勤族、学生党、需要控糖提神的人群",
  scenarios: "早八通勤\n午后犯困\n加班复习\n出差随身",
  promotion: "夏季提神专题，主打低负担快冲快喝",
  taskDescription: "生成电商卖点文案、详情页文案和种草短文案，重点突出便携提神、冷水即溶和低负担。",
};

function readStoredActiveJobId(): string {
  if (typeof localStorage === "undefined") {
    return "";
  }

  return localStorage.getItem(ACTIVE_JOB_STORAGE_KEY)?.trim() || "";
}

function writeStoredActiveJobId(jobId: string | null): void {
  if (typeof localStorage === "undefined") {
    return;
  }

  if (!jobId) {
    localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
    return;
  }

  localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, jobId);
}

function toExportSummary(exportJob: ExportJobRecord | null) {
  if (!exportJob) {
    return null;
  }

  return {
    id: exportJob.id,
    status: exportJob.status,
    exportType: exportJob.export_type,
    filePath: exportJob.file_path,
  } as const;
}

function BrandMark({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="proto-brand" onClick={onClick}>
      <span className="proto-brand__cube" />
      <span className="proto-brand__text">
        <strong>智绘商拍</strong>
        <span>电商商品内容生产系统</span>
      </span>
    </button>
  );
}

function PrototypeHeader({
  authUser,
  onHome,
  onWorkspace,
}: {
  authUser: AuthUser | null;
  onHome: () => void;
  onWorkspace: () => void;
}) {
  return (
    <header className="site-header">
      <BrandMark onClick={onHome} />
      <div className="site-actions">
        {authUser ? <span className="site-user">当前操作者：{authUser.username}</span> : null}
        <button type="button" className="primary-button primary-button--tight" onClick={onWorkspace}>
          进入工作台
        </button>
      </div>
    </header>
  );
}

function HeroPreviewCard() {
  return (
    <section className="hero-preview">
      <div className="hero-preview__top">
        <span className="hero-preview__eyebrow">结果预览</span>
        <span className="hero-preview__status">已按品牌口径收口</span>
      </div>

      <article className="hero-preview__panel">
        <p className="hero-preview__label">商品理解摘要</p>
        <h3>先把商品说对，再把文案写顺</h3>
        <p>主链会先消化商品事实、场景、人群和表达边界，再组织三类可继续编辑的内容初稿。</p>
      </article>

      <div className="hero-preview__grid">
        <article className="hero-preview__panel hero-preview__panel--compact">
          <p className="hero-preview__label">卖点文案</p>
          <ul>
            <li>先讲用户能感知的利益点，不堆参数词。</li>
            <li>把通勤、排队、换季这类场景直接带进表达里。</li>
          </ul>
        </article>
        <article className="hero-preview__panel hero-preview__panel--compact">
          <p className="hero-preview__label">种草短文案</p>
          <p>输出不会假装一步到终稿，而是交付一版能继续编辑、能快速带走的真实底稿。</p>
        </article>
      </div>
    </section>
  );
}

function CapabilityStrip() {
  const items = ["固定业务参考", "三类初稿同屏输出", "生成依据单独查看", "支持结果导出"];

  return (
    <div className="capability-strip">
      {items.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </div>
  );
}

function FeatureStrip() {
  const features = [
    {
      title: "先理解商品，再组织内容",
      text: "不是直接吐文案，而是先把商品任务理解清楚，再往下生成。",
    },
    {
      title: "固定资料直接参与生成",
      text: "品牌口径、平台表达和历史优稿参考会一起参与这一轮内容起稿。",
    },
    {
      title: "结果就是可继续编辑的初稿",
      text: "系统交付的是卖点文案、详情页文案和种草短文案，不是假装一步出终稿。",
    },
    {
      title: "把生成依据单独整理出来",
      text: "主结果区只放用户真正在意的内容结果，系统依据走单独入口查看。",
    },
  ];

  return (
    <section className="feature-strip">
      {features.map((feature) => (
        <article className="feature-strip__item" key={feature.title}>
          <span className="feature-strip__icon" />
          <div className="feature-strip__copy">
            <h3>{feature.title}</h3>
            <p>{feature.text}</p>
          </div>
        </article>
      ))}
    </section>
  );
}

function WorkspaceSidebar({ workspaceStatus }: { workspaceStatus: string }) {
  return (
    <aside className="workspace-sidebar">
      <div className="workspace-sidebar__brand">
        <span className="workspace-sidebar__cube" />
        <strong>智绘商拍</strong>
      </div>

      <div className="workspace-sidebar__nav" aria-label="当前工作区">
        <span>工作台</span>
        <span className="workspace-sidebar__nav-item workspace-sidebar__nav-item--active">内容生成</span>
      </div>

      <div className="workspace-sidebar__note">
        <small>当前状态</small>
        <strong>{workspaceStatus}</strong>
        <span>生成完成后可直接在右侧继续查看与导出。</span>
      </div>
    </aside>
  );
}

function LoginCard({
  authLoading,
  authSubmitting,
  authError,
  onSubmit,
}: {
  authLoading: boolean;
  authSubmitting: boolean;
  authError: string;
  onSubmit: (values: { username: string; password: string }) => Promise<void> | void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  return (
    <section className="workspace-card input-card">
      <div className="workspace-card__header">
        <h3>操作者登录</h3>
        <p>当前环境启用了最小登录边界，先登录再开始生成商品内容。</p>
      </div>

      <form
        className="workspace-card__body login-form"
        onSubmit={(event) => {
          event.preventDefault();
          void onSubmit({ username: username.trim(), password });
        }}
      >
        <label className="field-input">
          <span>用户名</span>
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>

        <label className="field-input">
          <span>密码</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>

        {authError ? <p className="workspace-error">{authError}</p> : null}

        <button
          type="submit"
          className="primary-button primary-button--block"
          disabled={authLoading || authSubmitting || !username.trim() || !password}
        >
          {authSubmitting ? "登录中..." : "登录"}
        </button>
      </form>
    </section>
  );
}

function ProductFields({
  formState,
  readOnly,
  onFieldChange,
}: {
  formState: PrototypeFormState;
  readOnly: boolean;
  onFieldChange: <K extends keyof PrototypeFormState>(field: K, value: PrototypeFormState[K]) => void;
}) {
  return (
    <div className="form-grid">
      <label className="field-input">
        <span>商品名称</span>
        <input value={formState.name} readOnly={readOnly} onChange={(event) => onFieldChange("name", event.target.value)} />
      </label>

      <label className="field-input">
        <span>商品类目</span>
        <input value={formState.category} readOnly={readOnly} onChange={(event) => onFieldChange("category", event.target.value)} />
      </label>

      <label className="field-input field-input--full">
        <span>规格参数</span>
        <textarea
          value={formState.specifications}
          readOnly={readOnly}
          onChange={(event) => onFieldChange("specifications", event.target.value)}
          rows={4}
        />
      </label>

      <label className="field-input">
        <span>价格带</span>
        <input value={formState.priceRange} readOnly={readOnly} onChange={(event) => onFieldChange("priceRange", event.target.value)} />
      </label>

      <label className="field-input">
        <span>目标人群</span>
        <input value={formState.audience} readOnly={readOnly} onChange={(event) => onFieldChange("audience", event.target.value)} />
      </label>

      <label className="field-input field-input--full">
        <span>核心卖点</span>
        <textarea value={formState.feature} readOnly={readOnly} onChange={(event) => onFieldChange("feature", event.target.value)} rows={4} />
      </label>

      <label className="field-input field-input--full">
        <span>使用场景</span>
        <textarea value={formState.scenarios} readOnly={readOnly} onChange={(event) => onFieldChange("scenarios", event.target.value)} rows={4} />
      </label>

      <label className="field-input field-input--full">
        <span>活动信息</span>
        <input value={formState.promotion} readOnly={readOnly} onChange={(event) => onFieldChange("promotion", event.target.value)} />
      </label>

      <label className="field-input field-input--full">
        <span>任务描述</span>
        <textarea
          value={formState.taskDescription}
          readOnly={readOnly}
          onChange={(event) => onFieldChange("taskDescription", event.target.value)}
          rows={4}
        />
      </label>
    </div>
  );
}

function EmptyResultState({ message }: { message: string }) {
  return (
    <div className="result-empty">
      <h4>当前结果</h4>
      <p>{message}</p>
    </div>
  );
}

function ResultCards({
  job,
  exportLoading,
  exportJob,
  onExportMarkdown,
  onExportStructuredText,
  onDownloadExport,
}: {
  job: ProductContentJobDetail;
  exportLoading: boolean;
  exportJob: ReturnType<typeof toExportSummary> | null;
  onExportMarkdown: () => void;
  onExportStructuredText: () => void;
  onDownloadExport: () => void;
}) {
  const viewModel = toPrototypeResultViewModel(job);

  return (
    <div className="result-stack">
      {viewModel.inputAlerts.length ? (
        <article className="result-card result-card--alert">
          <p className="result-card__eyebrow">输入提醒</p>
          <ul className="result-list">
            {viewModel.inputAlerts.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      ) : null}

      <article className="result-card result-card--brief">
        <p className="result-card__eyebrow">商品理解摘要</p>
        <h4>{viewModel.productBriefSummary}</h4>
        {viewModel.primaryValuePoints.length ? (
          <div className="chip-row">
            {viewModel.primaryValuePoints.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        ) : null}
        <p className="result-card__meta">目标人群：{viewModel.targetAudience}</p>
        <p className="result-card__meta">
          使用场景：{viewModel.useScenarios.length ? viewModel.useScenarios.join("、") : "未填写"}
        </p>
      </article>

      <div className="result-grid">
        <article className="result-card">
          <p className="result-card__eyebrow">电商卖点文案</p>
          {viewModel.sellingPoints.length ? (
            <ul className="result-list">
              {viewModel.sellingPoints.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>当前没有卖点文案结果。</p>
          )}
        </article>

        <article className="result-card">
          <p className="result-card__eyebrow">商品详情页文案</p>
          <p>{viewModel.detailPageCopy || "当前没有详情页文案结果。"}</p>
        </article>

        <article className="result-card">
          <p className="result-card__eyebrow">小红书 / 种草短文案</p>
          <p>{viewModel.socialSeedCopy || "当前没有种草短文案结果。"}</p>
        </article>

        <article className="result-card">
          <p className="result-card__eyebrow">风险提醒</p>
          {viewModel.riskNotes.length ? (
            <ul className="result-list">
              {viewModel.riskNotes.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>当前没有额外风险提醒。</p>
          )}
        </article>
      </div>

      <article className="result-card">
        <div className="result-card__header">
          <div>
            <p className="result-card__eyebrow">导出交付</p>
            <h4>当前结果可继续导出</h4>
          </div>
          <div className="workspace-actions">
            <button type="button" className="ghost-button ghost-button--tiny" disabled={exportLoading} onClick={onExportMarkdown}>
              导出 Markdown
            </button>
            <button
              type="button"
              className="ghost-button ghost-button--tiny"
              disabled={exportLoading}
              onClick={onExportStructuredText}
            >
              导出结构化文本
            </button>
            {exportJob?.status === "completed" ? (
              <button type="button" className="ghost-button ghost-button--tiny" onClick={onDownloadExport}>
                下载导出文件
              </button>
            ) : null}
          </div>
        </div>
        <p>文案主结果留在工作台里查看，系统理解、参考资料、卖点提炼和风险提示放到“生成依据”里单独展开。</p>
      </article>
    </div>
  );
}

export function EvidenceDrawer({
  job,
  open,
  onClose,
}: {
  job: ProductContentJobDetail | null;
  open: boolean;
  onClose: () => void;
}) {
  if (!open || !job) {
    return null;
  }

  const viewModel = toPrototypeResultViewModel(job);
  const riskItems = [...viewModel.inputAlerts, ...viewModel.riskNotes];

  return (
    <aside className="evidence-drawer" aria-label="生成依据">
      <div className="evidence-drawer__panel">
        <div className="evidence-drawer__header">
          <div>
            <p className="result-card__eyebrow">生成依据</p>
            <h3>这次结果的系统依据</h3>
          </div>
          <button type="button" className="ghost-button ghost-button--tiny" onClick={onClose}>
            收起
          </button>
        </div>

        <div className="evidence-drawer__grid">
          <article className="result-card">
            <p className="result-card__eyebrow">系统理解</p>
            <h4>{viewModel.productBriefSummary}</h4>
            <p className="result-card__meta">目标人群：{viewModel.targetAudience}</p>
            <p className="result-card__meta">
              使用场景：{viewModel.useScenarios.length ? viewModel.useScenarios.join("、") : "未填写"}
            </p>
          </article>

          <article className="result-card">
            <p className="result-card__eyebrow">参考资料</p>
            {viewModel.references.length ? (
              <div className="reference-grid">
                {viewModel.references.map((item) => (
                  <article className="reference-card" key={`${item.title}-${item.reason}`}>
                    <strong>{item.title}</strong>
                    <p className="reference-card__reason">{item.reason}</p>
                    <p>{item.snippet}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p>当前没有命中可展示的资料引用。</p>
            )}
          </article>

          <article className="result-card">
            <p className="result-card__eyebrow">卖点提炼</p>
            <div className="evidence-stack">
              <p><strong>主打方向：</strong>{viewModel.sellingStrategy.primaryAngle}</p>
              <p><strong>补充方向：</strong>{viewModel.sellingStrategy.supportingAngles.length ? viewModel.sellingStrategy.supportingAngles.join("、") : "暂无"}</p>
              <p><strong>场景聚焦：</strong>{viewModel.sellingStrategy.scenarioFocus.length ? viewModel.sellingStrategy.scenarioFocus.join("、") : "暂无"}</p>
              <p><strong>表达约束：</strong>{viewModel.sellingStrategy.expressionGuardrails.length ? viewModel.sellingStrategy.expressionGuardrails.join("；") : "暂无"}</p>
            </div>
          </article>

          <article className="result-card">
            <p className="result-card__eyebrow">风险提示</p>
            {riskItems.length ? (
              <ul className="result-list">
                {riskItems.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p>当前没有额外风险提示。</p>
            )}
          </article>
        </div>
      </div>
    </aside>
  );
}

export function DiagnosticsDrawer({
  job,
  open,
  isLoading,
  auditLogs,
  exportJobs,
  onClose,
}: {
  job: ProductContentJobDetail | null;
  open: boolean;
  isLoading: boolean;
  auditLogs: ProductContentAuditLog[];
  exportJobs: ExportJobRecord[];
  onClose: () => void;
}) {
  if (!open || !job) {
    return null;
  }

  const diagnostics = job.diagnostics;
  const latestExportJob = exportJobs[0] ?? null;

  return (
    <aside className="evidence-drawer" aria-label="诊断后台">
      <div className="evidence-drawer__panel">
        <div className="evidence-drawer__header">
          <div>
            <p className="result-card__eyebrow">诊断后台</p>
            <h3>这次任务的系统级诊断信息</h3>
          </div>
          <button type="button" className="ghost-button ghost-button--tiny" onClick={onClose}>
            收起
          </button>
        </div>

        {isLoading ? (
          <div className="result-loading">
            <div className="result-loading__line result-loading__line--wide" />
            <div className="result-loading__block" />
          </div>
        ) : null}

        {!isLoading ? (
          <div className="evidence-drawer__grid">
            <article className="result-card">
              <p className="result-card__eyebrow">链路概览</p>
              <div className="diagnostic-grid">
                <p><strong>任务状态：</strong>{getJobStatusLabel(job.status)}</p>
                <p><strong>当前阶段：</strong>{job.currentStage}</p>
                <p><strong>生成 provider：</strong>{diagnostics?.generationProvider || "未记录"}</p>
                <p><strong>检索 provider：</strong>{diagnostics?.retrievalProvider || "未记录"}</p>
                <p><strong>召回 top-k：</strong>{diagnostics?.retrievalTopKRequested || 0}</p>
                <p><strong>实际返回：</strong>{diagnostics?.retrievalTopKEffective || 0}</p>
                <p><strong>候选命中：</strong>{diagnostics?.candidateHitCount || 0}</p>
                <p><strong>最终选中：</strong>{diagnostics?.selectedHitCount || 0}</p>
                <p><strong>弱检索：</strong>{diagnostics?.weakRetrieval ? "是" : "否"}</p>
                <p><strong>去重移除：</strong>{diagnostics?.duplicateHitsRemoved || 0}</p>
              </div>
              {diagnostics?.retrievalQuery ? (
                <div className="preview-field-list__item">
                  <span>本轮检索 query</span>
                  <p>{diagnostics.retrievalQuery}</p>
                </div>
              ) : null}
              {diagnostics?.failureReason || job.errorMessage ? (
                <div className="preview-field-list__item">
                  <span>失败原因</span>
                  <p>{diagnostics?.failureReason || job.errorMessage}</p>
                </div>
              ) : null}
            </article>

            <article className="result-card">
              <p className="result-card__eyebrow">召回候选</p>
              {job.retrievalCandidates.length ? (
                <div className="reference-grid">
                  {job.retrievalCandidates.map((item) => (
                    <article className="reference-card" key={`${item.sourceId}-${item.rank ?? item.title}`}>
                      <strong>
                        {item.rank ? `#${item.rank} ` : ""}
                        {item.title}
                        {item.selected ? " · 已入选" : ""}
                      </strong>
                      <p className="reference-card__reason">{item.reason}</p>
                      {typeof item.score === "number" ? <p>排序分：{item.score.toFixed(2)}</p> : null}
                      {item.matchedTerms?.length ? <p>命中词：{item.matchedTerms.join("、")}</p> : null}
                      {item.matchedPhrases?.length ? <p>命中短语：{item.matchedPhrases.join("、")}</p> : null}
                      <p>{item.snippet}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p>当前没有可展示的召回候选。</p>
              )}
            </article>

            <article className="result-card">
              <p className="result-card__eyebrow">导出状态</p>
              {latestExportJob ? (
                <div className="evidence-stack">
                  <p><strong>最近一次导出：</strong>{latestExportJob.export_type}</p>
                  <p><strong>状态：</strong>{latestExportJob.status}</p>
                  {latestExportJob.file_path ? <p><strong>产物路径：</strong>{latestExportJob.file_path}</p> : null}
                  {latestExportJob.error_message ? <p><strong>失败原因：</strong>{latestExportJob.error_message}</p> : null}
                </div>
              ) : (
                <p>当前还没有导出记录。</p>
              )}
            </article>

            <article className="result-card">
              <p className="result-card__eyebrow">审计时间线</p>
              {auditLogs.length ? (
                <ul className="result-list">
                  {auditLogs.map((item) => (
                    <li key={item.id}>
                      <strong>{item.eventType}</strong> · {item.outcome === "failure" ? "失败" : "成功"} · {item.summary}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>当前还没有审计时间线。</p>
              )}
            </article>

            <article className="result-card">
              <p className="result-card__eyebrow">处理轨迹</p>
              {job.processingTrace.length ? (
                <ul className="result-list">
                  {job.processingTrace.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p>当前还没有处理轨迹。</p>
              )}
            </article>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function WorkspaceCanvas({
  authReady,
  authLoading,
  needsLogin,
  authSubmitting,
  authError,
  formState,
  resultState,
  workspaceStatus,
  pageError,
  job,
  jobLoading,
  exportLoading,
  exportJob,
  evidenceOpen,
  diagnosticsOpen,
  diagnosticsLoading,
  auditLogs,
  exportJobs,
  onFieldChange,
  onLogin,
  onSubmit,
  onOpenEvidence,
  onCloseEvidence,
  onOpenDiagnostics,
  onCloseDiagnostics,
  onExportMarkdown,
  onExportStructuredText,
  onDownloadExport,
}: {
  authReady: boolean;
  authLoading: boolean;
  needsLogin: boolean;
  authSubmitting: boolean;
  authError: string;
  formState: PrototypeFormState;
  resultState: ResultState;
  workspaceStatus: string;
  pageError: string;
  job: ProductContentJobDetail | null;
  jobLoading: boolean;
  exportLoading: boolean;
  exportJob: ReturnType<typeof toExportSummary> | null;
  evidenceOpen: boolean;
  diagnosticsOpen: boolean;
  diagnosticsLoading: boolean;
  auditLogs: ProductContentAuditLog[];
  exportJobs: ExportJobRecord[];
  onFieldChange: <K extends keyof PrototypeFormState>(field: K, value: PrototypeFormState[K]) => void;
  onLogin: (values: { username: string; password: string }) => Promise<void> | void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onOpenEvidence: () => void;
  onCloseEvidence: () => void;
  onOpenDiagnostics: () => void;
  onCloseDiagnostics: () => void;
  onExportMarkdown: () => void;
  onExportStructuredText: () => void;
  onDownloadExport: () => void;
}) {
  return (
    <section className="workspace-canvas">
      <WorkspaceSidebar workspaceStatus={workspaceStatus} />

      <div className="workspace-stage">
        <div className="workspace-stage__header">
          <div>
            <p className="workspace-stage__eyebrow">主流程</p>
            <h3>输入商品任务，直接产出可继续编辑的内容初稿</h3>
          </div>
          <span className="workspace-stage__status">{workspaceStatus}</span>
        </div>

        {pageError ? <p className="workspace-error">{pageError}</p> : null}

        <div className="workspace-stage__main">
          {!authReady || authLoading ? (
            <section className="workspace-card input-card">
              <div className="workspace-card__header">
                <h3>连接工作台</h3>
                <p>正在确认当前登录方式与工作台权限，请稍候。</p>
              </div>
            </section>
          ) : needsLogin ? (
            <LoginCard
              authLoading={authLoading}
              authSubmitting={authSubmitting}
              authError={authError}
              onSubmit={onLogin}
            />
          ) : (
            <form className="workspace-card input-card" onSubmit={onSubmit}>
              <div className="workspace-card__header">
                <h3>输入商品任务</h3>
                <p>围绕商品信息和一句任务描述，把这一轮内容生成需求交给系统。</p>
              </div>

              <div className="workspace-card__body">
                <ProductFields formState={formState} readOnly={false} onFieldChange={onFieldChange} />
              </div>

              <div className="workspace-card__footer">
                <button type="submit" className="primary-button primary-button--block" disabled={authLoading}>
                  {resultState === "loading" ? "生成中..." : "生成商品内容初稿"}
                </button>
              </div>
            </form>
          )}

          <section className="workspace-card output-card">
            <div className="workspace-card__header workspace-card__header--row">
              <div>
                <h3>当前结果</h3>
                <p>这里聚焦展示用户真正要带走的内容结果，系统依据放到单独入口查看。</p>
              </div>
              {job ? (
                <div className="workspace-actions">
                  <button type="button" className="ghost-button ghost-button--tiny" onClick={onOpenEvidence}>
                    查看生成依据
                  </button>
                  <button type="button" className="ghost-button ghost-button--tiny" onClick={onOpenDiagnostics}>
                    诊断后台
                  </button>
                </div>
              ) : null}
            </div>

            {resultState === "loading" || jobLoading ? (
              <div className="result-loading">
                <div className="result-loading__line result-loading__line--wide" />
                <div className="result-loading__line" />
                <div className="result-loading__line" />
                <div className="result-loading__block" />
                <div className="result-loading__block" />
              </div>
            ) : job ? (
              <ResultCards
                job={job}
                exportLoading={exportLoading}
                exportJob={exportJob}
                onExportMarkdown={onExportMarkdown}
                onExportStructuredText={onExportStructuredText}
                onDownloadExport={onDownloadExport}
              />
            ) : (
              <EmptyResultState message="提交商品任务后，当前结果会在这里自动刷新。" />
            )}
          </section>
        </div>
      </div>

      <EvidenceDrawer job={job} open={evidenceOpen} onClose={onCloseEvidence} />
      <DiagnosticsDrawer
        job={job}
        open={diagnosticsOpen}
        isLoading={diagnosticsLoading}
        auditLogs={auditLogs}
        exportJobs={exportJobs}
        onClose={onCloseDiagnostics}
      />
    </section>
  );
}

function Homepage({
  authLoading,
  onEnterWorkspace,
}: {
  authLoading: boolean;
  onEnterWorkspace: () => void;
}) {
  return (
    <main className="homepage-shell">
      <section className="home-hero">
        <div className="home-hero__copy">
          <span className="eyebrow-pill">AI 驱动的电商内容生产引擎</span>
          <h1>让商品内容起稿，从零散经验变成稳定流程</h1>
          <p>
            智绘商拍聚焦商品内容生产主链，不做生图，不堆花哨模块，只把商品理解、资料利用、文案生成、风险提醒和结果导出这件事做顺。
          </p>
          <div className="hero-actions">
            <button type="button" className="primary-button" onClick={onEnterWorkspace} disabled={authLoading}>
              进入工作台
            </button>
          </div>
          <CapabilityStrip />
        </div>

        <HeroPreviewCard />
      </section>

      <FeatureStrip />
    </main>
  );
}

function WorkspaceSurface(props: Parameters<typeof WorkspaceCanvas>[0]) {
  return (
    <main className="workspace-page">
      <WorkspaceCanvas {...props} />
    </main>
  );
}

export function StructuredSaasPrototype() {
  const [surface, setSurface] = useState<Surface>("homepage");
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [authError, setAuthError] = useState("");
  const [job, setJob] = useState<ProductContentJobDetail | null>(null);
  const [activeJobId, setActiveJobId] = useState("");
  const [jobLoading, setJobLoading] = useState(false);
  const [resultState, setResultState] = useState<ResultState>("ready");
  const [formState, setFormState] = useState<PrototypeFormState>(DEFAULT_FORM);
  const [pageError, setPageError] = useState("");
  const [exportLoading, setExportLoading] = useState(false);
  const [latestExportJob, setLatestExportJob] = useState<ExportJobRecord | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [auditLogs, setAuditLogs] = useState<ProductContentAuditLog[]>([]);
  const [exportHistory, setExportHistory] = useState<ExportJobRecord[]>([]);

  const authReady = authConfig !== null;
  const requiresPasswordLogin = authConfig?.auth_mode === "password_login";
  const needsLogin = authReady && requiresPasswordLogin && !authUser;
  const workspaceStatus = authLoading
    ? "正在连接服务"
    : needsLogin
      ? "等待登录"
      : activeJobId
        ? job && isJobActive(job.status)
          ? getJobStatusLabel(job.status)
          : "本轮结果已连接"
        : "准备开始";

  function switchSurface(next: Surface) {
    startTransition(() => {
      setSurface(next);
    });
  }

  function updateField<K extends keyof PrototypeFormState>(field: K, value: PrototypeFormState[K]) {
    setFormState((current) => ({ ...current, [field]: value }));
  }

  async function loadJob(jobId: string, options?: { silent?: boolean }) {
    if (!jobId) {
      return;
    }

    if (!options?.silent) {
      setJobLoading(true);
    }

    try {
      const nextJob = await fetchProductContentJob(jobId);
      setJob(nextJob);
      setFormState(toPrototypeFormState(nextJob));
      setActiveJobId(String(nextJob.id));
      writeStoredActiveJobId(String(nextJob.id));
      setResultState(isJobActive(nextJob.status) ? "loading" : "ready");
    } catch (error) {
      const recoveryAction = getJobLoadFailureViewState(error);
      if (recoveryAction.clearStoredJob) {
        writeStoredActiveJobId(null);
        setActiveJobId("");
        setJob(null);
      }
      setResultState(recoveryAction.nextResultState);
      setPageError(recoveryAction.message || "");
    } finally {
      if (!options?.silent) {
        setJobLoading(false);
      }
    }
  }

  async function bootstrapPage() {
    setAuthLoading(true);

    try {
      const config = await fetchAuthConfig();
      setAuthConfig(config);
      let hasValidatedSession = false;

      if (config.auth_mode === "password_login") {
        const storedSession = readStoredAuthSession();
        if (storedSession?.access_token) {
          try {
            const currentUser = await fetchCurrentUser();
            setAuthUser(currentUser);
            hasValidatedSession = true;
          } catch {
            logoutOperator();
            setAuthUser(null);
          }
        }
      }

      const storedJobId = readStoredActiveJobId();
      const canRestoreStoredJob = config.auth_mode !== "password_login" || hasValidatedSession;
      if (storedJobId && canRestoreStoredJob) {
        await loadJob(storedJobId);
      } else if (storedJobId && config.auth_mode === "password_login") {
        writeStoredActiveJobId(null);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "连接服务失败。";
      setPageError(message);
    } finally {
      setAuthLoading(false);
    }
  }

  useEffect(() => {
    void bootstrapPage();
  }, []);

  useEffect(() => {
    if (!activeJobId || !job || !isJobActive(job.status)) {
      return;
    }

    const timer = window.setInterval(() => {
      void loadJob(activeJobId, { silent: true });
    }, POLLING_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [activeJobId, job]);

  useEffect(() => {
    if (!latestExportJob || latestExportJob.status === "completed" || latestExportJob.status === "failed") {
      return;
    }

    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const refreshed = await fetchExportJob(latestExportJob.id);
          setLatestExportJob(refreshed);
        } catch (error) {
          const message = error instanceof Error ? error.message : "刷新导出状态失败。";
          setPageError(message);
        }
      })();
    }, POLLING_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [latestExportJob]);

  async function handleLogin(values: { username: string; password: string }) {
    setAuthSubmitting(true);
    setAuthError("");
    setPageError("");

    try {
      const session = await loginOperator(values);
      setAuthUser({
        username: session.username,
        auth_mode: session.auth_mode,
        expires_at: session.expires_at,
      });
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "登录失败。");
    } finally {
      setAuthSubmitting(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPageError("");
    setLatestExportJob(null);
    setResultState("loading");
    setEvidenceOpen(false);
    setDiagnosticsOpen(false);
    setAuditLogs([]);
    setExportHistory([]);

    try {
      const payload: ProductInputFormValues = toProductInputFormValues(formState);
      const jobId = await createProductContentJob(payload);
      setActiveJobId(jobId);
      writeStoredActiveJobId(jobId);
      await loadJob(jobId);
      switchSurface("workspace");
    } catch (error) {
      setResultState("ready");
      const message = error instanceof Error ? error.message : "创建商品内容任务失败。";
      setPageError(message);
    }
  }

  async function handleExport(exportType: "markdown" | "structured_text") {
    const exportTaskId = job?.id || activeJobId;
    if (!exportTaskId) {
      return;
    }

    setExportLoading(true);
    setPageError("");

    try {
      const exportJob = await createExportJob({
        taskId: exportTaskId,
        exportType,
      });
      setLatestExportJob(exportJob);
    } catch (error) {
      const message = error instanceof Error ? error.message : "创建导出任务失败。";
      setPageError(message);
    } finally {
      setExportLoading(false);
    }
  }

  async function handleDownloadExport() {
    if (!latestExportJob || latestExportJob.status !== "completed") {
      return;
    }

    try {
      const blob = await downloadExportArtifact(latestExportJob.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      const extension = latestExportJob.export_type === "markdown" ? "md" : "txt";
      link.href = url;
      link.download = `商品内容初稿-${latestExportJob.id}.${extension}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      const message = error instanceof Error ? error.message : "下载导出文件失败。";
      setPageError(message);
    }
  }

  async function handleOpenDiagnostics() {
    if (!job) {
      return;
    }

    setDiagnosticsOpen(true);
    setDiagnosticsLoading(true);
    try {
      const [nextAuditLogs, nextExportJobs] = await Promise.all([
        fetchProductContentJobAuditLogs(job.id),
        listExportJobs(job.id),
      ]);
      setAuditLogs(nextAuditLogs);
      setExportHistory(nextExportJobs);
    } catch (error) {
      const message = error instanceof Error ? error.message : "加载诊断信息失败。";
      setPageError(message);
    } finally {
      setDiagnosticsLoading(false);
    }
  }

  return (
    <div className="prototype-shell">
      <PrototypeHeader authUser={authUser} onHome={() => switchSurface("homepage")} onWorkspace={() => switchSurface("workspace")} />
      {surface === "homepage" ? (
        <Homepage authLoading={authLoading} onEnterWorkspace={() => switchSurface("workspace")} />
      ) : (
        <WorkspaceSurface
          authReady={authReady}
          authLoading={authLoading}
          needsLogin={needsLogin}
          authSubmitting={authSubmitting}
          authError={authError}
          formState={formState}
          resultState={resultState}
          workspaceStatus={workspaceStatus}
          pageError={pageError}
          job={job}
          jobLoading={jobLoading}
          exportLoading={exportLoading}
          exportJob={toExportSummary(latestExportJob)}
          evidenceOpen={evidenceOpen}
          diagnosticsOpen={diagnosticsOpen}
          diagnosticsLoading={diagnosticsLoading}
          auditLogs={auditLogs}
          exportJobs={exportHistory}
          onFieldChange={updateField}
          onLogin={handleLogin}
          onSubmit={handleSubmit}
          onOpenEvidence={() => setEvidenceOpen(true)}
          onCloseEvidence={() => setEvidenceOpen(false)}
          onOpenDiagnostics={() => void handleOpenDiagnostics()}
          onCloseDiagnostics={() => setDiagnosticsOpen(false)}
          onExportMarkdown={() => void handleExport("markdown")}
          onExportStructuredText={() => void handleExport("structured_text")}
          onDownloadExport={() => void handleDownloadExport()}
        />
      )}
    </div>
  );
}
