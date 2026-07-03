import { startTransition, useState, type FormEvent } from "react";

type Surface = "homepage" | "workspace";
type ResultState = "loading" | "ready";
type ResultTab = "全部" | "商品理解" | "卖点文案" | "详情页文案" | "种草短文案" | "风险提醒" | "参考依据";

type ProductFormState = {
  name: string;
  category: string;
  specifications: string;
  priceRange: string;
  feature: string;
  audience: string;
  scenarios: string;
  promotion: string;
  taskDescription: string;
};

const OUTPUT_TABS: ResultTab[] = ["全部", "商品理解", "卖点文案", "详情页文案", "种草短文案", "风险提醒", "参考依据"];

const DEFAULT_FORM: ProductFormState = {
  name: "氨基酸净澈洁面乳",
  category: "个护清洁",
  specifications: "150g\n氨基酸配方\n敏感肌可用",
  priceRange: "79-99 元",
  feature: "温和净润、泡沫细腻、清洁后不紧绷",
  audience: "18-35 岁女性，关注温和清洁与肌肤舒缓",
  scenarios: "日常洁面\n换季维稳\n早晚护肤",
  promotion: "夏季焕肤专题，主打温和净澈",
  taskDescription: "生成电商卖点文案、详情页文案和小红书种草短文案。",
};

const PRODUCT_BRIEF = {
  summary: "这是一款强调温和清洁与舒缓肤感的洁面产品，适合以成分安心感和日常使用体验为主线展开表达。",
  audience: "18-35 岁女性，关注温和洁面与肌肤舒缓",
  scenarios: ["日常洁面", "换季维稳", "早晚护肤"],
  points: ["氨基酸配方", "泡沫细腻", "清洁后不紧绷"],
};

