import axios from "axios";
import { useState } from "react";
import { v4 as uuidv4 } from "uuid";

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
    };

    setIsLoading(true);
    let resp: any;
    try {
      resp = await axios.post("http://localhost:8080/v1/query", request, {
        headers: { "Content-Type": "application/json" },
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
        },
      ]);
    }
  };

  return { messages, isLoading, handleSend };
};
