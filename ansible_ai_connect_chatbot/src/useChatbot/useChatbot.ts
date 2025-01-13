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
  GITHUB_NEW_ISSUE_BASE_URL,
  QUERY_SYSTEM_INSTRUCTION,
  Sentiment,
  TIMEOUT_MSG,
  TOO_MANY_REQUESTS_MSG,
} from "../Constants";

const userName = document.getElementById("user_name")?.innerText ?? "User";
const botName =
  document.getElementById("bot_name")?.innerText ?? "Ansible Lightspeed";

export const modelsSupported: LLMModel[] = [
  { model: "granite3-8b", provider: "my_rhoai_g3" },
  { model: "granite31-8b", provider: "my_rhoai_g31" },
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
              window.open(createGitHubIssueURL(f), "_blank")?.focus(),
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
  message: `The Red Hat Ansible Automation Platform Lightspeed service provides
  answers to questions related to the Ansible Automation Platform. Please refrain
  from including personal or business sensitive information in your input.
  Interactions with the Ansible Automation Platform Lightspeed may be reviewed
  and utilized to enhance our products and services. `,
  variant: "info",
};

const createGitHubIssueURL = (f: ChatFeedback): string => {
  const searchParams: URLSearchParams = new URLSearchParams();
  searchParams.append("assignees", "korenaren");
  searchParams.append("labels", "bug,triage");
  searchParams.append("projects", "");
  searchParams.append("template", "chatbot_feedback.yml");
  searchParams.append("conversation_id", f.response.conversation_id);
  searchParams.append("prompt", f.query);
  searchParams.append("response", f.response.response);
  // Referenced documents may increase as more source documents being ingested,
  // so let's be try not to generate long length for query parameter "ref_docs",
  // otherwise GH returns 414 URI Too Long error page. Assuming max of 30 docs.
  // See https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue#creating-an-issue-from-a-url-query.
  searchParams.append(
    "ref_docs",
    f.response.referenced_documents
      ?.slice(0, 30)
      .map((doc) => doc.docs_url)
      .join("\n"),
  );

  const url = new URL(GITHUB_NEW_ISSUE_BASE_URL);
  url.search = searchParams.toString();
  return url.toString();
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
  const [selectedModel, setSelectedModel] = useState("granite3-8b");
  const [systemPrompt, setSystemPrompt] = useState(QUERY_SYSTEM_INSTRUCTION);

  const addMessage = (
    newMessage: ExtendedMessage,
    addAfter?: ExtendedMessage,
  ) => {
    setMessages((msgs: ExtendedMessage[]) => {
      const newMsgs: ExtendedMessage[] = [];
      newMessage.scrollToHere = true;
      let inserted = false;
      for (const msg of msgs) {
        msg.scrollToHere = false;
        newMsgs.push(msg);
        if (msg === addAfter) {
          newMsgs.push(newMessage);
          inserted = true;
        }
      }
      if (!inserted) {
        newMsgs.push(newMessage);
      }
      return newMsgs;
    });
  };

  const botMessage = (
    response: ChatResponse | string,
    query = "",
  ): ExtendedMessage => {
    const message: ExtendedMessage = {
      role: "bot",
      content: typeof response === "object" ? response.response : response,
      name: botName,
      avatar: logo,
      timestamp: getTimestamp(),
      referenced_documents: [],
    };
    const sendFeedback = async (sentiment: Sentiment) => {
      if (typeof response === "object") {
        handleFeedback({ query, response, sentiment, message });
      }
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
      copy: {
        onClick: () => {
          if (message.actions) {
            message.actions.copy.className = "action-button-clicked";
            const ref_docs =
              typeof response === "object"
                ? response.referenced_documents?.slice(0, 5)
                : response;
            if (ref_docs) {
              const llmResponse = [
                typeof response === "object" ? response.response : response,
                ",\n",
                typeof response === "object"
                  ? response.referenced_documents
                      ?.slice(0, 5)
                      .map((doc) => doc.docs_url)
                      .join(",\n")
                  : response,
              ];
              navigator.clipboard.writeText(
                llmResponse?.map((llmResponse) => llmResponse).join(""),
              );
            }
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
        import.meta.env.PROD
          ? "/api/v0/ai/feedback/"
          : "http://localhost:8080/v1/feedback/",
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
        addMessage(newBotMessage, feedbackRequest.message);
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
        message: `An unexpected error occurred: ${e}`,
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

    if (systemPrompt !== QUERY_SYSTEM_INSTRUCTION) {
      chatRequest.system_prompt = systemPrompt;
    }

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
          message: `An unexpected error occurred: ${e}`,
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
    systemPrompt,
    setSystemPrompt,
  };
};
