import { startTransition, useEffect, useState, type FormEvent } from "react";

import { createExportJob, downloadExportArtifact, fetchExportJob } from "../services/exports";
import { createProductContentJob, fetchProductContentJob } from "../services/productContent";
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
  type ProductContentJobDetail,
  type ProductInputFormValues,
} from "../types/productContent";
import {
  toProductInputFormValues,
  toPrototypeResultViewModel,
  type PrototypeFormState,
} from "./prototypeContentAdapter";

type Surface = "homepage" | "workspace";
type ResultState = "loading" | "ready";
type ResultTab = "全部" | "商品理解" | "卖点文案" | "详情页文案" | "种草短文案" | "风险提醒" | "参考依据";

const OUTPUT_TABS: ResultTab[] = ["全部", "商品理解", "卖点文案", "详情页文案", "种草短文案", "风险提醒", "参考依据"];
const POLLING_INTERVAL_MS = 4000;
const ACTIVE_JOB_STORAGE_KEY = "ai-content-ops.prototype.active-job-id";

const DEFAULT_FORM: PrototypeFormState = {
  name: "氨基酸净澈洁面乳",
  category: "个护清洁",
  specifications: "150g\n氨基酸配方\n敏感肌可用",
  priceRange: "79-99 元",
  feature: "温和净润\n泡沫细腻\n清洁后不紧绷",
  audience: "18-35 岁女性，关注温和清洁与肌肤舒缓",
  scenarios: "日常洁面\n换季维稳\n早晚护肤",
  promotion: "夏季焕肤专题，主打温和净澈",
  taskDescription: "生成电商卖点文案、详情页文案和小红书种草短文案。",
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
        <button type="button" className="ghost-button ghost-button--tight" onClick={onWorkspace}>
          {authUser ? "查看结果" : "登录"}
        </button>
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
        <h3>温和清洁、净润肤感、适合日常反复使用</h3>
        <p>这是一款强调温和清洁与舒缓肤感的洁面产品，适合以成分安心感和日常使用体验为主线展开表达。</p>
      </article>

      <div className="hero-preview__grid">
        <article className="hero-preview__panel hero-preview__panel--compact">
          <p className="hero-preview__label">卖点文案</p>
          <ul>
            <li>氨基酸净澈配方，温和带走油脂与残留，不打扰肌肤舒适感。</li>
            <li>细腻泡沫快速铺开，清洁过程更柔和，敏感时刻也能安心使用。</li>
          </ul>
        </article>
        <article className="hero-preview__panel hero-preview__panel--compact">
          <p className="hero-preview__label">种草短文案</p>
          <p>最近在用这支氨基酸洁面乳，泡沫很细，洗完不是那种猛地拔干的感觉。</p>
        </article>
      </div>
    </section>
  );
}

function CapabilityStrip() {
  const items = ["固定业务参考", "三类初稿同屏输出", "风险提醒与参考依据", "支持结果导出"];

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
      title: "把风险和依据留在结果旁边",
      text: "方便运营直接判断、继续修改、再导出，不需要来回切换页面。",
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

      <nav className="workspace-sidebar__nav">
        <span>工作台</span>
        <span className="workspace-sidebar__nav-item workspace-sidebar__nav-item--active">内容生成</span>
      </nav>

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
            <p className="result-card__eyebrow">参考依据</p>
            <h4>当前命中的参考资料</h4>
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
    </div>
  );
}

