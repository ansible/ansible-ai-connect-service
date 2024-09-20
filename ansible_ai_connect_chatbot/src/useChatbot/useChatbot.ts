import axios from "axios";
import { useState } from "react";
import { v4 as uuidv4 } from "uuid";

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

export const useChatbot = () => {
  const [messages, setMessages] = useState<object[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  let conversation_id: string;
  const handleSend = async (message: any) => {
    setMessages((msgs) => [
      ...msgs,
      {
        role: "user",
        content: message,
        name: "User",
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
      resp = await axios.post("http://10.22.9.112:8080/v1/query/", request, {
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
      });
    } finally {
      setIsLoading(false);
    }

    console.log(`handleSend: status=${resp.status}`);
    console.log(JSON.stringify(resp.data, null, 2));
    if (resp.status === 200) {
      let content = resp.data.response;
      if (resp.data.referenced_documents.length > 0) {
        content += "\n\nRefer to the following for more information:\n";
        for (const doc of resp.data.referenced_documents) {
          content += `- [${doc.title}](${doc.docs_url})\n`;
        }
      }
      setMessages((msgs) => [
        ...msgs,
        {
          role: "bot",
          content,
          name: "Ansible Lightspeed Bot",
          avatar:
            "https://access.redhat.com/sites/default/files/images/product_icon-red_hat-ansible_automation_platform-rgb_0.png",
        },
      ]);
    }
  };

  return { messages, isLoading, handleSend };
};
