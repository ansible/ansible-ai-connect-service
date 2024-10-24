import axios from "axios";
import { useState } from "react";
import type { MessageProps } from "@patternfly/virtual-assistant/dist/dynamic/Message";
import type {
  ExtendedMessage,
  ChatRequest,
  ChatResponse,
} from "../types/Message";

export const readCookie = (name: string): string | null => {
  const nameEQ = name + "=";
  const ca = document.cookie.split(";");
  for (const c of ca) {
    const cookie = c.trim();
    if (cookie.startsWith(nameEQ)) {
      return cookie.substring(nameEQ.length, cookie.length);
    }
  }
  return null;
};

export const botMessage = (content: string): MessageProps => ({
  role: "bot",
  content,
  name: "Ansible Lightspeed Bot",
  avatar:
    "https://access.redhat.com/sites/default/files/images/product_icon-red_hat-ansible_automation_platform-rgb_0.png",
  actions: {
    positive: { onClick: () => console.log("Good response") },
    negative: { onClick: () => console.log("Bad response") },
  },
});

type AlertMessage = {
  title: string;
  message: string;
  variant: "success" | "danger" | "warning" | "info" | "custom";
};

const INITIAL_NOTICE: AlertMessage = {
  title: "Notice",
  message: `Please do not include any personal or confidential information
in your interaction with the virtual assistant. The tool is
intended to assist with general queries.`,
  variant: "info",
};

export const useChatbot = () => {
  const [messages, setMessages] = useState<ExtendedMessage[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [alertMessage, setAlertMessage] = useState<AlertMessage | undefined>(
    INITIAL_NOTICE,
  );
  const [conversationId, setConversationId] = useState<
    string | null | undefined
  >(undefined);

  const handleSend = async (message: string) => {
    const userMessage: ExtendedMessage = {
      role: "user",
      content: message,
      name: "User",
      avatar:
        "https://developers.redhat.com/sites/default/files/inline-images/Skill%20development_0.png",
      referenced_documents: [],
    };
    setMessages((msgs: ExtendedMessage[]) => [...msgs, userMessage]);

    const chatRequest: ChatRequest = {
      conversation_id: conversationId,
      query: message,
    };

    setIsLoading(true);
    try {
      const csrfToken = readCookie("csrftoken");
      const resp = await axios.post(
        import.meta.env.PROD
          ? "/api/v0/ai/chat/"
          : "http://localhost:8080/v1/query/",
        chatRequest,
        {
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
        },
      );
      if (resp.status === 200) {
        const chatResponse: ChatResponse = resp.data;
        const referenced_documents = chatResponse.referenced_documents;
        if (!conversationId) {
          setConversationId(chatResponse.conversation_id);
        }
        setMessages((msgs: ExtendedMessage[]) => [
          ...msgs,
          {
            referenced_documents,
            ...botMessage(chatResponse.response),
          },
        ]);
      } else {
        setAlertMessage({
          title: "Error",
          message: `Bot returned status_code ${resp.status}`,
          variant: "danger",
        });
      }
    } catch (e) {
      setAlertMessage({
        title: "Error",
        message: `An unexpected error occured: ${e}`,
        variant: "danger",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return { messages, isLoading, handleSend, alertMessage, setAlertMessage };
};
