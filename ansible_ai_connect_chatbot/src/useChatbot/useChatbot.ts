import axios from "axios";
import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import type { MessageProps } from "@patternfly/virtual-assistant/dist/dynamic/Message";

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

export const botMessage = (content: any): MessageProps => {
  return {
    role: "bot",
    content,
    name: "Ansible Lightspeed Bot",
    avatar:
      "https://access.redhat.com/sites/default/files/images/product_icon-red_hat-ansible_automation_platform-rgb_0.png",
  };
};

export const useChatbot = () => {
  const [messages, setMessages] = useState<object[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  let conversation_id: string;
  const handleSend = async (message: any) => {
    setMessages((msgs: any) => [
      ...msgs,
      {
        message: {
          role: "user",
          content: message,
          name: "User",
        },
        referenced_documents: [],
      },
    ]);

    if (!conversation_id) {
      conversation_id = uuidv4().toString();
    }
    const request = {
      conversation_id,
      model: "llama3.1:latest",
      provider: "ollama",
      query: message,
      attachments: [],
    };

    setIsLoading(true);
    let resp: any;
    try {
      const csrfToken = readCookie("csrftoken");
      resp = await axios.post(
        "http://localhost:8080/v1/query/" /* "/api/v0/ai/talk/" */,
        request,
        {
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
        },
      );
    } finally {
      setIsLoading(false);
    }

    console.log(`handleSend: status=${resp.status}`);
    console.log(JSON.stringify(resp.data, null, 2));
    if (resp.status === 200) {
      let content = resp.data.response;
      const referenced_documents = resp.data.referenced_documents;
      setMessages((msgs: any) => [
        ...msgs,
        {
          message: botMessage(content),
          referenced_documents,
        },
      ]);
    }
  };

  return { messages, isLoading, handleSend };
};
