import axios from "axios";
import { useState } from "react";
import type { MessageProps } from "@patternfly/chatbot/dist/dynamic/Message";
import type {
  ExtendedMessage,
  ChatRequest,
  ChatResponse,
  ChatFeedback,
} from "../types/Message";
import type { LLMModel } from "../types/Model";
import logo from "../assets/lightspeed.svg";
import userLogo from "../assets/user_logo.png";
import {
  API_TIMEOUT,
  GITHUB_NEW_ISSUE_URL,
  Sentiment,
  TIMEOUT_MSG,
  TOO_MANY_REQUESTS_MSG,
} from "../Constants";

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
  axios.isAxiosError(e) && e.message === `timeout of ${API_TIMEOUT}ms exceeded`;

const isTooManyRequestsError = (e: any) =>
  axios.isAxiosError(e) && e.response?.status === 429;

export const fixedMessage = (content: string): MessageProps => ({
  role: "bot",
  content,
  name: botName,
  avatar: logo,
  timestamp: getTimestamp(),
});

export const feedbackMessage = (f: ChatFeedback): MessageProps => ({
  role: "bot",
  content:
    f.sentiment === Sentiment.THUMBS_UP
      ? "Thank you for your feedback!"
      : "Thank you for your feedback. If you have more to share, please click the button below (_requires GitHub login_).",
  name: botName,
  avatar: logo,
  timestamp: getTimestamp(),
  quickResponses:
    f.sentiment === Sentiment.THUMBS_UP
      ? []
      : [
          {
            content: "Sure!",
            id: "response",
            onClick: () =>
              window
                .open(
                  `${GITHUB_NEW_ISSUE_URL}&conversation_id=${f.response.conversation_id}&prompt=${f.query}&response=${f.response.response}`,
                  "_blank",
                )
                ?.focus(),
          },
        ],
});

export const timeoutMessage = (): MessageProps => fixedMessage(TIMEOUT_MSG);
export const tooManyRequestsMessage = (): MessageProps =>
  fixedMessage(TOO_MANY_REQUESTS_MSG);

const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

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
    const message: MessageProps = {
      role: "bot",
      content: typeof response === "object" ? response.response : response,
      name: botName,
      avatar: logo,
      timestamp: getTimestamp(),
    };

    message.actions = {
      positive: {
        onClick: () => {
          sendFeedback(Sentiment.THUMBS_UP);
          if (message.actions) {
            message.actions.positive.isDisabled = true;
            message.actions.negative.isDisabled = true;
            message.actions.positive.className = "action-button-clicked";
          }
        },
      },
      negative: {
        onClick: () => {
          sendFeedback(Sentiment.THUMBS_DOWN);
          if (message.actions) {
            message.actions.positive.isDisabled = true;
            message.actions.negative.isDisabled = true;
            message.actions.negative.className = "action-button-clicked";
          }
        },
      },
    };
    return message;
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
      if (resp.status === 200) {
        const newBotMessage = {
          referenced_documents: [],
          ...feedbackMessage(feedbackRequest),
        };
        addMessage(newBotMessage);
      } else {
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
        const newBotMessage: any = botMessage(chatResponse, message);
        newBotMessage.referenced_documents = referenced_documents;
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
      } else if (isTooManyRequestsError(e)) {
        // Insert a 3-sec delay before showing the "Too Many Request" message
        // for reducing the number of chat requests when the server is busy.
        await delay(3000);
        const newBotMessage = {
          referenced_documents: [],
          ...tooManyRequestsMessage(),
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
