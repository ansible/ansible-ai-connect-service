import React from "react";
import { App as ChatbotApp } from "@ansible/ansible-ai-connect-chatbot";
import type { ChatbotConfig } from "@ansible/ansible-ai-connect-chatbot";
import { AnsibleAIConnectHeader } from "./AnsibleAIConnectHeader";

const config: Partial<ChatbotConfig> = {
  apiBasePath: "/api/v1",
  models: [{ model: "google/gemini-2.5-pro", provider: "vertexai" }],
  welcomeTitle: "Hello, Ansible User",
  welcomePrompts: [
    {
      title: "Using Ansible Automation Platform",
      message: "I have a question about using Ansible Automation Platform",
    },
    {
      title: "Installing Ansible Automation Platform",
      message:
        "I want to learn more about installing Ansible Automation Platform",
    },
    {
      title: "Operating Ansible Automation Platform",
      message:
        "I want to learn how to operate and monitor Ansible Automation Platform",
    },
  ],
  includeQueryInFeedbackUrl: false,
  renderHeader: (props) => <AnsibleAIConnectHeader {...props} />,
};

export const App = () => <ChatbotApp config={config} />;
