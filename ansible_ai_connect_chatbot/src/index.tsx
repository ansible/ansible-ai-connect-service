import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { ColorThemeSwitch } from "@ansible/ansible-ai-connect-chatbot";
import "@ansible/ansible-ai-connect-chatbot/style.css";
import reportWebVitals from "./reportWebVitals";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
);

root.render(
  <React.StrictMode>
    <div className="pf-v6-l-flex pf-m-column pf-m-gap-lg ws-full-page-utils pf-v6-m-dir-ltr ">
      <ColorThemeSwitch />
    </div>
    <App />
  </React.StrictMode>,
);

reportWebVitals();
