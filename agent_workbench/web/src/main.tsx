import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./styles/layout.css";
import "./styles/settings.css";
import "./styles/workbench.css";
import "highlight.js/styles/github.css";
import "./styles/markdown.css";
import "./styles/theme-dark.css";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
