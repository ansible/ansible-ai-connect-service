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
  setCurrentConversation: (
    id: string | undefined,
    msgs: ExtendedMessage[],
  ) => void;
  inDebugMode: boolean;
  bypassTools: boolean;
  setBypassTools: (v: boolean) => void;
  selectedModel: string;
  setSelectedModel: (v: string) => void;
  models: LLMModel[];
  bodyElement: HTMLElement;
}

export interface ChatbotConfig {
  apiBasePath?: string;
  models?: LLMModel[];
  username?: string;
  welcomeTitle?: string;
  welcomePrompts?: WelcomePromptItem[];
  renderHeader?: (props: HeaderRenderProps) => ReactNode;
  includeQueryInFeedbackUrl?: boolean;
}
