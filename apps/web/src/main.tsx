import React from "react";
import ReactDOM from "react-dom/client";

import { ProductWorkspacePage } from "./pages/ProductWorkspacePage";

import "./prototype/structured-saas-prototype.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ProductWorkspacePage />
  </React.StrictMode>,
);
