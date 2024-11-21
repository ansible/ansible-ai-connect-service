import axios from "axios";
import { useState } from "react";
import type { MessageProps } from "@patternfly/virtual-assistant/dist/dynamic/Message";
import type {
  ExtendedMessage,
  ChatRequest,
  ChatResponse,
  ChatFeedback,
} from "../types/Message";
import type { LLMModel } from "../types/Model";
import logo from "../assets/lightspeed.svg";
import userLogo from "../assets/user_logo.png";
import { API_TIMEOUT, Sentiment, TIMEOUT_MSG } from "../Constants";

const userName = document.getElementById("user_name")?.innerText ?? "User";
const botName =
  document.getElementById("bot_name")?.innerText ?? "Ansible Lightspeed";

export const modelsSupported: LLMModel[] = [
  { model: "granite-8b", provider: "my_rhoai" },
  { model: "granite3-8b", provider: "my_rhoai_g3" },
];

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

const getTimestamp = () => {
  const date = new Date();
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
};

export const inDebugMode = () => {
  // In the production environment, the debug UI becomes available only when the innter text of
  // the hidden debug div is set to "true". In the debug environment, the debug UI is enabled by
  // default and can be disabled by setting the innter text of the debug div is set to "false"
  const debug = document.getElementById("debug")?.innerText ?? "false";
  return import.meta.env.PROD ? debug === "true" : debug !== "false";
};

const isTimeoutError = (e: any) =>
  e?.name === "AxiosError" &&
  e?.message === `timeout of ${API_TIMEOUT}ms exceeded`;

export const timeoutMessage = (): MessageProps => ({
  role: "bot",
  content: TIMEOUT_MSG,
  name: botName,
  avatar: logo,
  timestamp: getTimestamp(),
});

type AlertMessage = {
  title: string;
  message: string;
  variant: "success" | "danger" | "warning" | "info" | "custom";
};

const INITIAL_NOTICE: AlertMessage = {
  title: "Important",
  message: `Red Hat Ansible Automation Platform Lightspeed can answer questions
related to Ansible Automation Platform. Do not include personal or buisness
sensitive information in your input. Interactions with Ansible Automation Platform
Lightspeed may be reviewed and used to improve our products and services`,
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
  const [selectedModel, setSelectedModel] = useState("granite-8b");

  const addMessage = (newMessage: ExtendedMessage) => {
    setMessages((msgs: ExtendedMessage[]) => [...msgs, newMessage]);
  };

  const botMessage = (
    response: ChatResponse | string,
    query = "",
  ): MessageProps => {
    const sendFeedback = async (sentiment: Sentiment) => {
      if (typeof response === "object") {
        handleFeedback({ query, response, sentiment });
      }
    };
    return {
      role: "bot",
      content: typeof response === "object" ? response.response : response,
      name: botName,
      avatar: logo,
      timestamp: getTimestamp(),
      actions: {
        positive: {
          onClick: () => {
            sendFeedback(Sentiment.THUMBS_UP);
          },
        },
        negative: {
          onClick: () => {
            sendFeedback(Sentiment.THUMBS_DOWN);
          },
        },
      },
    };
  };

  const handleFeedback = async (feedbackRequest: ChatFeedback) => {
    try {
      const csrfToken = readCookie("csrftoken");
      const resp = await axios.post(
        "/api/v0/ai/feedback/",
        {
          chatFeedback: feedbackRequest,
        },
        {
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
        },
      );
      if (resp.status !== 200) {
        setAlertMessage({
          title: "Error",
          message: `Feedback API returned status_code ${resp.status}`,
          variant: "danger",
        });
      }
    } catch (e) {
      setAlertMessage({
        title: "Error",
        message: `An unexpected error occured: ${e}`,
        variant: "danger",
      });
    }
  };

  const handleSend = async (message: string) => {
    const userMessage: ExtendedMessage = {
      role: "user",
      content: message,
      name: userName,
      avatar: userLogo,
      timestamp: getTimestamp(),
      referenced_documents: [],
    };
    addMessage(userMessage);

    const chatRequest: ChatRequest = {
      conversation_id: conversationId,
      query: message,
    };

    if (inDebugMode()) {
      for (const m of modelsSupported) {
        if (selectedModel === m.model) {
          chatRequest.model = m.model;
          chatRequest.provider = m.provider;
        }
      }
    }

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
          timeout: API_TIMEOUT,
        },
      );
      if (resp.status === 200) {
        const chatResponse: ChatResponse = resp.data;
        const referenced_documents = chatResponse.referenced_documents;
        if (!conversationId) {
          setConversationId(chatResponse.conversation_id);
        }
        const newBotMessage = {
          referenced_documents,
          ...botMessage(chatResponse, message),
        };
        addMessage(newBotMessage);
      } else {
        setAlertMessage({
          title: "Error",
          message: `Bot returned status_code ${resp.status}`,
          variant: "danger",
        });
      }
    } catch (e) {
      if (isTimeoutError(e)) {
        const newBotMessage = {
          referenced_documents: [],
          ...timeoutMessage(),
        };
        addMessage(newBotMessage);
      } else {
        setAlertMessage({
          title: "Error",
          message: `An unexpected error occured: ${e}`,
          variant: "danger",
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  return {
    messages,
    setMessages,
    botMessage,
    isLoading,
    handleSend,
    alertMessage,
    setAlertMessage,
    selectedModel,
    setSelectedModel,
    setConversationId,
  };
};