function WorkspaceCanvas({
  preview,
  authLoading,
  needsLogin,
  authSubmitting,
  authError,
  formState,
  resultState,
  selectedTab,
  workspaceStatus,
  pageError,
  job,
  jobLoading,
  exportLoading,
  exportJob,
  onFieldChange,
  onTabChange,
  onLogin,
  onSubmit,
  onExportMarkdown,
  onExportStructuredText,
  onDownloadExport,
}: {
  preview: boolean;
  authLoading: boolean;
  needsLogin: boolean;
  authSubmitting: boolean;
  authError: string;
  formState: PrototypeFormState;
  resultState: ResultState;
  selectedTab: ResultTab;
  workspaceStatus: string;
  pageError: string;
  job: ProductContentJobDetail | null;
  jobLoading: boolean;
  exportLoading: boolean;
  exportJob: ReturnType<typeof toExportSummary> | null;
  onFieldChange: <K extends keyof PrototypeFormState>(field: K, value: PrototypeFormState[K]) => void;
  onTabChange: (next: ResultTab) => void;
  onLogin: (values: { username: string; password: string }) => Promise<void> | void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onExportMarkdown: () => void;
  onExportStructuredText: () => void;
  onDownloadExport: () => void;
}) {
  return (
    <section className={preview ? "workspace-canvas workspace-canvas--preview" : "workspace-canvas"}>
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
          {needsLogin ? (
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
                <ProductFields formState={formState} readOnly={preview} onFieldChange={onFieldChange} />
              </div>

              <div className="workspace-card__footer">
                <button type="submit" className="primary-button primary-button--block" disabled={preview || authLoading}>
                  {resultState === "loading" ? "生成中..." : "生成商品内容初稿"}
                </button>
              </div>
            </form>
          )}

          <section className="workspace-card output-card">
            <div className="workspace-card__header workspace-card__header--row">
              <div>
                <h3>当前结果</h3>
                <p>系统会把商品理解、文案初稿、风险提醒和参考依据集中放在这里。</p>
              </div>
            </div>

            <div className="tab-row">
              {OUTPUT_TABS.map((item) => (
                <button
                  type="button"
                  key={item}
                  className={item === selectedTab ? "tab-chip tab-chip--active" : "tab-chip"}
                  onClick={() => onTabChange(item)}
                >
                  {item}
                </button>
              ))}
            </div>

            {preview ? (
              <EmptyResultState message="这里展示的是项目当前真实主流程结构，正式接入后会展示实时生成结果。" />
            ) : resultState === "loading" || jobLoading ? (
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
    </section>
  );
}

function Homepage({
  authLoading,
  formState,
  resultState,
  selectedTab,
  onEnterWorkspace,
  onFieldChange,
  onTabChange,
}: {
  authLoading: boolean;
  formState: PrototypeFormState;
  resultState: ResultState;
  selectedTab: ResultTab;
  onEnterWorkspace: () => void;
  onFieldChange: <K extends keyof PrototypeFormState>(field: K, value: PrototypeFormState[K]) => void;
  onTabChange: (next: ResultTab) => void;
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
            <button type="button" className="ghost-button" onClick={onEnterWorkspace} disabled={authLoading}>
              查看主流程
            </button>
          </div>
          <CapabilityStrip />
        </div>

        <HeroPreviewCard />
      </section>

      <FeatureStrip />

      <section className="preview-section">
        <div className="preview-section__heading">
          <span>项目现有主流程</span>
          <h2>从商品任务输入，到可继续编辑的内容结果</h2>
          <p>这里展示的不是效果图，而是项目现在真正要交付给用户的工作面。</p>
        </div>
        <WorkspaceCanvas
          preview={true}
          authLoading={authLoading}
          needsLogin={false}
          authSubmitting={false}
          authError=""
          formState={formState}
          resultState={resultState}
          selectedTab={selectedTab}
          workspaceStatus="主流程预览"
          pageError=""
          job={null}
          jobLoading={false}
          exportLoading={false}
          exportJob={null}
          onFieldChange={onFieldChange}
          onTabChange={onTabChange}
          onLogin={() => undefined}
          onSubmit={(event) => event.preventDefault()}
          onExportMarkdown={() => undefined}
          onExportStructuredText={() => undefined}
          onDownloadExport={() => undefined}
        />
      </section>
    </main>
  );
}

function WorkspaceSurface(props: Parameters<typeof WorkspaceCanvas>[0]) {
  return (
    <main className="workspace-page">
      <WorkspaceCanvas {...props} preview={false} />
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
  const [selectedTab, setSelectedTab] = useState<ResultTab>("全部");
  const [formState, setFormState] = useState<PrototypeFormState>(DEFAULT_FORM);
  const [pageError, setPageError] = useState("");
  const [exportLoading, setExportLoading] = useState(false);
  const [latestExportJob, setLatestExportJob] = useState<ExportJobRecord | null>(null);

  const requiresPasswordLogin = authConfig?.auth_mode === "password_login";
  const needsLogin = requiresPasswordLogin && !authUser;
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
      setActiveJobId(String(nextJob.id));
      writeStoredActiveJobId(String(nextJob.id));
      setResultState(isJobActive(nextJob.status) ? "loading" : "ready");
    } catch (error) {
      const message = error instanceof Error ? error.message : "加载当前结果失败。";
      setPageError(message);
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

      if (config.auth_mode === "password_login") {
        const storedSession = readStoredAuthSession();
        if (storedSession?.access_token) {
          try {
            const currentUser = await fetchCurrentUser();
            setAuthUser(currentUser);
          } catch {
            logoutOperator();
            setAuthUser(null);
          }
        }
      }

      const storedJobId = readStoredActiveJobId();
      if (storedJobId) {
        await loadJob(storedJobId);
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
    if (!activeJobId) {
      return;
    }

    setExportLoading(true);
    setPageError("");

    try {
      const exportJob = await createExportJob({
        taskId: activeJobId,
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

  return (
    <div className="prototype-shell">
      <PrototypeHeader authUser={authUser} onHome={() => switchSurface("homepage")} onWorkspace={() => switchSurface("workspace")} />
      {surface === "homepage" ? (
        <Homepage
          authLoading={authLoading}
          formState={formState}
          resultState={resultState}
          selectedTab={selectedTab}
          onEnterWorkspace={() => switchSurface("workspace")}
          onFieldChange={updateField}
          onTabChange={setSelectedTab}
        />
      ) : (
        <WorkspaceSurface
          preview={false}
          authLoading={authLoading}
          needsLogin={needsLogin}
          authSubmitting={authSubmitting}
          authError={authError}
          formState={formState}
          resultState={resultState}
          selectedTab={selectedTab}
          workspaceStatus={workspaceStatus}
          pageError={pageError}
          job={job}
          jobLoading={jobLoading}
          exportLoading={exportLoading}
          exportJob={toExportSummary(latestExportJob)}
          onFieldChange={updateField}
          onTabChange={setSelectedTab}
          onLogin={handleLogin}
          onSubmit={handleSubmit}
          onExportMarkdown={() => void handleExport("markdown")}
          onExportStructuredText={() => void handleExport("structured_text")}
          onDownloadExport={() => void handleDownloadExport()}
        />
      )}
    </div>
  );
}
