# Refactor ansible_ai_connect_chatbot to Use the @ansible/ansible-ai-connect-chatbot npm Package

## Context

The repo has two chatbot UI implementations that share ~95% identical code:

- **`aap_chatbot/`** — published to npm as `@ansible/ansible-ai-connect-chatbot` (v0.1.14), a React library (ESM + UMD)
- **`ansible_ai_connect_chatbot/`** — private SPA, built by Vite, rsynced into Django static/templates

8 source files are byte-for-byte identical between the two. The remaining differences are confined to configuration values (API paths, models, CSRF strategy, header layout, welcome prompts). This plan makes the npm package configurable enough to support both use cases, then refactors the SPA to import from the package instead of duplicating its source.

---

## Current State: File-by-File Comparison

### Identical files (zero diff)

| File | Lines |
|------|-------|
| `src/types/Message.ts` | 61 |
| `src/types/Model.ts` | 4 |
| `src/DebugSettingsModal/DebugSettingsModal.tsx` | 84 |
| `src/ReferencedDocuments/ReferencedDocuments.tsx` | 49 |
| `src/utils/MarkdownLinkBuffer.ts` | ~60 |
| `src/Clipboard.ts` | ~10 |
| `src/ColorThemeSwitch/ColorThemeSwitch.tsx` | ~30 |
| `tsconfig.json` | 21 |

### Files with differences

| Aspect | `aap_chatbot` (npm package) | `ansible_ai_connect_chatbot` (SPA) |
|--------|----------------------------|-------------------------------------|
| **API base path** | `/api/lightspeed/v1` | `/api/v1` |
| **Default model** | `granite-3.3-8b-instruct` (rhoai) | `google/gemini-2.5-pro` (vertexai) |
| **CSRF handling** | Gateway-aware: checks `gateway_sessionid` / `__Host-sessionid` cookies, then falls through | Simple: `__Host-csrftoken ?? csrftoken` |
| **Welcome prompt** | `"Hello " + username`, no suggestions | `"Hello, Ansible User"`, 3 AAP-specific suggestion prompts |
| **Header layout** | Menu, DebugSettings (if debug), NewChatButton | Menu, NewChatButton, BrandLogos, PreviewLabel, InventoryDocModal, DebugSettings (if debug), ModelSelector (if debug) |
| **GitHub issue URL** | Includes `prompt` and `response` params | Omits `prompt` and `response` params |
| **Streaming error format** | `title: "Error", message: 'Bot returned an error: response="...", cause="..."'` | `title: data.response, message: data.cause` |
| **Constants.ts** | Has `AAP_UI = true` (unused export) | Does not have it |
| **Asset paths** | `../public/lightspeed.svg` | `../assets/lightspeed.svg` |
| **AnsibleChatbot props** | Accepts `ChatbotContext { username?: string }` | No props (bare `React.FunctionComponent`) |
| **Model selector UI** | Hook returns `selectedModel`/`setSelectedModel` but UI doesn't render dropdown | Renders `ChatbotHeaderSelectorDropdown` in debug mode |

### Unique to `ansible_ai_connect_chatbot`

- `InventoryDocumentationModal/InventoryDocumentationModal.tsx` (266 lines) — help modal for AAP inventory file builder docs
- `reportWebVitals.ts` — performance measuring (trivial CRA artifact)

---

## Approach: npm Package Dependency

`ansible_ai_connect_chatbot` will add `@ansible/ansible-ai-connect-chatbot` as a dependency in `package.json` and import all shared components/hooks from it. This requires making the npm package configurable first.

**Trade-off**: Clean separation with a single source of truth, but shared changes require a package publish before the SPA picks them up.

---

## Phase 1: Make the npm Package Configurable (`aap_chatbot/`)

### 1.1 Add configuration interface

Create **`aap_chatbot/src/types/ChatbotConfig.ts`**:

```typescript
import type { ReactNode, RefObject } from "react";
import type { LLMModel } from "./Model";
import type { ExtendedMessage } from "./Message";

export interface WelcomePromptItem {
  title: string;
  message: string;
}

export interface HeaderRenderProps {
  isDrawerOpen: boolean;
  setIsDrawerOpen: (v: boolean) => void;
  historyRef: RefObject<HTMLButtonElement>;
  setCurrentConversation: (id: string | undefined, msgs: ExtendedMessage[]) => void;
  inDebugMode: boolean;
  bypassTools: boolean;
  setBypassTools: (v: boolean) => void;
  selectedModel: string;
  setSelectedModel: (v: string) => void;
  models: LLMModel[];
  bodyElement: HTMLElement;
}

export interface ChatbotConfig {
  /** API prefix: "/api/lightspeed/v1" (default) or "/api/v1" */
  apiBasePath?: string;

  /** Models shown in the debug model selector */
  models?: LLMModel[];

  /** Username for welcome greeting */
  username?: string;

  /** Custom welcome title. Default: "Hello " + username */
  welcomeTitle?: string;

  /** Welcome suggestion prompts. Default: [] (no suggestions) */
  welcomePrompts?: WelcomePromptItem[];

  /** Custom header renderer. When omitted, renders the default aap header */
  renderHeader?: (props: HeaderRenderProps) => ReactNode;

  /** Whether to include query/response in GitHub feedback issue URL. Default: true */
  includeQueryInFeedbackUrl?: boolean;
}
```

