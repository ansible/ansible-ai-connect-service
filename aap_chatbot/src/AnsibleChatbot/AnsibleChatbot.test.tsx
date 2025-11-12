import React from "react";
import { assert, beforeEach, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";
import { MemoryRouter } from "react-router-dom";
import { screen } from "@testing-library/react";
import { userEvent } from "@vitest/browser/context";
import axios from "axios";
import { AnsibleChatbot } from "./AnsibleChatbot";
import "@vitest/browser/matchers.d.ts";

const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

function mockAxiosGet() {
  const spyGet = vi.spyOn(axios, "get");
  spyGet.mockResolvedValue({
    data: {
      "chatbot-service": "ok",
      "streaming-chatbot-service": "disabled",
    },
    status: 200,
  });
}

function mockAxiosPost(status: number) {
  const spy = vi.spyOn(axios, "post");
  spy.mockResolvedValue({
    data: {
      conversation_id: "test-conversation-id",
      referenced_documents: [
        {
          docs_url: "https://docs.ansible.com/test",
          title: "Test Documentation",
        },
      ],
      response: "This is a test response.",
      truncated: false,
    },
    status,
  });
  return spy;
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
  mockAxiosGet();
});

test("Scroll does not trigger when feedback message is added inline", async () => {
  // Mock scrollIntoView to track calls
  const scrollIntoViewMock = vi.fn();
  Element.prototype.scrollIntoView = scrollIntoViewMock;

  const postSpy = mockAxiosPost(200);
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
  postSpy.mockResolvedValueOnce({
    data: {},
    status: 200,
  });

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

  mockAxiosPost(200);
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
