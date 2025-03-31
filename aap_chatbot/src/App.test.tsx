// NOTE: We don't need to import React, this is just to avoid the
// following warning:
// 'React' must be in scope when using JSX
// react/react-in-jsx-scope
import React from "react";

// NOTE: ignoring because we non-use of "screen" is conistent with the
// vitest-browser-react documentation
/* eslint-disable testing-library/prefer-screen-queries */

import { beforeEach, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";
import { MemoryRouter } from "react-router-dom";
import { screen } from "@testing-library/react";
import { App } from "./App";
import { ColorThemeSwitch } from "./ColorThemeSwitch/ColorThemeSwitch";
import { userEvent, page } from "@vitest/browser/context";
import axios, { AxiosError, AxiosHeaders } from "axios";
// See: https://github.com/vitest-dev/vitest/issues/6965
import "@vitest/browser/matchers.d.ts";

const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

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
  await textArea.fill("Hello");
  await userEvent.keyboard("{Enter}");
}

const referencedDocumentExample = [
  "https://docs\\.redhat\\.com/en/documentation/red_hat_ansible_automation_platform/2\\.5/html-single/getting_started_with_playbooks/index#ref-create-variables",
];

function mockAxios(
  status: number,
  reject = false,
  timeout = false,
  refDocs: string[] = referencedDocumentExample,
) {
  const spy = vi.spyOn(axios, "post");
  if (reject) {
    if (timeout) {
      spy.mockImplementationOnce(() =>
        Promise.reject(new AxiosError("timeout of 28000ms exceeded")),
      );
    } else if (status === 429) {
      spy.mockImplementationOnce(() =>
        Promise.reject(createError("Request failed with status code 429", 429)),
      );
    } else {
      spy.mockImplementationOnce(() =>
        Promise.reject(new Error("mocked error")),
      );
    }
  } else {
    spy.mockResolvedValue({
      data: {
        conversation_id: "123e4567-e89b-12d3-a456-426614174000",
        referenced_documents: refDocs.map((d, index) => ({
          docs_url: d,
          title: "Create variables" + (index > 0 ? index : ""),
        })),
        response:
          "In Ansible, the precedence of variables is determined by the order...",
        truncated: false,
      },
      status,
    });
  }
  return spy;
}