const RESULT_CONTENT = {
  sellingPoints: [
    "氨基酸净澈配方，温和带走油脂与残留，不打扰肌肤舒适感。",
    "细腻泡沫快速铺开，清洁过程更柔和，敏感时刻也能安心使用。",
    "洁面后肤感净润不紧绷，更适合日常早晚反复使用。",
  ],
  detailPage:
    "把温和清洁、细腻泡沫与净润肤感收进同一条表达主线，详情页围绕使用体验展开，而不是只堆叠成分名词。重点突出清洁后不紧绷、适合日常和换季护理，让商品信息更容易被消费者快速理解。",
  socialCopy:
    "最近在用这支氨基酸洁面乳，泡沫很细，洗完不是那种猛地拔干的感觉。早晚用都比较稳，尤其换季的时候会更在意这种温和但又洗得干净的肤感，如果你也在找一支不容易出错的日常洁面，可以看看这类思路。",
  riskNotes: [
    "避免使用过度功效承诺，例如深层修复、立刻改善敏感等表述。",
    "小红书文案建议保留真实使用感，少用过强销售话术。",
  ],
  references: [
    {
      title: "品牌语气规范",
      reason: "当前任务更适合自然松弛、不过度承诺的表达方式。",
      snippet: "强调真实肤感和日常体验，不直接堆砌绝对化功效词。",
    },
    {
      title: "平台表达差异",
      reason: "种草短文案需要更生活化，详情页则更适合清晰结构表达。",
      snippet: "电商详情页突出价值点，小红书内容更强调使用情境与个人感受。",
    },
  ],
};

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
  onHome,
  onWorkspace,
}: {
  onHome: () => void;
  onWorkspace: () => void;
}) {
  return (
    <header className="site-header">
      <BrandMark onClick={onHome} />
      <nav className="site-nav">
        <button type="button" className="site-nav__link site-nav__link--active" onClick={onHome}>
          产品
        </button>
        <span className="site-nav__item">解决方案</span>
        <span className="site-nav__item">应用场景</span>
        <span className="site-nav__item">使用方式</span>
      </nav>
      <div className="site-actions">
        <button type="button" className="ghost-button ghost-button--tight">
          登录
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
        <p>{PRODUCT_BRIEF.summary}</p>
      </article>

      <div className="hero-preview__grid">
        <article className="hero-preview__panel hero-preview__panel--compact">
          <p className="hero-preview__label">卖点文案</p>
          <ul>
            {RESULT_CONTENT.sellingPoints.slice(0, 2).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
        <article className="hero-preview__panel hero-preview__panel--compact">
          <p className="hero-preview__label">种草短文案</p>
          <p>{RESULT_CONTENT.socialCopy}</p>
        </article>
      </div>
    </section>
  );
}

function CapabilityStrip() {
  const items = ["固定业务资料底座", "三类初稿同屏输出", "风险提醒与参考依据", "支持结果导出"];

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

function WorkspaceSidebar() {
  return (
    <aside className="workspace-sidebar">
      <div className="workspace-sidebar__brand">
        <span className="workspace-sidebar__cube" />
        <strong>智绘商拍</strong>
      </div>

      <nav className="workspace-sidebar__nav">
        <span>工作台</span>
        <span className="workspace-sidebar__nav-item workspace-sidebar__nav-item--active">内容生成</span>
        <span className="workspace-sidebar__nav-item">资料底座</span>
        <span className="workspace-sidebar__nav-item">导出记录</span>
      </nav>

      <div className="workspace-sidebar__note">
        <small>当前状态</small>
        <strong>本轮结果已连接</strong>
        <span>生成完成后可直接在右侧继续查看与导出。</span>
      </div>
    </aside>
  );
}

function ProductFields({
  formState,
  readOnly,
  onFieldChange,
}: {
  formState: ProductFormState;
  readOnly: boolean;
  onFieldChange: <K extends keyof ProductFormState>(field: K, value: ProductFormState[K]) => void;
}) {
  return (
    <div className="form-grid">
      <label className="field-input">
        <span>商品名称</span>
        <input value={formState.name} readOnly={readOnly} onChange={(event) => onFieldChange("name", event.target.value)} />
      </label>

      <label className="field-input">
        <span>商品类目</span>
        <input
          value={formState.category}
          readOnly={readOnly}
          onChange={(event) => onFieldChange("category", event.target.value)}
        />
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
        <input
          value={formState.priceRange}
          readOnly={readOnly}
          onChange={(event) => onFieldChange("priceRange", event.target.value)}
        />
      </label>

      <label className="field-input">
        <span>目标人群</span>
        <input
          value={formState.audience}
          readOnly={readOnly}
          onChange={(event) => onFieldChange("audience", event.target.value)}
        />
      </label>

      <label className="field-input field-input--full">
        <span>核心卖点</span>
        <textarea value={formState.feature} readOnly={readOnly} onChange={(event) => onFieldChange("feature", event.target.value)} rows={4} />
      </label>

      <label className="field-input field-input--full">
        <span>使用场景</span>
        <textarea
          value={formState.scenarios}
          readOnly={readOnly}
          onChange={(event) => onFieldChange("scenarios", event.target.value)}
          rows={4}
        />
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

function ResultCards() {
  return (
    <div className="result-stack">
      <article className="result-card result-card--brief">
        <p className="result-card__eyebrow">商品理解摘要</p>
        <h4>{PRODUCT_BRIEF.summary}</h4>
        <div className="chip-row">
          {PRODUCT_BRIEF.points.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
        <p className="result-card__meta">目标人群：{PRODUCT_BRIEF.audience}</p>
        <p className="result-card__meta">使用场景：{PRODUCT_BRIEF.scenarios.join("、")}</p>
      </article>

      <div className="result-grid">
        <article className="result-card">
          <p className="result-card__eyebrow">电商卖点文案</p>
          <ul className="result-list">
            {RESULT_CONTENT.sellingPoints.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="result-card">
          <p className="result-card__eyebrow">商品详情页文案</p>
          <p>{RESULT_CONTENT.detailPage}</p>
        </article>

        <article className="result-card">
          <p className="result-card__eyebrow">小红书 / 种草短文案</p>
          <p>{RESULT_CONTENT.socialCopy}</p>
        </article>

        <article className="result-card">
          <p className="result-card__eyebrow">风险提醒</p>
          <ul className="result-list">
            {RESULT_CONTENT.riskNotes.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </div>

      <article className="result-card">
        <div className="result-card__header">
          <div>
            <p className="result-card__eyebrow">参考依据</p>
            <h4>当前命中的资料底座</h4>
          </div>
          <div className="workspace-actions">
            <button type="button" className="ghost-button ghost-button--tiny">
              导出 Markdown
            </button>
            <button type="button" className="ghost-button ghost-button--tiny">
              导出结构化文本
            </button>
          </div>
        </div>

        <div className="reference-grid">
          {RESULT_CONTENT.references.map((item) => (
            <article className="reference-card" key={item.title}>
              <strong>{item.title}</strong>
              <p className="reference-card__reason">{item.reason}</p>
              <p>{item.snippet}</p>
            </article>
          ))}
        </div>
      </article>
    </div>
  );
}

function WorkspaceCanvas({
  preview,
  formState,
  resultState,
  selectedTab,
  onFieldChange,
  onTabChange,
  onSubmit,
}: {
  preview: boolean;
  formState: ProductFormState;
  resultState: ResultState;
  selectedTab: ResultTab;
  onFieldChange: <K extends keyof ProductFormState>(field: K, value: ProductFormState[K]) => void;
  onTabChange: (next: ResultTab) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className={preview ? "workspace-canvas workspace-canvas--preview" : "workspace-canvas"}>
      <WorkspaceSidebar />

      <div className="workspace-stage">
        <div className="workspace-stage__header">
          <div>
            <p className="workspace-stage__eyebrow">主流程</p>
            <h3>输入商品任务，直接产出可继续编辑的内容初稿</h3>
          </div>
          <span className="workspace-stage__status">{resultState === "loading" ? "生成中" : "准备完成"}</span>
        </div>

        <div className="workspace-stage__main">
          <form className="workspace-card input-card" onSubmit={onSubmit}>
            <div className="workspace-card__header">
              <h3>输入商品任务</h3>
              <p>围绕商品信息和一句任务描述，把这一轮内容生成需求交给系统。</p>
            </div>

            <div className="workspace-card__body">
              <ProductFields formState={formState} readOnly={preview} onFieldChange={onFieldChange} />
            </div>

            <div className="workspace-card__footer">
              <button type="submit" className="primary-button primary-button--block">
                {resultState === "loading" ? "生成中..." : "生成商品内容初稿"}
              </button>
            </div>
          </form>

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

            {resultState === "loading" ? (
              <div className="result-loading">
                <div className="result-loading__line result-loading__line--wide" />
                <div className="result-loading__line" />
                <div className="result-loading__line" />
                <div className="result-loading__block" />
                <div className="result-loading__block" />
              </div>
            ) : (
              <ResultCards />
            )}
          </section>
        </div>
      </div>
    </section>
  );
}

function Homepage({
  formState,
  resultState,
  selectedTab,
  onEnterWorkspace,
  onFieldChange,
  onTabChange,
}: {
  formState: ProductFormState;
  resultState: ResultState;
  selectedTab: ResultTab;
  onEnterWorkspace: () => void;
  onFieldChange: <K extends keyof ProductFormState>(field: K, value: ProductFormState[K]) => void;
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
            <button type="button" className="primary-button" onClick={onEnterWorkspace}>
              进入工作台
            </button>
            <button type="button" className="ghost-button" onClick={onEnterWorkspace}>
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
          formState={formState}
          resultState={resultState}
          selectedTab={selectedTab}
          onFieldChange={onFieldChange}
          onTabChange={onTabChange}
          onSubmit={(event) => event.preventDefault()}
        />
      </section>
    </main>
  );
}

function WorkspaceSurface({
  formState,
  resultState,
  selectedTab,
  onFieldChange,
  onTabChange,
  onSubmit,
}: {
  formState: ProductFormState;
  resultState: ResultState;
  selectedTab: ResultTab;
  onFieldChange: <K extends keyof ProductFormState>(field: K, value: ProductFormState[K]) => void;
  onTabChange: (next: ResultTab) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <main className="workspace-page">
      <WorkspaceCanvas
        preview={false}
        formState={formState}
        resultState={resultState}
        selectedTab={selectedTab}
        onFieldChange={onFieldChange}
        onTabChange={onTabChange}
        onSubmit={onSubmit}
      />
    </main>
  );
}

export function StructuredSaasPrototype() {
  const [surface, setSurface] = useState<Surface>("homepage");
  const [resultState, setResultState] = useState<ResultState>("ready");
  const [selectedTab, setSelectedTab] = useState<ResultTab>("全部");
  const [formState, setFormState] = useState<ProductFormState>(DEFAULT_FORM);

  function switchSurface(next: Surface) {
    startTransition(() => {
      setSurface(next);
    });
  }

  function updateField<K extends keyof ProductFormState>(field: K, value: ProductFormState[K]) {
    setFormState((current) => ({ ...current, [field]: value }));
  }

  function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setResultState("loading");
    window.setTimeout(() => {
      setResultState("ready");
      switchSurface("workspace");
    }, 900);
  }

  return (
    <div className="prototype-shell">
      <PrototypeHeader onHome={() => switchSurface("homepage")} onWorkspace={() => switchSurface("workspace")} />
      {surface === "homepage" ? (
        <Homepage
          formState={formState}
          resultState={resultState}
          selectedTab={selectedTab}
          onEnterWorkspace={() => switchSurface("workspace")}
          onFieldChange={updateField}
          onTabChange={setSelectedTab}
        />
      ) : (
        <WorkspaceSurface
          formState={formState}
          resultState={resultState}
          selectedTab={selectedTab}
          onFieldChange={updateField}
          onTabChange={setSelectedTab}
          onSubmit={handleGenerate}
        />
      )}
    </div>
  );
}
