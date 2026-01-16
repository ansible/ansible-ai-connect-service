import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useEffect, useState } from "react";
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
import logo from "../public/lightspeed.svg";
import userLogo from "../public/user_logo.png";
import {
  ANSIBLE_LIGHTSPEED_PRODUCT_NAME,
  API_TIMEOUT,
  GITHUB_NEW_ISSUE_BASE_URL,
  INITIAL_NOTICE,
  QUERY_SYSTEM_INSTRUCTION,
  REFERENCED_DOCUMENTS_CAPTION,
  Sentiment,
  TIMEOUT_MSG,
  TOO_MANY_REQUESTS_MSG,
} from "../Constants";
import { setClipboard } from "../Clipboard";

const userName = document.getElementById("user_name")?.innerText ?? "User";
const botName =
  document.getElementById("bot_name")?.innerText ??
  ANSIBLE_LIGHTSPEED_PRODUCT_NAME;

export const modelsSupported: LLMModel[] = [
  { model: "granite-3.3-8b-instruct", provider: "rhoai" },
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

const isTimeoutError = (e: any) => e.name === "AbortError";

const isTooManyRequestsError = (e: any) =>
  e instanceof Response && e.status === 429;

const INFERENCE_MESSAGE_PROMPT = "\n\n`inference>`";
const INFERENCE_MESSAGE_PROMPT_REGEX = new RegExp(
  INFERENCE_MESSAGE_PROMPT,
  "mg", // 'm' for 'multiline' and 'g' for 'global'
);

const countInferenceMessagePrompts = (content: string | undefined): number => {
  if (!content) {
    return 0;
  }
  return (content.match(INFERENCE_MESSAGE_PROMPT_REGEX) || []).length;
};

export const fixedMessage = (content: string): MessageProps => ({
  role: "bot",
  content,
  name: botName,
  avatar: logo,
  timestamp: getTimestamp(),
});

export const feedbackMessage = (
  f: ChatFeedback,
  conversation_id: string,
): MessageProps => ({
  role: "bot",
  content:
    f.sentiment === Sentiment.THUMBS_UP
      ? "Thank you for your feedback!"
      : "Thank you for your feedback. If you have more to share, please click the button below (_requires GitHub login_). " +
        "\n\n Do not include any personal information or other sensitive information in your feedback. " +
        "Feedback may be used to improve Red Hat's products or services.",
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
                .open(createGitHubIssueURL(f, conversation_id), "_blank")
                ?.focus(),
          },
        ],
});

export const timeoutMessage = (): MessageProps => fixedMessage(TIMEOUT_MSG);
export const tooManyRequestsMessage = (): MessageProps =>
  fixedMessage(TOO_MANY_REQUESTS_MSG);

const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

