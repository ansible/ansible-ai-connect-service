import "./index.css";
import "@patternfly/react-core/dist/styles/base.css";
import "@patternfly/chatbot/dist/css/main.css";

export { App } from "./App";
export type { ChatbotContext } from "./App";
export { AnsibleChatbot } from "./AnsibleChatbot/AnsibleChatbot";
export type { ChatbotProps } from "./AnsibleChatbot/AnsibleChatbot";
export { conversationStore } from "./AnsibleChatbot/AnsibleChatbot";
export { ColorThemeSwitch } from "./ColorThemeSwitch/ColorThemeSwitch";
export { DebugSettingsModal } from "./DebugSettingsModal/DebugSettingsModal";
export {
  useChatbot,
  readCookie,
  readCsrfCookie,
  inDebugMode,
  bodyElement,
  DEFAULT_MODELS,
  DEFAULT_API_BASE_PATH,
} from "./useChatbot/useChatbot";
export type { UseChatbotConfig } from "./useChatbot/useChatbot";
export {
  getProductName,
  Sentiment,
  FOOTNOTE_LABEL,
  CHAT_HISTORY_HEADER,
  REFERENCED_DOCUMENTS_CAPTION,
} from "./Constants";

export type {
  ChatbotConfig,
  WelcomePromptItem,
  HeaderRenderProps,
} from "./types/ChatbotConfig";
export type { ExtendedMessage, ReferencedDocument } from "./types/Message";
export type { LLMModel } from "./types/Model";

import LIGHTSPEED_LOGO from "./public/lightspeed.svg";
export { LIGHTSPEED_LOGO };
import LIGHTSPEED_LOGO_DARK from "./public/lightspeed_dark.svg";
export { LIGHTSPEED_LOGO_DARK };
