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

  return (
    <main className="shell">
      <header className="hero hero--product">
        <div className="hero__content">
          <p className="eyebrow">AI 应用开发主链</p>
          <h1>电商商品内容生产系统</h1>
          <p className="hero__copy">
            输入商品基础信息和一句任务描述，系统会先理解商品，再结合内置品牌口径、平台差异和历史优稿参考，
            生成供运营二次编辑的高质量初稿。
          </p>
          <div className="hero__steps">
            <span className="hero-step">1. 填商品信息</span>
            <span className="hero-step">2. 自动理解与资料匹配</span>
            <span className="hero-step">3. 产出三类内容初稿</span>
          </div>
        </div>
      </header>

      {pageError ? <p className="alert">{pageError}</p> : null}

      <section className="workspace">
        <div className="workspace__sidebar">
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

          <section className="panel">
            <div className="panel__header panel__header--stacked">
              <p className="eyebrow eyebrow--soft">这次会得到什么</p>
              <h2>高质量初稿，不是最终发布稿</h2>
            </div>
            <div className="stack muted">
              <p>系统会同时给出电商卖点文案、商品详情页文案和小红书 / 种草短文案。</p>
              <p>结果默认是“可继续编辑”的初稿，会附带风险提醒和参考依据，方便你快速接着改。</p>
              <p>如果你刷新页面，系统会尽量找回最近一次正在处理或刚生成完成的结果。</p>
            </div>
          </section>
        </div>

        <div className="workspace__main">
          <ProductContentResult
            job={job}
            isLoading={jobLoading}
            exportLoading={exportLoading}
            exportJob={toExportSummary(latestExportJob)}
            onExportMarkdown={() => void handleExport("markdown")}
            onExportStructuredText={() => void handleExport("structured_text")}
            onDownloadExport={() => void handleDownloadExport()}
          />

          <section className="secondary-grid">
            <article className="support-card">
              <h3>系统这次会怎么处理</h3>
              <p className="muted">不是直接吐字，而是先做商品理解，再去匹配固定业务资料，最后统一生成三类内容。</p>
              <div className="token-list">
                <span className="token-chip">商品理解</span>
                <span className="token-chip">资料匹配</span>
                <span className="token-chip">卖点提炼</span>
                <span className="token-chip">内容生成</span>
                <span className="token-chip">风险检查</span>
              </div>
            </article>

            <article className="support-card">
              <h3>适合怎么输入</h3>
              <p className="muted">越具体越好，尤其是商品规格、核心卖点、目标人群、场景和活动信息。</p>
              <p className="muted">任务描述建议直接写清这次想突出什么，例如“偏通勤场景、强调清爽和便携”。</p>
            </article>

            <article className="support-card">
              <h3>当前状态</h3>
              <p className="muted">
                {authLoading
                  ? "正在连接服务并检查登录方式。"
                  : needsLogin
                    ? "当前环境启用了登录，请先登录再开始生成。"
                    : activeJobId
                      ? "已经连接到当前任务，结果区会自动刷新。"
                      : "还没有开始本轮生成，先在左侧填写商品任务。"}
              </p>
              {authUser ? <p className="muted">当前操作者：{authUser.username}</p> : null}
              {job ? <p className="muted">最近任务状态：{job.currentStage}</p> : null}
            </article>
          </section>
        </div>
      </section>
    </main>
  );
}
