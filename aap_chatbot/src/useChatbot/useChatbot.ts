import axios from "axios";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useState } from "react";
import type { MessageProps } from "@patternfly/chatbot/dist/dynamic/Message";
import type {
  AlertMessage,
  ExtendedMessage,
  ChatRequest,
  ChatResponse,
  ChatFeedback,
  RagChunk,
  ReferencedDocument,
} from "../types/Message";
import type { LLMModel } from "../types/Model";
import logo from "../assets/lightspeed.svg";
import userLogo from "../assets/user_logo.png";
import {
  API_TIMEOUT,
  GITHUB_NEW_ISSUE_BASE_URL,
  INITIAL_NOTICE,
  QUERY_SYSTEM_INSTRUCTION,
  Sentiment,
  TIMEOUT_MSG,
  TOO_MANY_REQUESTS_MSG,
} from "../Constants";
import { setClipboard } from "../Clipboard";

const userName = document.getElementById("user_name")?.innerText ?? "User";
const botName =
  document.getElementById("bot_name")?.innerText ?? "Ansible Lightspeed";

export const modelsSupported: LLMModel[] = [
  { model: "granite3-1-8b", provider: "my_rhoai_g31" },
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

export const isStreamingSupported = () => {
  // For making streaming mode debug easier.
  if (!import.meta.env.PROD && import.meta.env.MODE.includes("stream")) {
    return true;
  }
  const stream = document.getElementById("stream")?.innerText ?? "false";
  return stream === "true";
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
  const [selectedModel, setSelectedModel] = useState("granite3-1-8b");
  const [systemPrompt, setSystemPrompt] = useState(QUERY_SYSTEM_INSTRUCTION);
  const [hasStopButton, setHasStopButton] = useState<boolean>(false);
  const [abortController, setAbortController] = useState(new AbortController());

  const addMessage = (
    newMessage: ExtendedMessage,
    addAfter?: ExtendedMessage,
  ) => {
    setMessages((msgs: ExtendedMessage[]) => {
      const newMsgs: ExtendedMessage[] = [];
      newMessage.scrollToHere = !isStreamingSupported();
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

  const appendMessageChunk = (chunk: string, query: string = "") => {
    setMessages((msgs: ExtendedMessage[]) => {
      const lastMessage = msgs[msgs.length - 1];
      if (!lastMessage || lastMessage.role === "user") {
        const newMessage: ExtendedMessage = botMessage(chunk, query);
        chunk = "";
        return [...msgs, newMessage];
      } else {
        lastMessage.content += chunk;
        chunk = "";
        return [...msgs];
      }
    });
  };

  const addReferencedDocuments = (ragChunks: RagChunk[]) => {
    setMessages((msgs: ExtendedMessage[]) => {
      if (ragChunks.length === 0) {
        return msgs;
      }
      const referenced_documents: ReferencedDocument[] = [];
      for (const ragChunk of ragChunks) {
        referenced_documents.push({
          title: ragChunk.doc_title,
          docs_url: ragChunk.doc_url,
        });
      }
      const lastMessage = msgs[msgs.length - 1];
      if (!lastMessage || lastMessage.role === "user") {
        const newMessage: ExtendedMessage = botMessage("");
        return [...msgs, newMessage];
      } else {
        lastMessage.referenced_documents = referenced_documents;
        return [...msgs];
      }
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
    const sendFeedback = async (
      sentiment: Sentiment,
      content: string = "",
      referenced_documents: ReferencedDocument[] = [],
    ) => {
      if (typeof response === "string") {
        const resp = {
          conversation_id: conversationId
            ? conversationId
            : "00000000-0000-0000-0000-000000000000",
          response: content,
          referenced_documents,
          truncated: false,
        };
        handleFeedback({ query, response: resp, sentiment, message });
      } else {
        handleFeedback({ query, response, sentiment, message });
      }
    };

    message.actions = {
      positive: {
        onClick: () => {
          sendFeedback(
            Sentiment.THUMBS_UP,
            message.content,
            message.referenced_documents,
          );
          if (message.actions) {
            message.actions.positive.isDisabled = true;
            message.actions.negative.isDisabled = true;
            message.actions.positive.className = "action-button-clicked";
          }
        },
      },
      negative: {
        onClick: () => {
          sendFeedback(
            Sentiment.THUMBS_DOWN,
            message.content,
            message.referenced_documents,
          );
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
              setClipboard(
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
          ? "/api/lightspeed/v1/ai/feedback/"
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

  const handleStopButton = () => {
    abortController.abort();
    setAbortController(new AbortController());
  };

  const handleSend = async (query: string | number) => {
    const userMessage: ExtendedMessage = {
      role: "user",
      content: query.toString(),
      name: userName,
      avatar: userLogo,
      timestamp: getTimestamp(),
      referenced_documents: [],
    };
    addMessage(userMessage);

    const chatRequest: ChatRequest = {
      conversation_id: conversationId,
      query: query.toString(),
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

      if (isStreamingSupported()) {
        setHasStopButton(true);
        chatRequest.media_type = "application/json";
        await fetchEventSource(
          import.meta.env.PROD
            ? "/api/lightspeed/v1/ai/streaming_chat/"
            : "http://localhost:8080/v1/streaming_query",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json,text/event-stream",
              "X-CSRFToken": csrfToken!,
            },
            body: JSON.stringify(chatRequest),
            async onopen(resp: any) {
              if (
                resp.status >= 400 &&
                resp.status < 500 &&
                resp.status !== 429
              ) {
                setAlertMessage({
                  title: "Error",
                  message: `Bot returned status_code ${resp.status}`,
                  variant: "danger",
                });
              }
            },
            onmessage(msg: any) {
              let message = msg;
              if (!msg.event) {
                message = JSON.parse(msg.data);
              } else {
                message.data = JSON.parse(msg.data);
              }
              if (message.event === "start") {
                if (!conversationId) {
                  setConversationId(message.data.conversation_id);
                }
              } else if (message.event === "token") {
                if (message.data.token !== "") {
                  setIsLoading(false);
                }
                appendMessageChunk(message.data.token, query.toString());
              } else if (message.event === "end") {
                if (message.data.referenced_documents.length > 0) {
                  addReferencedDocuments(message.data.referenced_documents);
                }
              } else if (message.event === "error") {
                const data = message.data;
                setAlertMessage({
                  title: "Error",
                  message:
                    `Bot returned an error: response="${data.response}", ` +
                    `cause="${data.cause}"`,
                  variant: "danger",
                });
              } else if (
                message.event === "tool_call" ||
                message.event === "step_complete"
              ) {
                console.log(
                  `!![${message.event}] ${JSON.stringify(message.data)}`,
                );
                appendMessageChunk(
                  "\n\n`[" +
                    message.event +
                    "]`\n```json\n" +
                    message.data.token +
                    "\n```\n",
                );
              } else if (message.event === "turn_complete") {
                setMessages((msgs: ExtendedMessage[]) => {
                  const lastMessage = msgs[msgs.length - 1];
                  lastMessage.collapse = true;
                  msgs.push(botMessage(message.data.token));
                  return msgs;
                });
              }
            },
            onclose() {
              console.log("Connection closed by the server");
            },
            onerror(err) {
              console.log("There was an error from server", err);
            },
            signal: abortController.signal,
          },
        );
      } else {
        const resp = await axios.post(
          import.meta.env.PROD
            ? "/api/lightspeed/v1/ai/chat/"
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
          const newBotMessage: any = botMessage(chatResponse, query.toString());
          newBotMessage.referenced_documents = referenced_documents;
          addMessage(newBotMessage);
        } else {
          setAlertMessage({
            title: "Error",
            message: `Bot returned status_code ${resp.status}`,
            variant: "danger",
          });
        }
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
      if (isStreamingSupported()) {
        setHasStopButton(false);
      }
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
    conversationId,
    setConversationId,
    systemPrompt,
    setSystemPrompt,
    hasStopButton,
    handleStopButton,
  };
};
