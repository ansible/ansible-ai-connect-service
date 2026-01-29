// NOTE: We don't need to import React, this is just to avoid the
// following warning:
// 'React' must be in scope when using JSX
// react/react-in-jsx-scope
import React from "react";

// NOTE: ignoring because we non-use of "screen" is conistent with the
// vitest-browser-react documentation
/* eslint-disable testing-library/prefer-screen-queries */
/* eslint-disable no-nested-ternary */
import { assert, beforeEach, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";
import { MemoryRouter } from "react-router-dom";
import { screen } from "@testing-library/react";
import { App } from "./App";
import { ColorThemeSwitch } from "./ColorThemeSwitch/ColorThemeSwitch";
import { userEvent, page } from "@vitest/browser/context";
// See: https://github.com/vitest-dev/vitest/issues/6965
import "@vitest/browser/matchers.d.ts";
import { conversationStore } from "./AnsibleChatbot/AnsibleChatbot";

const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

// Declare the custom matcher type
declare module "vitest" {
  interface AsymmetricMatchersContaining {
    objectStringContaining(expected: Record<string, any>): any;
  }
}

expect.extend({
  objectStringContaining(received, expected) {
    const obj = JSON.parse(received);
    let pass = true;
    let message = () => `${received} contains ${expected}`;
    Object.entries(expected).forEach(([k, v]) => {
      if (obj[k] !== v) {
        pass = false;
        message = () => `${received} does not contain ${expected}`;
      }
    });
    return { pass, message };
  },
});

async function renderApp(debug = false, stream = false) {
  let rootDiv = document.getElementById("root");
  rootDiv?.remove();

  let debugDiv = document.getElementById("debug");
  debugDiv?.remove();
  debugDiv = document.createElement("div");
  debugDiv.setAttribute("id", "debug");
  debugDiv.innerText = debug.toString();
  document.body.appendChild(debugDiv);

  let streamDiv = document.getElementById("stream");
  streamDiv?.remove();
  streamDiv = document.createElement("div");
  streamDiv.setAttribute("id", "stream");
  streamDiv.innerText = stream.toString();
  document.body.appendChild(streamDiv);

  rootDiv = document.createElement("div");
  rootDiv.setAttribute("id", "root");
  const view = render(
    <MemoryRouter>
      <div className="pf-v6-l-flex pf-m-column pf-m-gap-lg ws-full-page-utils pf-v6-m-dir-ltr ">
        <ColorThemeSwitch />
      </div>
      <App />
    </MemoryRouter>,
    {
      container: document.body.appendChild(rootDiv),
    },
  );

  return view;
}

async function sendMessage(message: string) {
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill(message);
  await textArea.click();
  await userEvent.keyboard("{Enter}");
}

const referencedDocumentExample = [
  "https://docs\\.redhat\\.com/en/documentation/red_hat_ansible_automation_platform/2\\.5/html-single/getting_started_with_playbooks/index#ref-create-variables",
];

function mockFetch(
  status: number,
  reject = false,
  timeout = false,
  refDocs: string[] = referencedDocumentExample,
  stream = false,
  get_reject = false,
) {
  const originalFetch = global.fetch;

  global.fetch = vi.fn((url, options) => {
    // Handle GET requests for health check
    if (
      typeof url === "string" &&
      url.includes("/api/lightspeed/v1/health/status/chatbot/") &&
      (!options || options.method === "GET")
    ) {
      if (get_reject) {
        return Promise.reject(new Error("mocked error"));
      }
      if (stream) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            "chatbot-service": "ok",
            "streaming-chatbot-service": "ok",
          }),
        } as Response);
      } else {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            status: "ok",
            dependencies: [
              {
                name: "chatbot-service",
                status: { provider: "http", models: "ok" },
                time_taken: 709.4,
              },
              {
                name: "streaming-chatbot-service",
                status: "disabled",
                time_taken: 0.002,
              },
            ],
          }),
        } as Response);
      }
    }

    // Handle POST requests for chat and feedback
    if (options?.method === "POST") {
      if (reject) {
        if (timeout) {
          const error = new Error("timeout of 28000ms exceeded");
          error.name = "AbortError";
          return Promise.reject(error);
        } else if (status === 429) {
          const response = new Response(null, { status: 429 });
          return Promise.reject(response);
        } else {
          return Promise.reject(new Error("mocked error"));
        }
      } else {
        return Promise.resolve({
          ok: status >= 200 && status < 300,
          status,
          json: async () => ({
            conversation_id: "123e4567-e89b-12d3-a456-426614174000",
            referenced_documents: refDocs.map((d, index) => ({
              docs_url: d,
              title: "Create variables" + (index > 0 ? index : ""),
            })),
            response:
              "In Ansible, the precedence of variables is determined by the order...",
            truncated: false,
          }),
        } as Response);
      }
    }

    return originalFetch(url, options);
  });

  return global.fetch;
}

