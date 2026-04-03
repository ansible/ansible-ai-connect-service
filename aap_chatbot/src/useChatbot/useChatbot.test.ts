import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { feedbackMessage, useChatbot } from "./useChatbot";
import type { MessageProps } from "@patternfly/chatbot/dist/dynamic/Message";
import { Sentiment } from "../Constants";
import type { ChatFeedback } from "../types/Message";
import * as fetchEventSourceModule from "@microsoft/fetch-event-source";

const CONVERSATION_ID = "123e4567-e89b-12d3-a456-426614174000";

// Mock fetchEventSource
vi.mock("@microsoft/fetch-event-source", () => ({
  fetchEventSource: vi.fn(),
}));

describe("feedbackMessage", () => {
  it("should return a message with a thank you note for positive feedback", () => {
    const feedback: ChatFeedback = {
      sentiment: Sentiment.THUMBS_UP,
      query: "",
      response: {
        conversation_id: "",
        response: "",
        referenced_documents: [],
        truncated: false,
      },
      message: {
        role: "user",
        content: "This is a test message",
        name: "User",
        avatar: "user_avatar",
        quickResponses: [],
        referenced_documents: [],
      },
    };
    const message: MessageProps = feedbackMessage(feedback, CONVERSATION_ID);

    expect(message.role).toBe("bot");
    expect(message.content).toBe("Thank you for your feedback!");
    expect(message.quickResponses).toEqual([]);
  });

  it("should return a message with a thank you note and a quick response for negative feedback", () => {
    const feedback: ChatFeedback = {
      sentiment: Sentiment.THUMBS_DOWN,
      query: "",
      response: {
        conversation_id: "",
        response: "",
        referenced_documents: [],
        truncated: false,
      },
      message: {
        role: "user",
        content: "This is a test message",
        name: "User",
        avatar: "user_avatar",
        quickResponses: [],
        referenced_documents: [],
      },
    };
    const message: MessageProps = feedbackMessage(feedback, CONVERSATION_ID);

    expect(message.role).toBe("bot");
    expect(message.content).toMatch(
      "Thank you for your feedback. If you have more to share, please click the button below (_requires GitHub login_). " +
        "\n\n Do not include any personal information or other sensitive information in your feedback. " +
        "Feedback may be used to improve Red Hat's products or services.",
    );
    expect(message.quickResponses).toEqual([
      {
        content: "Sure!",
        id: "response",
        onClick: expect.any(Function),
      },
    ]);
    // Check for the two line breaks
    expect(message.content).toMatch(/\n\n/);
  });
});

describe("useChatbot - fetchEventSource openWhenHidden", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock fetch for health check
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ "streaming-chatbot-service": "ok" }),
    });
    // Mock fetchEventSource to resolve immediately
    vi.mocked(fetchEventSourceModule.fetchEventSource).mockResolvedValue(
      undefined,
    );
  });

  it("should call fetchEventSource with openWhenHidden set to true", async () => {
    const { result } = renderHook(() => useChatbot());

    // Wait for the health check to complete and streaming to be enabled
    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    // Send a message to trigger fetchEventSource
    await result.current.handleSend("test query");

    // Wait for fetchEventSource to be called
    await waitFor(() => {
      expect(fetchEventSourceModule.fetchEventSource).toHaveBeenCalled();
    });

    // Verify that fetchEventSource was called with openWhenHidden: true
    expect(fetchEventSourceModule.fetchEventSource).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        openWhenHidden: true,
      }),
    );
  });
});

