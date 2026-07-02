import { useState } from "react";

import type { AuthMode } from "../../types/auth";

interface AuthPanelProps {
  authMode: AuthMode;
  isSubmitting?: boolean;
  error?: string;
  onSubmit: (values: { username: string; password: string }) => Promise<void> | void;
}

export function AuthPanel({
  authMode,
  isSubmitting = false,
  error = "",
  onSubmit,
}: AuthPanelProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  if (authMode === "legacy_token") {
    return (
      <section className="panel">
        <div className="panel__header">
          <h2>当前环境使用访问令牌</h2>
          <p>这个环境没有开放账号密码登录，请通过配置好的访问令牌进入系统。</p>
        </div>
        <p className="muted">
          请在前端环境里提供 <code>VITE_API_ACCESS_TOKEN</code>。
        </p>
        {error ? <p className="form__error">{error}</p> : null}
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>操作者登录</h2>
        <p>当前环境启用了最小登录边界，先登录再开始生成商品内容。</p>
      </div>

      <form
        className="form"
        onSubmit={(event) => {
          event.preventDefault();
          void onSubmit({
            username: username.trim(),
            password,
          });
        }}
      >
        <label className="form__label">
          用户名
          <input
            className="input"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="请输入用户名"
            autoComplete="username"
          />
        </label>

        <label className="form__label">
          密码
          <input
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="请输入密码"
            autoComplete="current-password"
          />
        </label>

        {error ? <p className="form__error">{error}</p> : null}

        <button className="button-primary" type="submit" disabled={isSubmitting || !username.trim() || !password}>
          {isSubmitting ? "登录中..." : "登录"}
        </button>
      </form>
    </section>
  );
}
