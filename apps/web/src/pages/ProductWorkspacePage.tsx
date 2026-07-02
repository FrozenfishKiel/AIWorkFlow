import { useEffect, useState } from "react";

import { AuthPanel } from "../features/auth/AuthPanel";
import { ProductContentForm } from "../features/product-content/ProductContentForm";
import { ProductContentResult } from "../features/product-content/ProductContentResult";
import { getStoredJobRecoveryAction } from "./productWorkspaceState";
import { fetchCurrentUser, fetchAuthConfig, loginOperator, logoutOperator, readStoredAuthSession } from "../services/auth";
import { createExportJob, downloadExportArtifact, fetchExportJob } from "../services/exports";
import { createProductContentJob, fetchProductContentJob } from "../services/productContent";
import type { AuthConfig, AuthUser } from "../types/auth";
import type { ExportJobRecord } from "../types/export";
import { isJobActive, type ProductContentJobDetail, type ProductInputFormValues } from "../types/productContent";

const POLLING_INTERVAL_MS = 4000;
const ACTIVE_JOB_STORAGE_KEY = "ai-content-ops.product-content.active-job-id";

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

export function ProductWorkspacePage() {
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [authError, setAuthError] = useState("");

  const [job, setJob] = useState<ProductContentJobDetail | null>(null);
  const [activeJobId, setActiveJobId] = useState("");
  const [jobLoading, setJobLoading] = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [latestExportJob, setLatestExportJob] = useState<ExportJobRecord | null>(null);
  const [pageError, setPageError] = useState("");

  const requiresPasswordLogin = authConfig?.auth_mode === "password_login";
  const needsLogin = requiresPasswordLogin && !authUser;

  async function loadJob(jobId: string, options?: { silent?: boolean; fromStoredJob?: boolean }) {
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
    } catch (error) {
      if (options?.fromStoredJob) {
        const recovery = getStoredJobRecoveryAction(error);
        if (recovery.clearStoredJob) {
          setJob(null);
          setActiveJobId("");
          writeStoredActiveJobId(null);
          return;
        }

        setPageError(recovery.message ?? "加载当前结果失败。");
        return;
      }

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
        await loadJob(storedJobId, { fromStoredJob: true });
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

    try {
      const session = await loginOperator(values);
      setAuthUser({
        username: session.username,
        auth_mode: session.auth_mode,
        expires_at: session.expires_at,
      });
      setPageError("");
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "登录失败。");
    } finally {
      setAuthSubmitting(false);
    }
  }

  async function handleSubmit(values: ProductInputFormValues) {
    setSubmitLoading(true);
    setPageError("");
    setLatestExportJob(null);

    try {
      const jobId = await createProductContentJob(values);
      setActiveJobId(jobId);
      writeStoredActiveJobId(jobId);
      await loadJob(jobId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "创建商品内容任务失败。";
      setPageError(message);
    } finally {
      setSubmitLoading(false);
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

  const workspaceStatus = authLoading
    ? "正在连接服务"
    : needsLogin
      ? "等待登录"
      : activeJobId
        ? "本轮结果已连接"
        : "准备开始";

  return (
    <main className="shell shell--product">
      <header className="hero hero--product">
        <div className="hero__content">
          <p className="eyebrow">AI 内容工作流</p>
          <h1>电商商品内容生产系统</h1>
          <p className="hero__copy">
            围绕单个商品任务，把品牌口径、平台表达和历史优稿参考收进同一条生成链，直接交付可继续编辑的内容初稿。
          </p>
          <div className="hero__badges">
            <span className="hero-badge">统一品牌口径</span>
            <span className="hero-badge">多场景内容起稿</span>
            <span className="hero-badge">结果可直接导出</span>
          </div>
        </div>
        <aside className="hero__preview">
          <section className="preview-card">
            <p className="eyebrow eyebrow--light">商品内容工作台</p>
            <h2>让内容团队先拿到能改、能复用、能交付的第一版。</h2>
            <div className="preview-grid">
              <article className="preview-tile">
                <strong>统一商品叙事</strong>
                <p>先沉淀卖点，再把不同内容形态拉回同一条口径线上。</p>
              </article>
              <article className="preview-tile">
                <strong>覆盖三类产物</strong>
                <p>卖点文案、详情页文案、种草短文会一起落到同一个结果页。</p>
              </article>
              <article className="preview-tile">
                <strong>保留风险提醒</strong>
                <p>参考依据和口径风险跟结果同屏展示，方便运营继续收尾。</p>
              </article>
            </div>
            <div className="status-row">
              <span className="status-pill">{workspaceStatus}</span>
              {authUser ? <span className="status-pill status-pill--soft">操作者：{authUser.username}</span> : null}
            </div>
          </section>
        </aside>
      </header>

      {pageError ? <p className="alert">{pageError}</p> : null}

      <section className="workspace">
        <div className="workspace__rail">
          {needsLogin ? (
            <AuthPanel
              authMode="password_login"
              isSubmitting={authSubmitting}
              error={authError}
              onSubmit={handleLogin}
            />
          ) : (
            <ProductContentForm onSubmit={handleSubmit} isSubmitting={submitLoading} />
          )}
        </div>

        <div className="workspace__stage">
          <section className="panel panel--stage-intro">
            <div className="panel__header panel__header--aligned">
              <div>
                <p className="eyebrow">商品内容工作台</p>
                <h2>当前结果</h2>
              </div>
              <div className="status-row">
                <span className="status-pill status-pill--soft">{workspaceStatus}</span>
              </div>
            </div>
            <p className="muted">生成完成后，结果会在这里集中展开，方便继续编辑和导出。</p>
          </section>

          <ProductContentResult
            job={job}
            isLoading={jobLoading}
            exportLoading={exportLoading}
            exportJob={toExportSummary(latestExportJob)}
            onExportMarkdown={() => void handleExport("markdown")}
            onExportStructuredText={() => void handleExport("structured_text")}
            onDownloadExport={() => void handleDownloadExport()}
          />
        </div>
      </section>

      <section className="value-strip" aria-label="产品亮点">
        <article className="value-card">
          <p className="eyebrow">Brand Fit</p>
          <h2>把品牌语气和平台差异收进默认底座</h2>
          <p>不用再来回翻资料，生成时就按固定业务知识一起收口。</p>
        </article>
        <article className="value-card">
          <p className="eyebrow">Draft First</p>
          <h2>先给运营一个能继续改的强初稿</h2>
          <p>重点不是一次出终稿，而是让内容前半程不再从零开始。</p>
        </article>
        <article className="value-card">
          <p className="eyebrow">Traceable</p>
          <h2>结果、风险、参考依据放在同一个工作面</h2>
          <p>减少切页和反复确认，让人机协作更像产品而不是后台。</p>
        </article>
      </section>
    </main>
  );
}
