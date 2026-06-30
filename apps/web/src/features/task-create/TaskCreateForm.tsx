import { useState } from "react";

import {
  TASK_CONSOLE_INPUT_TYPES,
  type TaskCreateFormValues,
  type TaskInputType,
} from "../../types/task";

export interface TaskCreateFormProps {
  onSubmit: (values: TaskCreateFormValues) => Promise<void> | void;
  isSubmitting?: boolean;
}

const EMPTY_VALUES: TaskCreateFormValues = {
  inputType: "text",
  content: "",
  knowledgeDomain: "",
  file: null,
};

/**
 * Simple submission form for the first console iteration.
 * It keeps the controls explicit so the API contract stays easy to inspect.
 */
export function TaskCreateForm({ onSubmit, isSubmitting = false }: TaskCreateFormProps) {
  const [values, setValues] = useState<TaskCreateFormValues>(EMPTY_VALUES);
  const [error, setError] = useState("");
  const isFileTask = values.inputType === "file";
  const canSubmit = isFileTask ? Boolean(values.file) : values.content.trim().length > 0;

  function updateField<K extends keyof TaskCreateFormValues>(field: K, value: TaskCreateFormValues[K]) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!canSubmit) {
      setError(isFileTask ? "A file is required." : "Content is required.");
      return;
    }

    await onSubmit(values);
    setValues(EMPTY_VALUES);
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>New task</h2>
        <p>Create a text, URL, or file task for the async pipeline.</p>
      </div>

      <form className="form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Input type</span>
          <select
            value={values.inputType}
            onChange={(event) => updateField("inputType", event.target.value as TaskInputType)}
          >
            {TASK_CONSOLE_INPUT_TYPES.map((inputType) => (
              <option key={inputType} value={inputType}>
                {inputType === "text" ? "Text" : inputType === "url" ? "URL" : "File"}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Knowledge domain</span>
          <input
            value={values.knowledgeDomain ?? ""}
            onChange={(event) => updateField("knowledgeDomain", event.target.value)}
            placeholder="Optional, for example: brand / compliance / content-ops"
          />
          <span className="muted">Leave blank to search across all indexed knowledge for now.</span>
        </label>

        {isFileTask ? (
          <label className="field">
            <span>File</span>
            <input
              type="file"
              accept=".txt,.md,.markdown"
              onChange={(event) => updateField("file", event.target.files?.[0] ?? null)}
            />
            <span className="muted">Accepted: .txt, .md, .markdown, up to backend-enforced limits.</span>
          </label>
        ) : (
          <label className="field">
            <span>Content</span>
            <textarea
              value={values.content}
              onChange={(event) => updateField("content", event.target.value)}
              placeholder={
                values.inputType === "url"
                  ? "https://example.com/article"
                  : "Paste the task content here."
              }
              rows={7}
            />
          </label>
        )}

        {error ? <p className="form__error">{error}</p> : null}

        <button type="submit" disabled={!canSubmit || isSubmitting}>
          {isSubmitting ? "Creating..." : "Create task"}
        </button>
      </form>
    </section>
  );
}