### 1.2 Modify `useChatbot` hook

**File:** `aap_chatbot/src/useChatbot/useChatbot.ts`

Changes:
- Accept optional config parameter: `useChatbot(config?: { apiBasePath?: string; models?: LLMModel[] })`
- Default `apiBasePath` to `"/api/lightspeed/v1"` when not provided
- Default `models` to `[{ model: "granite-3.3-8b-instruct", provider: "rhoai" }]` when not provided
- Replace 4 hardcoded API paths with template strings using `apiBasePath`:
  - `${apiBasePath}/health/status/chatbot/`
  - `${apiBasePath}/ai/chat/`
  - `${apiBasePath}/ai/streaming_chat/`
  - `${apiBasePath}/ai/feedback/`
- Replace hardcoded `modelsSupported` array with the config value
- Replace hardcoded `useState("granite-3.3-8b-instruct")` with `useState(models[0].model)`
- In `createGitHubIssueURL`: conditionally include `prompt`/`response` params based on a parameter
- Keep gateway-aware CSRF detection as-is (it's a superset that works for both — when no gateway cookie is present, it falls through to the simple logic)

### 1.3 Modify `AnsibleChatbot` component

**File:** `aap_chatbot/src/AnsibleChatbot/AnsibleChatbot.tsx`

Changes:
- Extend props interface to include `ChatbotConfig` fields
- Pass `apiBasePath` and `models` to `useChatbot()`
- Use `config.welcomeTitle` / `config.welcomePrompts` in `ChatbotWelcomePrompt`. Default welcome title is `"Hello " + username`
- Support `renderHeader` render prop:
  - When provided: call `config.renderHeader(headerProps)` instead of rendering the default header
  - When absent: render current aap header unchanged (backward compatible)
- Add model selector dropdown to the default header under `inDebugMode()` (the hook already returns `selectedModel`/`setSelectedModel`, just needs UI)

### 1.4 Update `App` component

**File:** `aap_chatbot/src/App.tsx`

- Accept optional `config?: Partial<ChatbotConfig>` alongside existing `username`
- Pass all config to `AnsibleChatbot`
- Backward compatible: `<App username="someone" />` still works with no config (all defaults apply)

```typescript
export interface ChatbotContext {
  username?: string;
  config?: Partial<ChatbotConfig>;
}

export const App: React.FunctionComponent<ChatbotContext> = (context) => (
  <AnsibleChatbot username={context?.username} {...context?.config} />
);
```

### 1.5 Expand exports

**File:** `aap_chatbot/src/index.tsx`

Add these exports (existing exports remain unchanged):

```typescript
// Components
export { AnsibleChatbot } from "./AnsibleChatbot/AnsibleChatbot";
export { ColorThemeSwitch } from "./ColorThemeSwitch/ColorThemeSwitch";
export { DebugSettingsModal } from "./DebugSettingsModal/DebugSettingsModal";

// Hook and utilities
export { useChatbot, readCookie, readCsrfCookie, inDebugMode, bodyElement } from "./useChatbot/useChatbot";

// Types
export type { ChatbotConfig, WelcomePromptItem, HeaderRenderProps } from "./types/ChatbotConfig";
export type { ExtendedMessage, ReferencedDocument } from "./types/Message";
export type { LLMModel } from "./types/Model";

// Existing (unchanged)
export { App } from "./App";
export { getProductName } from "./Constants";
export { LIGHTSPEED_LOGO };
export { LIGHTSPEED_LOGO_DARK };
```

### 1.6 Bump version

**File:** `aap_chatbot/package.json` — bump to `0.2.0` (minor version: additive, non-breaking).

---

## Phase 2: Refactor the SPA (`ansible_ai_connect_chatbot/`)

### 2.1 Add npm package dependency

**File:** `ansible_ai_connect_chatbot/package.json`

```json
{
  "dependencies": {
    "@ansible/ansible-ai-connect-chatbot": "^0.2.0"
  }
}
```

Remove `@microsoft/fetch-event-source` (now consumed internally by the package).

### 2.2 Create custom header component

**New file:** `ansible_ai_connect_chatbot/src/AnsibleAIConnectHeader.tsx` (~70 lines)

Extracted from the current `AnsibleChatbot.tsx` header section. Contains:
- Brand logos (light/dark mode)
- "Preview" label with tooltip
- `InventoryDocumentationModal` (imported from local source)
- `DebugSettingsModal` (imported from npm package)
- Model selector dropdown (imported from `@patternfly/chatbot`)

```typescript
import {
  DebugSettingsModal,
  type HeaderRenderProps,
} from "@ansible/ansible-ai-connect-chatbot";
import { InventoryDocumentationModal } from "./InventoryDocumentationModal/InventoryDocumentationModal";
// ... PatternFly imports for Brand, Label, Tooltip, etc.

export const AnsibleAIConnectHeader: React.FC<HeaderRenderProps> = (props) => (
  <ChatbotHeader>
    <ChatbotHeaderMain>
      <ChatbotHeaderMenu ... />
      <ChatbotHeaderNewChatButton ... />
      <ChatbotHeaderTitle>
        <Bullseye>
          <div className="show-light"><Brand src={lightspeedLogo} alt="Ansible" /></div>
          <div className="show-dark"><Brand src={lightspeedLogoDark} alt="Ansible" /></div>
        </Bullseye>
      </ChatbotHeaderTitle>
    </ChatbotHeaderMain>
    <ChatbotHeaderActions>
      <Tooltip content="This is a Developer Preview feature..." position="left" maxWidth="25rem" isContentLeftAligned>
        <Label color="orange" icon={<InfoCircleIcon />}>Preview</Label>
      </Tooltip>
      <InventoryDocumentationModal />
      {props.inDebugMode && <DebugSettingsModal bypassTools={props.bypassTools} setBypassTools={props.setBypassTools} />}
      {props.inDebugMode && <ChatbotHeaderSelectorDropdown value={props.selectedModel} onSelect={...}>
        <DropdownList>
          {props.models.map(m => <DropdownItem value={m.model} key={m.model}>{m.model}</DropdownItem>)}
        </DropdownList>
      </ChatbotHeaderSelectorDropdown>}
    </ChatbotHeaderActions>
  </ChatbotHeader>
);
```

### 2.3 Rewrite `App.tsx`

```typescript
import { App as ChatbotApp } from "@ansible/ansible-ai-connect-chatbot";
import type { ChatbotConfig } from "@ansible/ansible-ai-connect-chatbot";
import { AnsibleAIConnectHeader } from "./AnsibleAIConnectHeader";

const config: Partial<ChatbotConfig> = {
  apiBasePath: "/api/v1",
  models: [{ model: "google/gemini-2.5-pro", provider: "vertexai" }],
  welcomeTitle: "Hello, Ansible User",
  welcomePrompts: [
    { title: "Using Ansible Automation Platform", message: "I have a question about using Ansible Automation Platform" },
    { title: "Installing Ansible Automation Platform", message: "I want to learn more about installing Ansible Automation Platform" },
    { title: "Operating Ansible Automation Platform", message: "I want to learn how to operate and monitor Ansible Automation Platform" },
  ],
  includeQueryInFeedbackUrl: false,
  renderHeader: (props) => <AnsibleAIConnectHeader {...props} />,
};

export const App = () => <ChatbotApp config={config} />;
```

### 2.4 Update `index.tsx`

```typescript
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { ColorThemeSwitch } from "@ansible/ansible-ai-connect-chatbot";
import "@ansible/ansible-ai-connect-chatbot/style.css";
import "./header-overrides.css";
import reportWebVitals from "./reportWebVitals";

const root = ReactDOM.createRoot(document.getElementById("root") as HTMLElement);
root.render(
  <React.StrictMode>
    <div className="pf-v6-l-flex pf-m-column pf-m-gap-lg ws-full-page-utils pf-v6-m-dir-ltr">
      <ColorThemeSwitch />
    </div>
    <App />
  </React.StrictMode>,
);
reportWebVitals();
```

### 2.5 Create `header-overrides.css`

**New file:** `ansible_ai_connect_chatbot/src/header-overrides.css`

Extract the ansible_ai_connect-specific CSS overrides (if any exist in the current SCSS that differ from the package). These are the header styling adjustments unique to the SPA.

### 2.6 Update `InventoryDocumentationModal` imports

**File:** `ansible_ai_connect_chatbot/src/InventoryDocumentationModal/InventoryDocumentationModal.tsx`

Change:
```typescript
// Before
import { getProductName } from "../Constants";

// After
import { getProductName } from "@ansible/ansible-ai-connect-chatbot";
```

Keep local SVG imports from `../assets/` (still needed for the modal's `Brand` component).

### 2.7 Delete duplicated source files

Remove these files (now provided by the npm package):

```
src/useChatbot/useChatbot.ts
src/useChatbot/useChatbot.test.ts
src/AnsibleChatbot/AnsibleChatbot.tsx
src/AnsibleChatbot/AnsibleChatbot.scss
src/AnsibleChatbot/AnsibleChatbot.test.tsx
src/AnsibleChatbot/__screenshots__/
src/DebugSettingsModal/
src/ReferencedDocuments/
src/ColorThemeSwitch/
src/utils/
src/types/
src/Constants.ts
src/Constants.test.ts
src/Clipboard.ts
src/index.css
```

### 2.8 Files retained after refactoring

```
ansible_ai_connect_chatbot/
├── src/
│   ├── App.tsx                         # Thin wrapper (rewritten)
│   ├── App.test.tsx                    # Updated imports
│   ├── index.tsx                       # SPA entry (updated)
│   ├── AnsibleAIConnectHeader.tsx      # NEW: custom header
│   ├── header-overrides.css            # NEW: local CSS overrides
│   ├── InventoryDocumentationModal/    # KEPT: unique feature
│   │   ├── InventoryDocumentationModal.tsx
│   │   └── InventoryDocumentationModal.test.tsx
│   ├── assets/                         # KEPT: SVGs for InventoryDocModal
│   │   ├── lightspeed.svg
│   │   └── lightspeed_dark.svg
│   └── reportWebVitals.ts             # KEPT: trivial
├── index.html                          # KEPT: Django template
├── vite.config.ts                      # KEPT: SPA build config
├── tsconfig.json                       # KEPT
├── package.json                        # MODIFIED
└── eslint.config.mjs                   # KEPT
```

### 2.9 Update tests

**`App.test.tsx`**:
- Update import paths: `conversationStore`, `ColorThemeSwitch`, etc. now come from `@ansible/ansible-ai-connect-chatbot`
- Test assertions remain unchanged (the config preserves identical runtime behavior)
- Remove tests for deleted local components

**`InventoryDocumentationModal.test.tsx`**: Keep unchanged.

**Delete** test files for components now provided by the package:
- `useChatbot.test.ts`
- `MarkdownLinkBuffer.test.ts`
- `Constants.test.ts`
- `AnsibleChatbot.test.tsx`

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `import.meta.env.PROD` in npm package code | When the hook code is in the package, `import.meta.env.PROD` reflects the **consumer's** build, not the package's | This is actually correct behavior — the consumer's Vite build determines prod/dev |
| DOM-based config (`document.getElementById`) runs at import time | `userName`, `botName` are set when the module loads | Works fine because Django injects hidden divs before JS executes |
| CSS ordering conflicts | Package CSS vs. consumer CSS specificity | Import order: PatternFly base -> package CSS -> local overrides |
| Package publish cycle for shared changes | Changes to shared code require npm publish before SPA picks them up | Acceptable trade-off; alternative (workspaces) was considered and rejected |
| Assets in npm package (`lightspeed.svg`) | Need to be importable by Vite when used as dependency | Already handled: the package re-exports them as ES module imports; Vite resolves them correctly |
| Backward compatibility for existing npm consumers | Adding config must not break `<App username="..." />` | All config fields are optional with defaults matching current behavior |

---

## Verification Checklist

1. **Package tests**: `cd aap_chatbot && npm test` — all existing tests pass
2. **Package build**: `cd aap_chatbot && npm run build` — produces ESM, UMD, CSS, type declarations
3. **Consumer install**: `cd ansible_ai_connect_chatbot && npm install` — package resolves
4. **Consumer tests**: `cd ansible_ai_connect_chatbot && npm test` — all tests pass
5. **Consumer build**: `cd ansible_ai_connect_chatbot && npm run build` — SPA output in `dist/`, postbuild rsync succeeds
6. **Django integration**: Start dev server, navigate to chatbot:
   - [ ] Welcome greeting shows "Hello, Ansible User"
   - [ ] 3 suggestion prompts render and are clickable
   - [ ] Preview label with tooltip visible
   - [ ] InventoryDocumentationModal opens and closes
   - [ ] Brand logos visible, switch with dark/light mode
   - [ ] Model selector dropdown appears in debug mode
   - [ ] Chat messages work (non-streaming and streaming)
   - [ ] Thumbs up/down feedback works
   - [ ] Dark mode toggle works
7. **Backward compatibility**: `<App username="someone" />` (no config) in aap context works identically

---

## Summary of Changes

| Area | Files Created | Files Modified | Files Deleted |
|------|--------------|----------------|---------------|
| `aap_chatbot/` (npm package) | 1 | 5 | 0 |
| `ansible_ai_connect_chatbot/` (SPA) | 2 | 4 | ~15 |

**Net result**: ~15 duplicated source files eliminated. The SPA shrinks from ~20 source files to ~7, with the npm package as the single source of truth for all shared chatbot logic.
