import React from "react";
import ReactDOM from "react-dom/client";

import { TaskConsolePage } from "./pages/TaskConsolePage";

import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TaskConsolePage />
  </React.StrictMode>,
);

