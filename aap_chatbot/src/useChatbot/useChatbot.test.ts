import { describe, it, expect } from "vitest";
import { feedbackMessage } from "./useChatbot";
import type { MessageProps } from "@patternfly/chatbot/dist/dynamic/Message";
import { Sentiment } from "../Constants";
import type { ChatFeedback } from "../types/Message";

const CONVERSATION_ID = "123e4567-e89b-12d3-a456-426614174000";

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
