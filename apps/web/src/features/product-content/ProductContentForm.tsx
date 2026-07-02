import { useState } from "react";

import type { ProductInputFormValues } from "../../types/productContent";

export interface ProductContentFormProps {
  onSubmit: (values: ProductInputFormValues) => Promise<void> | void;
  isSubmitting?: boolean;
}

const EMPTY_VALUES: ProductInputFormValues = {
  name: "",
  category: "",
  specificationsText: "",
  priceRange: "",
  coreSellingPointsText: "",
  targetAudience: "",
  useScenariosText: "",
  promotionNotes: "",
  taskDescription: "",
};

export function ProductContentForm({ onSubmit, isSubmitting = false }: ProductContentFormProps) {
  const [values, setValues] = useState<ProductInputFormValues>(EMPTY_VALUES);
  const [error, setError] = useState("");

  function updateField<K extends keyof ProductInputFormValues>(field: K, value: ProductInputFormValues[K]) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!values.name.trim() || !values.category.trim() || !values.taskDescription.trim()) {
      setError("请至少填写商品名称、商品类目和任务描述。");
      return;
    }

    await onSubmit(values);
    setValues(EMPTY_VALUES);
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>输入商品任务</h2>
        <p>填写商品基础信息，再补一句这次要生成什么内容。系统会自动结合内置电商资料底座输出三类高质量初稿。</p>
      </div>

      <form className="form" onSubmit={handleSubmit}>
        <label className="field">
          <span>商品名称</span>
          <input value={values.name} onChange={(event) => updateField("name", event.target.value)} placeholder="例如：清透防晒霜" />
        </label>

        <label className="field">
          <span>商品类目</span>
          <input value={values.category} onChange={(event) => updateField("category", event.target.value)} placeholder="例如：护肤 / 家居 / 食品" />
        </label>

        <label className="field">
          <span>规格参数</span>
          <textarea
            value={values.specificationsText}
            onChange={(event) => updateField("specificationsText", event.target.value)}
            placeholder={"每行一条，例如：\n50ml\nSPF50+ PA++++"}
            rows={4}
          />
        </label>

        <label className="field">
          <span>价格带</span>
          <input value={values.priceRange} onChange={(event) => updateField("priceRange", event.target.value)} placeholder="例如：89-129元" />
        </label>

        <label className="field">
          <span>核心卖点</span>
          <textarea
            value={values.coreSellingPointsText}
            onChange={(event) => updateField("coreSellingPointsText", event.target.value)}
            placeholder={"每行一条，例如：\n清爽不搓泥\n通勤补涂方便"}
            rows={4}
          />
        </label>

        <label className="field">
          <span>目标人群</span>
          <input value={values.targetAudience} onChange={(event) => updateField("targetAudience", event.target.value)} placeholder="例如：通勤女生" />
        </label>

        <label className="field">
          <span>使用场景</span>
          <textarea
            value={values.useScenariosText}
            onChange={(event) => updateField("useScenariosText", event.target.value)}
            placeholder={"每行一条，例如：\n夏季通勤\n户外补涂"}
            rows={4}
          />
        </label>

        <label className="field">
          <span>活动信息</span>
          <input value={values.promotionNotes} onChange={(event) => updateField("promotionNotes", event.target.value)} placeholder="例如：618 第二件半价" />
        </label>

        <label className="field">
          <span>任务描述</span>
          <textarea
            value={values.taskDescription}
            onChange={(event) => updateField("taskDescription", event.target.value)}
            placeholder="例如：生成电商卖点、详情页和小红书种草短文案。"
            rows={4}
          />
        </label>

        {error ? <p className="form__error">{error}</p> : null}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "生成中..." : "生成商品内容初稿"}
        </button>
      </form>
    </section>
  );
}