describe("useChatbot - auto-scroll during streaming", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock fetch for health check
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ "streaming-chatbot-service": "ok" }),
    });
  });

  it("should set scrollToHere flag when appending message chunks during streaming", async () => {
    let onmessageHandler: any;

    // Mock fetchEventSource to capture the onmessage handler
    vi.mocked(fetchEventSourceModule.fetchEventSource).mockImplementation(
      async (_url, options: any) => {
        onmessageHandler = options.onmessage;
        // Simulate start event
        onmessageHandler({
          event: "start",
          data: JSON.stringify({ conversation_id: CONVERSATION_ID }),
        });
      },
    );

    const { result } = renderHook(() => useChatbot());

    // Wait for streaming to be enabled
    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    // Send a message to trigger streaming
    await result.current.handleSend("test query");

    // Wait for onmessage handler to be captured
    await waitFor(() => {
      expect(onmessageHandler).toBeDefined();
    });

    // Simulate token events
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "Hello" }),
    });

    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: " world" }),
    });

    // Verify that messages have scrollToHere flag set
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.scrollToHere).toBe(true);
    });
  });

  it("should set scrollToHere flag when adding referenced documents", async () => {
    let onmessageHandler: any;

    // Mock fetchEventSource to capture the onmessage handler
    vi.mocked(fetchEventSourceModule.fetchEventSource).mockImplementation(
      async (_url, options: any) => {
        onmessageHandler = options.onmessage;
        // Simulate start event
        onmessageHandler({
          event: "start",
          data: JSON.stringify({ conversation_id: CONVERSATION_ID }),
        });
      },
    );

    const { result } = renderHook(() => useChatbot());

    // Wait for streaming to be enabled
    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    // Send a message to trigger streaming
    await result.current.handleSend("test query");

    // Wait for onmessage handler to be captured
    await waitFor(() => {
      expect(onmessageHandler).toBeDefined();
    });

    // Simulate token event first
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "Response content" }),
    });

    // Simulate end event with referenced documents
    onmessageHandler({
      event: "end",
      data: JSON.stringify({
        referenced_documents: [
          {
            doc_title: "Test Doc",
            doc_url: "https://example.com/test",
          },
        ],
      }),
    });

    // Verify that the message has scrollToHere flag set
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.scrollToHere).toBe(true);
    });
    const messages = result.current.messages;
    const lastMessage = messages[messages.length - 1];
    expect(lastMessage.referenced_documents).toHaveLength(1);
  });

  it("should set scrollToHere flag on turn_complete event", async () => {
    let onmessageHandler: any;

    // Mock fetchEventSource to capture the onmessage handler
    vi.mocked(fetchEventSourceModule.fetchEventSource).mockImplementation(
      async (_url, options: any) => {
        onmessageHandler = options.onmessage;
        // Simulate start event
        onmessageHandler({
          event: "start",
          data: JSON.stringify({ conversation_id: CONVERSATION_ID }),
        });
      },
    );

    const { result } = renderHook(() => useChatbot());

    // Wait for streaming to be enabled
    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    // Send a message to trigger streaming
    await result.current.handleSend("test query");

    // Wait for onmessage handler to be captured
    await waitFor(() => {
      expect(onmessageHandler).toBeDefined();
    });

    // Simulate token event
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "Initial response" }),
    });

    // Simulate turn_complete event
    onmessageHandler({
      event: "turn_complete",
      data: JSON.stringify({ token: "Final response" }),
    });

    // Verify that the new message has scrollToHere flag set
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.scrollToHere).toBe(true);
    });
    const messages = result.current.messages;
    const lastMessage = messages[messages.length - 1];
    expect(lastMessage.content).toBe("Final response");
  });
});