const createGitHubIssueURL = (
  f: ChatFeedback,
  conversation_id: string,
): string => {
  const searchParams: URLSearchParams = new URLSearchParams();
  searchParams.append("assignees", "korenaren");
  searchParams.append("labels", "bug,triage");
  searchParams.append("projects", "");
  searchParams.append("template", "chatbot_feedback.yml");
  searchParams.append("conversation_id", conversation_id);
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

// For fixing tooltips that pops up from an iframe
export let bodyElement = document.body;

export const useChatbot = () => {
  const [messages, setMessages] = useState<ExtendedMessage[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [alertMessage, setAlertMessage] = useState<AlertMessage | undefined>(
    INITIAL_NOTICE,
  );
  const [conversationId, setConversationId] = useState<
    string | null | undefined
  >(undefined);

  // Workaround for the lag issue of the conversation_id state value.
  const getConversationId = () => {
    let id;
    setConversationId((value) => {
      id = value;
      return value;
    });
    if (!id) {
      id = "00000000-0000-0000-0000-000000000000";
    }
    return id;
  };

  const [selectedModel, setSelectedModel] = useState("granite-3.3-8b-instruct");
  const [systemPrompt, setSystemPrompt] = useState(QUERY_SYSTEM_INSTRUCTION);
  const [hasStopButton, setHasStopButton] = useState<boolean>(false);
  const [abortController, setAbortController] = useState(new AbortController());
  const [bypassTools, setBypassTools] = useState<boolean>(false);

  const [stream, setStream] = useState(false);
  useEffect(() => {
    const frameWindow = window[0];
    if (frameWindow) {
      bodyElement = frameWindow.document.getElementsByTagName("body")[0];
    }
    const checkStatus = async () => {
      const csrfToken = readCookie("csrftoken");
      try {
        const resp = await fetch("/api/lightspeed/v1/health/status/chatbot/", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken || "",
          },
        });
        if (resp.ok) {
          const data = await resp.json();
          if ("streaming-chatbot-service" in data) {
            if (data["streaming-chatbot-service"] === "ok") {
              // If streaming is enabled on the service side, use it.
              setStream(true);
            }
          }
        }
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
      } catch (e) {
        // Ignore errors thrown and use non-streaming chat.
      }
    };
    checkStatus();
  }, []);

  const isStreamingSupported = () => {
    // For making streaming mode debug easier.
    if (!import.meta.env.PROD && import.meta.env.MODE.includes("stream")) {
      return true;
    }
    return stream;
  };

  const addMessage = (
    newMessage: ExtendedMessage,
    addAfter?: ExtendedMessage,
  ) => {
    setMessages((msgs: ExtendedMessage[]) => {
      const newMsgs: ExtendedMessage[] = [];
      // Only set scrollToHere if message is added at the end (not inserted inline)
      newMessage.scrollToHere = !isStreamingSupported() && !addAfter;
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
          conversation_id: getConversationId(),
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
        tooltipProps: { appendTo: bodyElement, content: "Good response" },
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
        tooltipProps: { appendTo: bodyElement, content: "Bad response" },
      },
      copy: {
        onClick: () => {
          if (message.actions) {
            const contents = [message.content];
            if (message.referenced_documents.length > 0) {
              contents.push(`\n${REFERENCED_DOCUMENTS_CAPTION}`);
              const ref_docs = message.referenced_documents.map(
                (doc) => `- [${doc.title}](${doc.docs_url})`,
              );
              contents.push(...ref_docs);
            }
            setClipboard(contents.join("\n"));
          }
        },
        tooltipProps: { appendTo: bodyElement, content: "Copy" },
      },
    };

    // Hide action icons while streaming
    if (isStreamingSupported()) {
      message.actions.positive.className =
        message.actions.negative.className =
        message.actions.copy.className =
          "action-button-hidden";
    }

    return message;
  };

  // Show action icons when the end of
  const showActionIcons = () => {
    setMessages((msgs: ExtendedMessage[]) => {
      const message = msgs[msgs.length - 1];
      if (message?.actions && message?.role === "bot") {
        message.actions.positive.className =
          message.actions.negative.className =
          message.actions.copy.className =
            "";
      }
      return msgs;
    });
  };

  const handleFeedback = async (feedbackRequest: ChatFeedback) => {
    try {
      const csrfToken = readCookie("csrftoken");
      const resp = await fetch(
        import.meta.env.PROD
          ? "/api/lightspeed/v1/ai/feedback/"
          : "http://localhost:8080/v1/feedback/",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken || "",
          },
          body: JSON.stringify({
            chatFeedback: feedbackRequest,
          }),
        },
      );
      if (resp.ok) {
        const newBotMessage = {
          referenced_documents: [],
          ...feedbackMessage(feedbackRequest, getConversationId()),
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

  const show429Message = async () => {
    // Insert a 3-sec delay before showing the "Too Many Request" message
    // for reducing the number of chat requests when the server is busy.
    await delay(3000);
    const newBotMessage = {
      referenced_documents: [],
      ...tooManyRequestsMessage(),
    };
    addMessage(newBotMessage);
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
    if (bypassTools) {
      chatRequest.no_tools = true;
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
            openWhenHidden: true,
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json,text/event-stream",
              "X-CSRFToken": csrfToken!,
            },
            body: JSON.stringify(chatRequest),
            async onopen(resp: any) {
              if (resp.status === 429) {
                await show429Message();
              } else if (resp.status >= 400 && resp.status < 500) {
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
                    JSON.stringify(message.data.token) +
                    "\n```\n",
                );
              } else if (message.event === "turn_complete") {
                setMessages((msgs: ExtendedMessage[]) => {
                  const lastMessage = msgs[msgs.length - 1];
                  const n = countInferenceMessagePrompts(lastMessage.content);
                  if (n === 1) {
                    lastMessage.content = lastMessage.content
                      ?.replace(INFERENCE_MESSAGE_PROMPT, "")
                      .replace("<noinput>", "");
                    return [...msgs];
                  } else if (n > 1) {
                    const i = lastMessage.content?.lastIndexOf(
                      INFERENCE_MESSAGE_PROMPT,
                    );
                    lastMessage.content = lastMessage.content?.substring(0, i);
                  }
                  lastMessage.collapse = true;
                  const newMessage = botMessage(
                    message.data.token,
                    query.toString(),
                  );
                  return [...msgs, newMessage];
                });
              }
            },
            onclose() {
              console.log("Connection closed by the server");
              showActionIcons();
            },
            onerror(err) {
              console.log("There was an error from server", err);
              showActionIcons();
            },
            signal: abortController.signal,
          },
        );
      } else {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);

        try {
          const resp = await fetch(
            import.meta.env.PROD
              ? "/api/lightspeed/v1/ai/chat/"
              : "http://localhost:8080/v1/query/",
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken || "",
              },
              body: JSON.stringify(chatRequest),
              signal: controller.signal,
            },
          );

          clearTimeout(timeoutId);

          if (!resp.ok) {
            if (resp.status === 429) {
              throw resp;
            }
            setAlertMessage({
              title: "Error",
              message: `Bot returned status_code ${resp.status}`,
              variant: "danger",
            });
            return;
          }

          const chatResponse: ChatResponse = await resp.json();
          const referenced_documents = chatResponse.referenced_documents;
          if (!conversationId) {
            setConversationId(chatResponse.conversation_id);
          }
          const newBotMessage: any = botMessage(chatResponse, query.toString());
          newBotMessage.referenced_documents = referenced_documents;
          addMessage(newBotMessage);
        } catch (fetchError) {
          clearTimeout(timeoutId);
          throw fetchError;
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
        await show429Message();
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
    isStreamingSupported,
    bypassTools,
    setBypassTools,
  };
};
