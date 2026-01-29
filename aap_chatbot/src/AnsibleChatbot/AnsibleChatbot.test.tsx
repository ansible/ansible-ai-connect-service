import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";
import { MemoryRouter } from "react-router-dom";
import { screen } from "@testing-library/react";
import { userEvent } from "@vitest/browser/context";
import { AnsibleChatbot } from "./AnsibleChatbot";
import "@vitest/browser/matchers.d.ts";

function mockFetchGet() {
  const originalFetch = global.fetch;
  global.fetch = vi.fn((url, options) => {
    if (
      typeof url === "string" &&
      url.includes("/api/v1/health/status/chatbot/") &&
      (!options || options.method === "GET")
    ) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          "chatbot-service": "ok",
          "streaming-chatbot-service": "disabled",
        }),
      } as Response);
    }
    return originalFetch(url, options);
  });
}

function mockFetchPost(status: number) {
  const originalFetch = global.fetch;
  global.fetch = vi.fn((url, options) => {
    // Handle GET requests for health check
    if (
      typeof url === "string" &&
      url.includes("/api/v1/health/status/chatbot/") &&
      (!options || options.method === "GET")
    ) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          "chatbot-service": "ok",
          "streaming-chatbot-service": "disabled",
        }),
      } as Response);
    }

    // Handle POST requests
    if (options?.method === "POST") {
      return Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: async () => ({
          conversation_id: "test-conversation-id",
          referenced_documents: [
            {
              docs_url: "https://docs.ansible.com/test",
              title: "Test Documentation",
            },
          ],
          response: "This is a test response.",
          truncated: false,
        }),
      } as Response);
    }

    return originalFetch(url, options);
  });
  return global.fetch;
}

async function renderChatbot() {
  let rootDiv = document.getElementById("root");
  rootDiv?.remove();

  rootDiv = document.createElement("div");
  rootDiv.setAttribute("id", "root");
  const view = render(
    <MemoryRouter>
      <AnsibleChatbot />
    </MemoryRouter>,
    {
      container: document.body.appendChild(rootDiv),
    },
  );

  return view;
}

beforeEach(() => {
  vi.restoreAllMocks();
  mockFetchGet();
});

test("Scroll does not trigger when feedback message is added inline", async () => {
  // Mock scrollIntoView to track calls
  const scrollIntoViewMock = vi.fn();
  Element.prototype.scrollIntoView = scrollIntoViewMock;

  mockFetchPost(200);
  const view = await renderChatbot();

  // Send first message
  const textArea = view.getByLabelText("Send a message...");
  await textArea.fill("First message");
  await userEvent.keyboard("{Enter}");

  // Wait for response
  await expect
    .element(view.getByText("This is a test response."))
    .toBeVisible();

  // Verify scroll was called for the first message (with scrollToHere flag)
  const scrollCallsAfterFirstMessage = scrollIntoViewMock.mock.calls.length;
  expect(scrollCallsAfterFirstMessage).toBeGreaterThan(0);

  // Mock feedback API response
  vi.mocked(global.fetch).mockResolvedValueOnce({
    ok: true,
    status: 200,
    json: async () => ({}),
  } as Response);

  // Click thumbs up on the bot response
  const thumbsUpButton = await screen.findByRole("button", {
    name: "Good response",
  });
  await thumbsUpButton.click();

  // Wait for feedback confirmation message
  await expect
    .element(view.getByText("Thank you for your feedback!"))
    .toBeVisible();

  // Verify scroll was NOT called again (feedback message should appear inline without scrolling)
  const scrollCallsAfterFeedback = scrollIntoViewMock.mock.calls.length;
  expect(scrollCallsAfterFeedback).toBe(scrollCallsAfterFirstMessage);
});

test("Scroll does trigger when new chat message is sent", async () => {
  // Mock scrollIntoView to track calls
  const scrollIntoViewMock = vi.fn();
  Element.prototype.scrollIntoView = scrollIntoViewMock;

  mockFetchPost(200);
  const view = await renderChatbot();

  // Reset mock to start counting from 0
  scrollIntoViewMock.mockClear();

  // Send a message
  const textArea = view.getByLabelText("Send a message...");
  await textArea.fill("Test message");
  await userEvent.keyboard("{Enter}");

  // Wait for response
  await expect
    .element(view.getByText("This is a test response."))
    .toBeVisible();

  // Verify scroll was called (new messages should trigger scroll)
  expect(scrollIntoViewMock.mock.calls.length).toBeGreaterThan(0);
});