describe("useChatbot - markdown URL buffering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock fetch for health check to enable streaming
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ "streaming-chatbot-service": "ok" }),
    });
  });

  it("should handle normal text without markdown links", async () => {
    let onmessageHandler: any;

    vi.mocked(fetchEventSourceModule.fetchEventSource).mockImplementation(
      async (_url, options: any) => {
        onmessageHandler = options.onmessage;
        onmessageHandler({
          event: "start",
          data: JSON.stringify({ conversation_id: CONVERSATION_ID }),
        });
      },
    );

    const { result } = renderHook(() => useChatbot());

    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    await result.current.handleSend("test query");

    await waitFor(() => {
      expect(onmessageHandler).toBeDefined();
    });

    // Send normal text
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "This is normal text" }),
    });

    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("This is normal text");
    });
  });

  it("should buffer markdown URL when ]( is in single chunk", async () => {
    let onmessageHandler: any;

    vi.mocked(fetchEventSourceModule.fetchEventSource).mockImplementation(
      async (_url, options: any) => {
        onmessageHandler = options.onmessage;
        onmessageHandler({
          event: "start",
          data: JSON.stringify({ conversation_id: CONVERSATION_ID }),
        });
      },
    );

    const { result } = renderHook(() => useChatbot());

    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    await result.current.handleSend("test query");

    await waitFor(() => {
      expect(onmessageHandler).toBeDefined();
    });

    // Send link title
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "Check [this link](" }),
    });

    // At this point, ']' should be shown but '(' should be buffered
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("Check [this link]");
    });

    // Send URL characters (should be buffered)
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "https://example.com/very-long-url" }),
    });

    // Content should still be the same (URL buffered)
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("Check [this link]");
    });

    // Send closing parenthesis
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: ")" }),
    });

    // Now the full link should appear
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe(
        "Check [this link](https://example.com/very-long-url)",
      );
    });
  });

  it("should handle ]( split across chunks", async () => {
    let onmessageHandler: any;

    vi.mocked(fetchEventSourceModule.fetchEventSource).mockImplementation(
      async (_url, options: any) => {
        onmessageHandler = options.onmessage;
        onmessageHandler({
          event: "start",
          data: JSON.stringify({ conversation_id: CONVERSATION_ID }),
        });
      },
    );

    const { result } = renderHook(() => useChatbot());

    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    await result.current.handleSend("test query");

    await waitFor(() => {
      expect(onmessageHandler).toBeDefined();
    });

    // Send chunk ending with ']'
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "Check [link]" }),
    });

    // ']' is buffered as it might be start of ']('
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("Check [link");
    });

    // Send '(' in next chunk
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "(https://example.com" }),
    });

    // Now ']' should be shown and '(https://example.com' buffered
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("Check [link]");
    });

    // Complete the URL
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: ")" }),
    });

    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("Check [link](https://example.com)");
    });
  });

  it("should handle false alarm when ] is not followed by (", async () => {
    let onmessageHandler: any;

    vi.mocked(fetchEventSourceModule.fetchEventSource).mockImplementation(
      async (_url, options: any) => {
        onmessageHandler = options.onmessage;
        onmessageHandler({
          event: "start",
          data: JSON.stringify({ conversation_id: CONVERSATION_ID }),
        });
      },
    );

    const { result } = renderHook(() => useChatbot());

    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    await result.current.handleSend("test query");

    await waitFor(() => {
      expect(onmessageHandler).toBeDefined();
    });

    // Send chunk ending with ']'
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "Array[5]" }),
    });

    // ']' is buffered
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("Array[5");
    });

    // Next chunk doesn't start with '('
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: " is good" }),
    });

    // Both buffered ']' and new text should appear
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("Array[5] is good");
    });
  });

  it("should handle multiple markdown links in sequence", async () => {
    let onmessageHandler: any;

    vi.mocked(fetchEventSourceModule.fetchEventSource).mockImplementation(
      async (_url, options: any) => {
        onmessageHandler = options.onmessage;
        onmessageHandler({
          event: "start",
          data: JSON.stringify({ conversation_id: CONVERSATION_ID }),
        });
      },
    );

    const { result } = renderHook(() => useChatbot());

    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    await result.current.handleSend("test query");

    await waitFor(() => {
      expect(onmessageHandler).toBeDefined();
    });

    // First link
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "[link1](" }),
    });

    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("[link1]");
    });

    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "url1)" }),
    });

    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("[link1](url1)");
    });

    // Second link
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: " and [link2](" }),
    });

    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("[link1](url1) and [link2]");
    });

    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "url2)" }),
    });

    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("[link1](url1) and [link2](url2)");
    });
  });

  it("should reset buffering state on new user message", async () => {
    let onmessageHandler: any;

    vi.mocked(fetchEventSourceModule.fetchEventSource).mockImplementation(
      async (_url, options: any) => {
        onmessageHandler = options.onmessage;
        onmessageHandler({
          event: "start",
          data: JSON.stringify({ conversation_id: CONVERSATION_ID }),
        });
      },
    );

    const { result } = renderHook(() => useChatbot());

    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    // First message with incomplete link
    await result.current.handleSend("test query 1");

    await waitFor(() => {
      expect(onmessageHandler).toBeDefined();
    });

    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "[link](" }),
    });

    await waitFor(() => {
      const messages = result.current.messages;
      expect(messages.length).toBeGreaterThan(0);
    });

    // Send second message - should reset buffering state
    await result.current.handleSend("test query 2");

    // The new message handler should work normally
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "Normal text" }),
    });

    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("Normal text");
    });
  });

  it("should handle URL with query parameters and fragments", async () => {
    let onmessageHandler: any;

    vi.mocked(fetchEventSourceModule.fetchEventSource).mockImplementation(
      async (_url, options: any) => {
        onmessageHandler = options.onmessage;
        onmessageHandler({
          event: "start",
          data: JSON.stringify({ conversation_id: CONVERSATION_ID }),
        });
      },
    );

    const { result } = renderHook(() => useChatbot());

    await waitFor(() => {
      expect(result.current.isStreamingSupported()).toBe(true);
    });

    await result.current.handleSend("test query");

    await waitFor(() => {
      expect(onmessageHandler).toBeDefined();
    });

    // Start link
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: "[docs](" }),
    });

    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("[docs]");
    });

    // Send complex URL in chunks
    onmessageHandler({
      event: "token",
      data: JSON.stringify({
        token: "https://example.com/path?param=value&other=123#section",
      }),
    });

    // URL should be buffered
    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe("[docs]");
    });

    // Close the link
    onmessageHandler({
      event: "token",
      data: JSON.stringify({ token: ")" }),
    });

    await waitFor(() => {
      const messages = result.current.messages;
      const lastMessage = messages[messages.length - 1];
      expect(lastMessage.content).toBe(
        "[docs](https://example.com/path?param=value&other=123#section)",
      );
    });
  });
});
