import "@patternfly/patternfly/patternfly-base.css";
import "@patternfly/patternfly/patternfly-charts-theme-dark.css";

import "@ansible/ansible-ui-framework/style.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./i18n";
import "./index.css";

const userName = document.getElementById("user_name")?.innerText ?? "undefined";
const telemetrySchema2EnabledInnerText = document.getElementById(
  "telemetry_schema_2_enabled",
)?.innerText;
const telemetrySchem2Enabled =
  telemetrySchema2EnabledInnerText?.toLowerCase() === "true";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App userName={userName} telemetryOptEnabled={telemetrySchem2Enabled} />
  </StrictMode>,
);
