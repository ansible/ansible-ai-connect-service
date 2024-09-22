import axios from "axios";
import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import type { MessageProps } from "@patternfly/virtual-assistant/dist/dynamic/Message";
import type {
  ExtendedMessage,
  LLMRequest,
  LLMResponse,
} from "../types/Message";

export const readCookie = (name: string): string | null => {
  const nameEQ = name + "=";
  const ca = document.cookie.split(";");
  for (let c of ca) {
    const cookie = c.trim();
    if (cookie.startsWith(nameEQ)) {
      return cookie.substring(nameEQ.length, cookie.length);
    }
  }
  return null;
};

export const botMessage = (content: string): MessageProps => {
  return {
    role: "bot",
    content,
    name: "Ansible Lightspeed Bot",
    avatar:
      "https://access.redhat.com/sites/default/files/images/product_icon-red_hat-ansible_automation_platform-rgb_0.png",
  };
};

export const useChatbot = () => {
  const [messages, setMessages] = useState<ExtendedMessage[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  let conversation_id: string;
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

    if (!conversation_id) {
      conversation_id = uuidv4().toString();
    }
    const llmRequest: LLMRequest = {
      conversation_id,
      query: message,
    };

    setIsLoading(true);
    try {
      const csrfToken = readCookie("csrftoken");
      const resp = await axios.post(
        "http://localhost:8080/v1/query/" /* "/api/v0/ai/talk/" */,
        llmRequest,
        {
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
        },
      );
      if (resp.status === 200) {
        const llmResponse: LLMResponse = resp.data;
        const referenced_documents = llmResponse.referenced_documents;
        setMessages((msgs: ExtendedMessage[]) => [
          ...msgs,
          {
            referenced_documents,
            ...botMessage(llmResponse.response),
          },
        ]);
      } else {
        setMessages((msgs: ExtendedMessage[]) => [
          ...msgs,
          {
            referenced_documents: [],
            ...botMessage(`Bot returned an error (status=${resp.status})`),
          },
        ]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return { messages, isLoading, handleSend };
};