function createError(message: string, status: number): AxiosError {
  const request = { path: "/chat" };
  const headers = new AxiosHeaders({
    "Content-Type": "application/json",
  });
  const config = {
    url: "http://localhost:8000",
    headers,
  };
  const code = "SOME_ERR";

  const error = new AxiosError(message, code, config, request);
  if (status > 0) {
    const response = {
      data: {},
      status,
      statusText: "",
      config,
      headers,
    };
    error.response = response;
  }
  return error;
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
      data: { id: 0, token: "Let me search for " },
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
      data: { id: 4, token: "EDA stands for " },
    },
    {
      event: "token",
      data: { id: 5, token: "Event Driven Ansible." },
    },
    {
      event: "step_complete",
      data: { id: 6, token: '{ "key":"value"}' },
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
    const o = JSON.parse(init.body);
    if (o.query.startsWith("status=")) {
      status = parseInt(o.query.substring(7));
    } else if (o.query.startsWith("error in stream")) {
      errorCase = true;
    } else if (o.query.startsWith("agent")) {
      agent = true;
    }
    console.log(`status ${status}`);

    const ok = status === 200;
    await init.onopen({ status, ok });
    if (status === 200) {
      const streamData = agent
        ? streamAgentNormalData
        : errorCase
          ? streamErrorData
          : streamNormalData;
      for (const data of streamData) {
        init.onmessage({ data: JSON.stringify(data) });
      }
    }
    init.onclose();
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
  const spy = mockAxios(200);
  const view = await renderApp();
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("Hello");

  await userEvent.keyboard("{Enter}");

  expect(spy).toHaveBeenCalledWith(
    expect.anything(),
    expect.objectContaining({
      conversation_id: undefined,
      query: "Hello",
    }),
    expect.anything(),
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
  expect(
    copiedString.startsWith(
      "In Ansible, the precedence of variables is determined by the order...",
    ),
  );

  await page.getByLabelText("Toggle menu").click();
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

  const footNoteLink = page.getByText(
    "Always review AI-generated content prior to use.",
  );
  await footNoteLink.click();
  await expect
    .element(page.getByText("While Lightspeed strives for accuracy,"))
    .toBeVisible();
  await page.getByText("Got it").click();
  await expect
    .element(page.getByText("While Lightspeed strives for accuracy,"))
    .not.toBeVisible();

  await textArea.fill("Tell me about Ansible.");
  await userEvent.keyboard("{Enter}");
  await expect
    .element(
      view.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .toBeVisible();
  await expect.element(view.getByText("Create variables")).toBeVisible();

  await page.getByLabelText("Toggle menu").click();

  const filterHistory = page.getByLabelText("Filter menu items");
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
  vi.stubGlobal("open", () => {
    ghIssueLinkSpy++;
  });
  mockAxios(200);
  const view = await renderApp();
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("Hello");

  await userEvent.keyboard("{Enter}");
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
  mockAxios(200, false, false, lotsOfRefDocs);
  const view = await renderApp();
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("Hello");

  await userEvent.keyboard("{Enter}");

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
  mockAxios(500);
  const view = await renderApp();
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("Hello");

  await userEvent.keyboard("{Enter}");
  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual("Bot returned status_code 500");
});

test("Chat service returns a timeout error", async () => {
  mockAxios(-1, true, true);
  await renderApp();
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("Hello");
  await userEvent.keyboard("{Enter}");

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
  mockAxios(429, true);
  await renderApp();
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("Hello");
  await userEvent.keyboard("{Enter}");

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
  mockAxios(-1, true);
  const view = await renderApp();
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("Hello");
  await userEvent.keyboard("{Enter}");

  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual(
    "An unexpected error occurred: Error: mocked error",
  );
});

test("Feedback API returns 500", async () => {
  mockAxios(200);
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

  mockAxios(500);

  const thumbsUpIcon = view.getByRole("button", {
    name: "Good response",
  });
  await thumbsUpIcon.click();
  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual("Feedback API returned status_code 500");
});

test("Feedback API returns an unexpected error", async () => {
  mockAxios(200);
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

  mockAxios(-1, true);

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
  mockAxios(200);
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

// test("Debug mode test", async () => {
//   mockAxios(200);

//   await renderApp(true);
//   await expect.element(page.getByText("granite3-1-8b")).toBeVisible();
//   await page.getByText("granite3-1-8b").click();
//   // Comment out following lines for now since granite3-1-8b is the only choice.
//   //   await expect
//   //     .element(page.getByRole("menuitem", { name: "granite3-8b" }))
//   //     .toBeVisible();
//   //   await page.getByRole("menuitem", { name: "granite3-8b" }).click();

//   await sendMessage("Hello");
//   await expect
//     .element(
//       page.getByText(
//         "In Ansible, the precedence of variables is determined by the order...",
//       ),
//     )
//     .toBeVisible();
//   await expect.element(page.getByText("Create variables")).toBeVisible();
// });

test("Test system prompt override", async () => {
  const spy = mockAxios(200);
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

  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("Hello with system prompt override");

  await userEvent.keyboard("{Enter}");
  expect(spy).toHaveBeenCalledWith(
    expect.anything(),
    expect.objectContaining({
      conversation_id: undefined,
      query: "Hello with system prompt override",
      system_prompt: "MY SYSTEM PROMPT",
    }),
    expect.anything(),
  );
});

test("Chat streaming test", async () => {
  let ghIssueLinkSpy = 0;
  vi.stubGlobal("open", () => {
    ghIssueLinkSpy++;
  });
  mockAxios(200);

  const view = await renderApp(false, true);
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("Hello");

  await userEvent.keyboard("{Enter}");

  await expect
    .element(
      view.getByText(
        "The Full Support Phase for AAP 2.4 ends on October 1, 2024.",
      ),
    )
    .toBeVisible();

  const thumbsDownIcon = await screen.findByRole("button", {
    name: "Bad response",
  });
  await thumbsDownIcon.click();

  const sureButton = await screen.findByText("Sure!");
  await expect.element(sureButton).toBeVisible();
  await sureButton.click();

  expect(ghIssueLinkSpy).toEqual(1);
});

test("Agent chat streaming test", async () => {
  let ghIssueLinkSpy = 0;
  vi.stubGlobal("open", () => {
    ghIssueLinkSpy++;
  });
  mockAxios(200);

  const view = await renderApp(false, true);
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("agent test");

  await userEvent.keyboard("{Enter}");

  await expect.element(view.getByText("Turn complete")).toBeVisible();

  const thumbsDownIcon = await screen.findByRole("button", {
    name: "Bad response",
  });
  await thumbsDownIcon.click();

  const sureButton = await screen.findByText("Sure!");
  await expect.element(sureButton).toBeVisible();
  await sureButton.click();

  expect(ghIssueLinkSpy).toEqual(1);

  await expect
    .element(view.getByText("EDA stands for Event Driven Ansible."))
    .not.toBeVisible();
  const showMoreLink = await screen.findByRole("button", { name: "Show more" });
  await showMoreLink.click();
  await expect
    .element(view.getByText("EDA stands for Event Driven Ansible."))
    .toBeVisible();
});

test("Chat streaming error at API call", async () => {
  const view = await renderApp(false, true);
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("status=400");

  await userEvent.keyboard("{Enter}");

  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual("Bot returned status_code 400");
});

test("Chat streaming error in streaming data", async () => {
  const view = await renderApp(false, true);
  const textArea = page.getByLabelText("Send a message...");
  await textArea.fill("error in stream");

  await userEvent.keyboard("{Enter}");

  const alert = view.container.querySelector(".pf-v6-c-alert__description");
  const textContent = alert?.textContent;
  expect(textContent).toEqual(
    "Bot returned an error: " +
      'response="Oops, something went wrong during LLM invocation", ' +
      "cause=\"Error code: 404 - {'detail': 'Not Found'}\"",
  );
});
