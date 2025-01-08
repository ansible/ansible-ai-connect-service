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

async function renderApp(debug = false) {
  let rootDiv = document.getElementById("root");
  rootDiv?.remove();
  let debugDiv = document.getElementById("debug");
  debugDiv?.remove();

  debugDiv = document.createElement("div");
  debugDiv.setAttribute("id", "debug");
  debugDiv.innerText = debug.toString();
  document.body.appendChild(debugDiv);
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
  "https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.5/html-single/getting_started_with_playbooks/index#ref-create-variables",
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

beforeEach(() => {
  vi.restoreAllMocks();
});

test("Basic chatbot interaction", async () => {
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
  await expect.element(view.getByText("Create variables")).toBeVisible();

  await view.getByRole("button", { name: "Clear context" }).click();
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
    "Lightspeed uses AI. Check for mistakes.",
  );
  await footNoteLink.click();
  await expect
    .element(page.getByText("While Lightspeed strives for accuracy,"))
    .toBeVisible();
  await page.getByText("Got it").click();
  await expect
    .element(view.getByText("While Lightspeed strives for accuracy,"))
    .not.toBeVisible();
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

test("Debug mode test", async () => {
  mockAxios(200);

  const view = await renderApp(true);
  await page.getByText("granite3-8b").click();
  await expect
    .element(view.getByRole("menuitem", { name: "granite3-8b" }))
    .toBeTruthy();
  await view.getByRole("menuitem", { name: "granite3-8b" }).click();

  await sendMessage("Hello");
  await expect
    .element(
      page.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    )
    .toBeVisible();
  await expect.element(page.getByText("Create variables")).toBeVisible();
});
