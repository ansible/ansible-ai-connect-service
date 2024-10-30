import React from "react";

import ReactDOM from "react-dom/client";
import "./index.css";
import { App } from "./App";
import { ColorThemeSwitch } from "./ColorThemeSwitch/ColorThemeSwitch";
import reportWebVitals from "./reportWebVitals";
import "@patternfly/react-core/dist/styles/base.css";
// import '@patternfly/patternfly/patternfly-addons.css';

export const userName =
  document.getElementById("user_name")?.innerText ?? "User";
export const botName =
  document.getElementById("bot_name")?.innerText ??
  "Ansible AI Virtual Assistant";

// Add your extension CSS below
import "@patternfly/virtual-assistant/dist/css/main.css";
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

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
