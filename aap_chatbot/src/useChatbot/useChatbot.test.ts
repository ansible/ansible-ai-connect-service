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
