import type { ExportJobSummary, ProductContentJobDetail } from "../../types/productContent";
import { getJobStatusLabel, isJobActive } from "../../types/productContent";

export interface ProductContentResultProps {
  job: ProductContentJobDetail | null;
  isLoading?: boolean;
  exportLoading?: boolean;
  exportJob?: ExportJobSummary | null;
  onExportMarkdown?: () => void;
  onExportStructuredText?: () => void;
  onDownloadExport?: () => void;
}

export function ProductContentResult({
  job,
  isLoading = false,
  exportLoading = false,
  exportJob,
  onExportMarkdown,
  onExportStructuredText,
  onDownloadExport,
}: ProductContentResultProps) {
  if (isLoading) {
    return (
      <section className="panel">
        <div className="panel__header">
          <h2>当前结果</h2>
          <p>正在加载这次生成结果...</p>
        </div>
      </section>
    );
  }

  if (!job) {
    return (
      <section className="panel">
        <div className="panel__header">
          <h2>当前结果</h2>
          <p>填写商品信息后，这里会显示商品理解、三类初稿、风险提醒和参考依据。</p>
        </div>
      </section>
    );
  }

  if (isJobActive(job.status) && !job.generatedContent) {
    return (
      <section className="panel">
        <div className="panel__header">
          <h2>{job.product.name}</h2>
          <p>{getJobStatusLabel(job.status)}</p>
        </div>
        <p>正在生成这一轮商品内容初稿，请稍等片刻，结果会自动刷新出来。</p>
      </section>
    );
  }

  return (
    <section className="panel panel--result">
      <div className="panel__header">
        <h2>{job.product.name}</h2>
        <p>{getJobStatusLabel(job.status)} · {job.taskDescription}</p>
      </div>

      {job.productBrief ? (
        <section className="support-card">
          <h3>商品理解摘要</h3>
          <p>{job.productBrief.summary}</p>
          <p className="muted">目标人群：{job.productBrief.targetAudience ?? "未填写"}</p>
          <p className="muted">使用场景：{job.productBrief.useScenarios.join("、") || "未填写"}</p>
          <p className="muted">主打价值点：{job.productBrief.primaryValuePoints.join("、") || "未提炼"}</p>
        </section>
      ) : null}

      {job.generatedContent ? (
        <div className="detail-stack">
          <section className="support-card">
            <h3>电商卖点文案</h3>
            <ul className="stack">
              {job.generatedContent.sellingPointsCopy.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          </section>

          <section className="support-card">
            <h3>商品详情页文案</h3>
            <p>{job.generatedContent.detailPageCopy}</p>
          </section>

          <section className="support-card">
            <h3>小红书 / 种草短文案</h3>
            <p>{job.generatedContent.socialSeedCopy}</p>
          </section>

          <section className="support-card">
            <h3>风险提醒</h3>
            {job.generatedContent.riskNotes.length ? (
              <ul className="stack">
                {job.generatedContent.riskNotes.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">当前没有额外风险提醒。</p>
            )}
          </section>

          <section className="support-card">
            <h3>参考依据</h3>
            {job.referenceContext.length ? (
              <div className="stack">
                {job.referenceContext.map((item) => (
                  <article className="hit-card" key={item.sourceId}>
                    <strong>{item.title}</strong>
                    <p className="muted">{item.reason}</p>
                    <p>{item.snippet}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">当前没有命中可展示的资料引用。</p>
            )}
          </section>

          <section className="support-card">
            <h3>导出</h3>
            <div className="stack">
              <button type="button" className="button-secondary" disabled={exportLoading} onClick={onExportMarkdown}>
                导出 Markdown
              </button>
              <button type="button" className="button-secondary" disabled={exportLoading} onClick={onExportStructuredText}>
                导出结构化文本
              </button>
              {exportJob?.status === "completed" ? (
                <button type="button" className="button-secondary" onClick={onDownloadExport}>
                  下载导出文件
                </button>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