function mockFetchEventSource() {
  const streamNormalData: object[] = [
    {
      event: "start",
      data: { conversation_id: "1ec5ba5b-c12d-465b-a722-0b95fee55e8c" },
    },
    { event: "token", data: { id: 0, token: "" } },
    { event: "token", data: { id: 1, token: "The" } },
    { event: "token", data: { id: 2, token: " Full" } },
    { event: "token", data: { id: 3, token: " Support" } },
    { event: "token", data: { id: 4, token: " Phase" } },
    { event: "token", data: { id: 5, token: " for" } },
    { event: "token", data: { id: 6, token: " A" } },
    { event: "token", data: { id: 7, token: "AP" } },
    { event: "token", data: { id: 8, token: " " } },
    { event: "token", data: { id: 9, token: "2" } },
    { event: "token", data: { id: 10, token: "." } },
    { event: "token", data: { id: 11, token: "4" } },
    { event: "token", data: { id: 12, token: " ends" } },
    { event: "token", data: { id: 13, token: " on" } },
    { event: "token", data: { id: 14, token: " October" } },
    { event: "token", data: { id: 15, token: " " } },
    { event: "token", data: { id: 16, token: "1" } },
    { event: "token", data: { id: 17, token: "," } },
    { event: "token", data: { id: 18, token: " " } },
    { event: "token", data: { id: 19, token: "2" } },
    { event: "token", data: { id: 20, token: "0" } },
    { event: "token", data: { id: 21, token: "2" } },
    { event: "token", data: { id: 22, token: "4" } },
    { event: "token", data: { id: 23, token: "." } },
    { event: "token", data: { id: 24, token: "" } },
    {
      event: "end",
      data: {
        referenced_documents: [
          {
            doc_title: "AAP Lifecycle Dates",
            doc_url:
              "https://github.com/ansible/aap-rag-content/blob/main/additional_docs/additional_content.txt",
          },
          {
            doc_title: "Ansible Components Versions",
            doc_url:
              "https://github.com/ansible/aap-rag-content/blob/main/additional_docs/components_versions.txt",
          },
        ],
        truncated: false,
        input_tokens: 819,
        output_tokens: 20,
      },
    },
  ];

  const streamErrorData: object[] = [
    {
      event: "start",
      data: { conversation_id: "6e33a46e-2b15-4128-8e5c-c6f637ebfbb3" },
    },
    {
      event: "error",
      data: {
        response: "Oops, something went wrong during LLM invocation",
        cause: "Error code: 404 - {'detail': 'Not Found'}",
      },
    },
  ];

  const streamAgentNormalData: object[] = [
    {
      event: "start",
      data: { conversation_id: "6e33a46e-2b15-4128-8e5c-c6f637ebfbb4" },
    },
    {
      event: "token",
      data: { id: 0, token: "\n\n`inference>`Let me search for " },
    },
    {
      event: "token",
      data: { id: 1, token: "information about EDA." },
    },
    {
      event: "tool_call",
      data: { id: 2, token: '{ "key":"value"}' },
    },
    {
      event: "step_details",
      data: { id: 3, token: '{ "key":"value"}' },
    },
    {
      event: "token",
      data: { id: 5, token: "Some output" },
    },
    {
      event: "token",
      data: { id: 6, token: "\n\n`inference>`EDA stands for " },
    },
    {
      event: "token",
      data: { id: 7, token: "Event Driven Ansible." },
    },
    {
      event: "step_complete",
      data: { id: 8, token: '{ "key":"value"}' },
    },
    {
      event: "turn_complete",
      data: { id: 0, token: "Turn complete." },
    },
  ];

  const streamAgentGreetingData: object[] = [
    {
      event: "start",
      data: { conversation_id: "6e33a46e-2b15-4128-8e5c-c6f637ebfbb4" },
    },
    {
      event: "token",
      data: {
        id: 0,
        token:
          "\n\n`inference>` Hello! How can I assist you with Ansible today?",
      },
    },
    {
      event: "turn_complete",
      data: { id: 0, token: "Turn complete." },
    },
  ];

  return vi.fn(async (_, init) => {
    let status = 200;
    let errorCase = false;
    let agent = false;
    let agent_greeting = false;
    let skipClose = false;
    const o = JSON.parse(init.body);
    if (o.query.startsWith("status=")) {
      status = parseInt(o.query.substring(7));
    } else if (o.query.startsWith("error in stream")) {
      errorCase = true;
    } else if (o.query.startsWith("agent_greeting")) {
      agent_greeting = true;
    } else if (o.query.startsWith("agent")) {
      agent = true;
    } else if (o.query.startsWith("skip close")) {
      skipClose = true;
    }
    console.log(`status ${status}`);

    const ok = status === 200;
    await init.onopen({ status, ok });
    if (status === 200) {
      const streamData = agent_greeting
        ? streamAgentGreetingData
        : agent
          ? streamAgentNormalData
          : errorCase
            ? streamErrorData
            : streamNormalData;
      for (const data of streamData) {
        init.onmessage({ data: JSON.stringify(data) });
      }
    }
    if (!skipClose) {
      init.onclose();
    }
  });
}

