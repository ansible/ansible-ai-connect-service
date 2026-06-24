import React from "react";
import {
  AnsibleChatbot,
  ChatbotProps,
} from "./AnsibleChatbot/AnsibleChatbot";
import type { ChatbotConfig } from "./types/ChatbotConfig";

export interface ChatbotContext {
  username?: string | undefined;
  config?: Partial<ChatbotConfig>;
}

export const App: React.FunctionComponent<ChatbotContext> = (
  context: ChatbotContext,
) => {
  const props: ChatbotProps = {
    username: context?.username,
    ...context?.config,
  };
  return <AnsibleChatbot {...props} />;
};

App.displayName = "App";
