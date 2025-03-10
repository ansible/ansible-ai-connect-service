import React from "react";
import {
  AnsibleChatbot,
  ChatbotContext,
} from "./AnsibleChatbot/AnsibleChatbot";

export const App: React.FunctionComponent<ChatbotContext> = (
  context: ChatbotContext,
) => <AnsibleChatbot username={context?.username} />;

App.displayName = "App";