let copiedString = "";
function mockSetClipboard() {
  return vi.fn((s: string) => {
    copiedString = s;
    console.log(`mockedSetClipboard:${s}`);
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.mock("@microsoft/fetch-event-source", () => ({
    fetchEventSource: mockFetchEventSource(),
  }));
  vi.mock("./Clipboard", () => ({
    setClipboard: mockSetClipboard(),
  }));
});

test("Basic chatbot interaction", async () => {
  const spy = mockFetch(200);
  const view = await renderApp();

  await sendMessage("Hello");
  expect(spy).toHaveBeenCalledWith(
    expect.anything(),
    expect.objectContaining({
      body: expect.objectStringContaining({
        query: "Hello",
      }),
    }),
  );

  await expect
    .element(
      view.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .toBeVisible();
  await expect.element(view.getByText("Create variables")).toBeVisible();

  const copyIcon = await screen.findByRole("button", {
    name: "Copy",
  });
  await copyIcon.click();
  assert(
    copiedString.startsWith(
      "In Ansible, the precedence of variables is determined by the order...",
    ),
  );
  assert(copiedString.includes("Refer to the following for more information:"));
  assert(copiedString.includes("Create variables"));
  assert(copiedString.includes("https://"));

  await page.getByLabelText("Chat history menu").click();
  const newChatButton = page
    .getByText("New chat")
    .element() as HTMLButtonElement;
  await expect(newChatButton).toBeVisible();
  await newChatButton.click();

  await expect
    .element(
      page.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .not.toBeInTheDocument();
  await expect
    .element(view.getByText("Create variables"))
    .not.toBeInTheDocument();

  await sendMessage("Tell me about Ansible.");
  await expect
    .element(
      view.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .toBeVisible();
  await expect.element(view.getByText("Create variables")).toBeVisible();

  const newChatIcon = page.getByTestId("header-new-chat-button");
  await newChatIcon.click();

  await expect
    .element(
      page.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .not.toBeInTheDocument();
  await expect
    .element(view.getByText("Create variables"))
    .not.toBeInTheDocument();

  await sendMessage("Tell me about Ansible.");
  await expect
    .element(
      view.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .toBeVisible();
  await expect.element(view.getByText("Create variables")).toBeVisible();

  await page.getByLabelText("Chat history menu").click();

  const filterHistory = page.getByLabelText("Search previous conversations");
  await expect.element(filterHistory).toBeVisible();

  await filterHistory.fill("Some non-existent string");
  await expect
    .element(page.getByRole("menuitem", { name: "No results found" }))
    .toBeVisible();

  await filterHistory.fill("the precedence of variables");
  await expect
    .element(page.getByRole("menuitem", { name: "Hello" }))
    .toBeVisible();
});

test("ThumbsDown icon test", async () => {
  let ghIssueLinkSpy = 0;
  let ghIssueUrl = "";
  vi.stubGlobal("open", (url: string) => {
    ghIssueUrl = url;
    ghIssueLinkSpy++;
  });
  mockFetch(200);
  const view = await renderApp();

  await sendMessage("Hello");
  await expect
    .element(
      view.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .toBeVisible();

  await expect.element(page.getByText("Create variables")).toBeVisible();

  const thumbsDownIcon = await screen.findByRole("button", {
    name: "Bad response",
  });
  await thumbsDownIcon.click();

  const sureButton = await screen.findByText("Sure!");
  await expect.element(sureButton).toBeVisible();
  await sureButton.click();

  expect(ghIssueLinkSpy).toEqual(1);
  expect(ghIssueUrl).toContain(
    "conversation_id=123e4567-e89b-12d3-a456-426614174000",
  );
});

const REF_DOCUMENT_EXAMPLE_REGEXP = new RegExp(
  encodeURIComponent(referencedDocumentExample[0]),
  "g",
);
test("Too many reference documents for the GU issue creation query param.", async () => {
  const ahrefToAdd = 35;
  let ghIssueLinkSpy = 0;
  let ghIssueUrl = "";
  vi.stubGlobal("open", (url: string) => {
    ghIssueUrl = url;
    ghIssueLinkSpy++;
  });
  // Initialize 35 reference documents for this test case, in order to verify that the url
  // will not contain more than the max allowed documents (30).
  const lotsOfRefDocs = [];
  for (let i = 0; i < ahrefToAdd; i++) {
    lotsOfRefDocs.push(referencedDocumentExample[0]);
  }
  mockFetch(200, false, false, lotsOfRefDocs);
  const view = await renderApp();

  await sendMessage("Hello");
  await expect
    .element(
      page.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .toBeVisible();
  await expect(
    await page.getByText("Create variables").elements().length,
  ).toEqual(ahrefToAdd);

  await view
    .getByRole("button", {
      name: "Bad response",
    })
    .click();

  const sureButton = page.getByText("sure!");
  await expect.element(sureButton).toBeVisible();
  await sureButton.click();

  expect(ghIssueLinkSpy).toEqual(1);
  //   // Assert the size of the resulting documents in the query parameter is 30,
  //   // as the max defined, instead of the 35 being present.
  //   const url: string | undefined = ghIssueLinkSpy.mock.calls[0][0]?.toString();
  expect((ghIssueUrl?.match(REF_DOCUMENT_EXAMPLE_REGEXP) || []).length).toEqual(
    30,
  );
});

test("Chat service returns 500", async () => {
  mockFetch(500);
  const view = await renderApp();

  await sendMessage("Hello");
  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual("Bot returned status_code 500");
});

test("Chat service returns a timeout error", async () => {
  mockFetch(-1, true, true);
  await renderApp();

  await sendMessage("Hello");
  await expect
    .element(
      page.getByText(
        "Chatbot service is taking too long to respond to your query. ",
        { exact: false },
      ),
      { timeout: 15000 },
    )
    .toBeVisible();
});

test("Chat service returns 429 Too Many Requests error", async () => {
  mockFetch(429, true);
  await renderApp();

  await sendMessage("Hello");

  // Insert an artificial 3s delay, which is inserted in useChatbot.ts.
  await delay(3000);

  await expect
    .element(
      page.getByText("Chatbot service is busy with too many requests. ", {
        exact: false,
      }),
      { timeout: 15000 },
    )
    .toBeVisible();
});

test("Chat service returns an unexpected error", async () => {
  mockFetch(-1, true);
  const view = await renderApp();

  await sendMessage("Hello");
  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual(
    "An unexpected error occurred: Error: mocked error",
  );
});

test("Feedback API returns 500", async () => {
  mockFetch(200);
  const view = await renderApp();
  await sendMessage("Hello");
  await expect
    .element(
      page.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .toBeVisible();
  await expect.element(page.getByText("Create variables")).toBeVisible();

  mockFetch(500);

  const thumbsUpIcon = view.getByRole("button", {
    name: "Good response",
  });
  await thumbsUpIcon.click();
  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual("Feedback API returned status_code 500");
});

test("Feedback API returns an unexpected error", async () => {
  mockFetch(200);
  const view = await renderApp();
  await sendMessage("Hello");
  await expect
    .element(
      page.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .toBeVisible();
  await expect.element(page.getByText("Create variables")).toBeVisible();

  mockFetch(-1, true);

  const thumbsUpIcon = view.getByRole("button", {
    name: "Good response",
  });
  await thumbsUpIcon.click();
  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual(
    "An unexpected error occurred: Error: mocked error",
  );
});

test("Color theme switch", async () => {
  mockFetch(200);
  const view = await renderApp();
  const colorThemeSwitch: HTMLInputElement | null =
    view.container.querySelector("#color-theme-switch");
  expect(ColorThemeSwitch).not.toBeNull();
  if (colorThemeSwitch) {
    expect(colorThemeSwitch.checked).toBeFalsy();

    const htmlElementClassList =
      document.getElementsByTagName("html")[0].classList;
    expect(htmlElementClassList.length).equals(0);

    await colorThemeSwitch.click();
    expect(colorThemeSwitch.checked).toBeTruthy();

    expect(htmlElementClassList.length).equals(1);
    expect(htmlElementClassList[0]).equals("pf-v6-theme-dark");
  }
});

test("Test system prompt override", async () => {
  const spy = mockFetch(200);
  await renderApp(true);

  await expect.element(page.getByLabelText("SystemPrompt")).toBeVisible();
  const systemPromptIcon = page.getByLabelText("SystemPrompt");
  await systemPromptIcon.click();

  const systemPromptTextArea = page.getByLabelText(
    "system-prompt-form-text-area",
  );
  await systemPromptTextArea.fill("MY SYSTEM PROMPT");
  const systemPromptButton = page.getByLabelText("system-prompt-form-button");
  await systemPromptButton.click();

  await sendMessage("Hello with system prompt override");
  expect(spy).toHaveBeenCalledWith(
    expect.anything(),
    expect.objectContaining({
      body: expect.objectStringContaining({
        conversation_id: undefined,
        query: "Hello with system prompt override",
        system_prompt: "MY SYSTEM PROMPT",
      }),
    }),
  );
});

test("Test system prompt override with no_tools option", async () => {
  const spy = mockFetch(200);
  await renderApp(true);

  await expect.element(page.getByLabelText("SystemPrompt")).toBeVisible();
  const systemPromptIcon = page.getByLabelText("SystemPrompt");
  await systemPromptIcon.click();

  const systemPromptTextArea = page.getByLabelText(
    "system-prompt-form-text-area",
  );
  await systemPromptTextArea.fill("MY SYSTEM PROMPT WITH NO_TOOLS OPTION");

  const bypassToolsCheckbox = page.getByRole("checkbox");
  expect(bypassToolsCheckbox).not.toBeChecked();
  await bypassToolsCheckbox.click();
  expect(bypassToolsCheckbox).toBeChecked();

  const systemPromptButton = page.getByLabelText("system-prompt-form-button");
  await systemPromptButton.click();

  await sendMessage("Hello with system prompt override with no_tools option");
  expect(spy).toHaveBeenCalledWith(
    expect.anything(),
    expect.objectContaining({
      body: expect.objectStringContaining({
        conversation_id: undefined,
        no_tools: true,
        query: "Hello with system prompt override with no_tools option",
        system_prompt: "MY SYSTEM PROMPT WITH NO_TOOLS OPTION",
      }),
    }),
  );
});

test("Chat streaming test", async () => {
  let ghIssueLinkSpy = 0;
  let ghIssueUrl = "";
  vi.stubGlobal("open", (url: string) => {
    ghIssueUrl = url;
    ghIssueLinkSpy++;
  });
  mockFetch(200, false, false, referencedDocumentExample, true);
  const view = await renderApp(false, true);

  await sendMessage("Hello");
  await expect
    .element(
      view.getByText(
        "The Full Support Phase for AAP 2.4 ends on October 1, 2024.",
      ),
    )
    .toBeVisible();

  const copyIcon = await screen.findByRole("button", {
    name: "Copy",
  });

  // Make sure the copy button does not contain the "action-button-hidden" CSS class.
  assert(!copyIcon.getAttribute("class")?.includes("action-button-hidden"));

  await copyIcon.click();
  assert(copiedString.startsWith("The Full Support Phase for AAP 2.4"));
  assert(copiedString.includes("Refer to the following for more information:"));
  assert(copiedString.includes("Ansible Components Versions"));
  assert(copiedString.includes("https://"));

  const thumbsDownIcon = await screen.findByRole("button", {
    name: "Bad response",
  });
  await thumbsDownIcon.click();

  const sureButton = await screen.findByText("Sure!");
  await expect.element(sureButton).toBeVisible();
  await sureButton.click();

  expect(ghIssueLinkSpy).toEqual(1);
  expect(ghIssueUrl).toContain(
    "conversation_id=1ec5ba5b-c12d-465b-a722-0b95fee55e8c",
  );
});

test("Chat streaming test when streaming is not closed.", async () => {
  let ghIssueLinkSpy = 0;
  let ghIssueUrl = "";
  vi.stubGlobal("open", (url: string) => {
    ghIssueUrl = url;
    ghIssueLinkSpy++;
  });
  mockFetch(200, false, false, referencedDocumentExample, true);
  const view = await renderApp(false, true);

  await sendMessage("skip close");
  await expect
    .element(
      view.getByText(
        "The Full Support Phase for AAP 2.4 ends on October 1, 2024.",
      ),
    )
    .toBeVisible();

  const copyIcon = await screen.findByRole("button", {
    name: "Copy",
  });

  // Make sure the copy button contains the "action-button-hidden" CSS class.
  assert(copyIcon.getAttribute("class")?.includes("action-button-hidden"));
});

test("Agent chat streaming test", async () => {
  let ghIssueLinkSpy = 0;
  vi.stubGlobal("open", () => {
    ghIssueLinkSpy++;
  });
  mockFetch(200, false, false, referencedDocumentExample, true);

  const view = await renderApp(false, true);

  await sendMessage("agent test");

  await expect.element(view.getByText("Turn complete")).toBeVisible();

  const thumbsDownIcon = await screen.findByRole("button", {
    name: "Bad response",
  });
  await thumbsDownIcon.click();

  const sureButton = await screen.findByText("Sure!");
  await expect.element(sureButton).toBeVisible();
  await sureButton.click();

  expect(ghIssueLinkSpy).toEqual(1);

  await expect.element(view.getByText("Some output")).not.toBeVisible();
  const showMoreLink = await screen.findByRole("button", { name: "Show more" });
  await showMoreLink.click();
  await expect.element(view.getByText("Show less")).toBeVisible();
  await expect.element(view.getByText("Some output")).toBeVisible();
  await expect.element(view.getByText("EDA stands for Event Driven Ansible."))
    .not.exist;
});

test("Agent chat streaming test with a general greeting", async () => {
  let ghIssueLinkSpy = 0;
  vi.stubGlobal("open", () => {
    ghIssueLinkSpy++;
  });
  mockFetch(200, false, false, referencedDocumentExample, true);

  const view = await renderApp(false, true);

  await sendMessage("agent_greeting test");

  await expect
    .element(view.getByText("Hello! How can I assist you with Ansible today?"))
    .toBeVisible();
  await expect.element(view.getByText("Show more")).not.exist;
});

test("Chat streaming error at API call", async () => {
  mockFetch(200, false, false, referencedDocumentExample, true);
  const view = await renderApp(false, true);

  await sendMessage("status=400");
  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual("Bot returned status_code 400");
});

test("Chat streaming error in streaming data", async () => {
  mockFetch(200, false, false, referencedDocumentExample, true);
  const view = await renderApp(false, true);

  await sendMessage("error in stream");
  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual(
    "Bot returned an error: " +
      'response="Oops, something went wrong during LLM invocation", ' +
      "cause=\"Error code: 404 - {'detail': 'Not Found'}\"",
  );
});

test("Chat streaming error in status check", async () => {
  mockFetch(200, false, false, referencedDocumentExample, true, true);

  const view = await renderApp(false, true);
  await delay(100);

  // Make sure the error popup is NOT displayed in this error case.
  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).not.contain("mocked error");
});

test("Chat service returns 429 Too Many Requests error in streaming", async () => {
  mockFetch(200, false, false, referencedDocumentExample, true);
  const view = await renderApp(false, true);

  await sendMessage("status=429");

  // Insert an artificial 3s delay, which is inserted in useChatbot.ts.
  await delay(3000);

  await expect
    .element(
      page.getByText("Chatbot service is busy with too many requests. ", {
        exact: false,
      }),
      { timeout: 15000 },
    )
    .toBeVisible();
});

test("Test reset conversation state once unmounting the component.", async () => {
  const view = await renderApp();
  conversationStore.set("1", []);
  view.unmount();
  assert(conversationStore.size === 0);
});
