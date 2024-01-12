import "@patternfly/patternfly/patternfly-base.css";
import "@patternfly/patternfly/patternfly-charts-theme-dark.css";

import "@ansible/ansible-ui-framework/style.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../i18n";
import "../index.css";
import { AppDenied } from "./AppDenied";

const userName = document.getElementById("user_name")?.innerText ?? undefined;
const hasSubscription =
  document.getElementById("has_subscription")?.innerText.toLowerCase() ===
  "true";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <AppDenied userName={userName} hasSubscription={hasSubscription} />
  </StrictMode>,
);
