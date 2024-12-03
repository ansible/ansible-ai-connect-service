import React from "react";
import { vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";
import { ColorThemeSwitch } from "./ColorThemeSwitch/ColorThemeSwitch";
import userEvent from "@testing-library/user-event";
import axios, { AxiosError, AxiosHeaders } from "axios";

describe("App tests", () => {
  const renderApp = (debug = false) => {
    const debugDiv = document.createElement("div");
    debugDiv.setAttribute("id", "debug");
    debugDiv.innerText = debug.toString();
    document.body.appendChild(debugDiv);
    const rootDiv = document.createElement("div");
    rootDiv.setAttribute("id", "root");
    return render(
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
  };

  const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

  const createError = (message: string, status: number): AxiosError => {
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
  };

  const mockAxios = (status: number, reject = false, timeout = false) => {
    const spy = vi.spyOn(axios, "post");
    if (reject) {
      if (timeout) {
        spy.mockImplementationOnce(() =>
          Promise.reject(new AxiosError("timeout of 28000ms exceeded")),
        );
      } else if (status === 429) {
        spy.mockImplementationOnce(() =>
          Promise.reject(
            createError("Request failed with status code 429", 429),
          ),
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
          referenced_documents: [
            {
              docs_url:
                "https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.5/html-single/" +
                "getting_started_with_playbooks/index#ref-create-variables",
              title: "Create variables",
            },
          ],
          response:
            "In Ansible, the precedence of variables is determined by the order...",
          truncated: false,
        },
        status,
      });
    }
  };

  afterEach(() => {
    vi.restoreAllMocks();
    const rootDiv = document.getElementById("root");
    rootDiv?.remove();
    const debugDiv = document.getElementById("debug");
    debugDiv?.remove();
  });

  it("App renders", () => {
    renderApp();
    expect(screen.getByText("Hello, Ansible User")).toBeInTheDocument();
    const attachButton = screen.queryByLabelText("Attach button");
    expect(attachButton).toBeNull();
  });

  it("Basic chatbot interaction", async () => {
    mockAxios(200);
    renderApp();
    const textArea = screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = screen.getByLabelText("Send button");
    await act(async () => fireEvent.click(sendButton));
    expect(
      screen.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Create variables")).toBeInTheDocument();

    const thumbsUpIcon = screen.getByRole("button", { name: "Good response" });
    await act(async () => fireEvent.click(thumbsUpIcon));

    const thumbsDownIcon = screen.getByRole("button", { name: "Bad response" });
    await act(async () => fireEvent.click(thumbsDownIcon));

    const clearContextButton = screen.getByLabelText("Clear context");
    await act(async () => fireEvent.click(clearContextButton));
    expect(
      screen.queryByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    ).toBeNull();
    expect(screen.queryByText("Create variables")).toBeNull();

    const footNoteLink = screen.getByText(
      "Lightspeed uses AI. Check for mistakes.",
    );
    await act(async () => fireEvent.click(footNoteLink));
    expect(
      screen.getByText("While Lightspeed strives for accuracy,", {
        exact: false,
      }),
    ).toBeVisible();
    const gotItButton = screen.getByText("Got it");
    await act(async () => fireEvent.click(gotItButton));
    expect(
      screen.queryByText("While Lightspeed strives for accuracy,", {
        exact: false,
      }),
    ).not.toBeVisible();
  });

  it("ThumbsDown icon test", async () => {
    mockAxios(200);
    renderApp();
    const textArea = screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = screen.getByLabelText("Send button");
    await act(async () => fireEvent.click(sendButton));
    expect(
      screen.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Create variables")).toBeInTheDocument();

    const thumbsDownIcon = screen.getByRole("button", { name: "Bad response" });
    await act(async () => fireEvent.click(thumbsDownIcon));

    const sureButton = screen.getByText("Sure!");
    await act(async () => fireEvent.click(sureButton));
  });

  it("Chat service returns 500", async () => {
    mockAxios(500);
    const view = renderApp();
    const textArea = screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = screen.getByLabelText("Send button");
    await act(async () => fireEvent.click(sendButton));
    const alert = view.container.querySelector(".pf-v6-c-alert__description");
    const textContent = alert?.textContent;
    expect(textContent).toEqual("Bot returned status_code 500");
  });

  it("Chat service returns a timeout error", async () => {
    mockAxios(-1, true, true);
    renderApp();
    const textArea = screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = screen.getByLabelText("Send button");
    await act(async () => fireEvent.click(sendButton));
    expect(
      screen.getByText(
        "Chatbot service is taking too long to respond to your query. ",
        { exact: false },
      ),
    ).toBeInTheDocument();
  });

  it("Chat service returns 429 Too Many Requests error", async () => {
    mockAxios(429, true);
    renderApp();
    const textArea = screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = screen.getByLabelText("Send button");
    await act(async () => fireEvent.click(sendButton));
    await delay(3100);
    expect(
      screen.getByText("Chatbot service is busy with too many requests. ", {
        exact: false,
      }),
    ).toBeInTheDocument();
  });

  it("Chat service returns an unexpected error", async () => {
    mockAxios(-1, true);
    const view = renderApp();
    const textArea = screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = screen.getByLabelText("Send button");
    await act(async () => fireEvent.click(sendButton));
    const alert = view.container.querySelector(".pf-v6-c-alert__description");
    const textContent = alert?.textContent;
    expect(textContent).toEqual(
      "An unexpected error occured: Error: mocked error",
    );
  });

  it("Feedback API returns 500", async () => {
    mockAxios(200);
    const view = renderApp();
    const textArea = screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = screen.getByLabelText("Send button");
    await act(async () => fireEvent.click(sendButton));
    expect(
      screen.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Create variables")).toBeInTheDocument();

    vi.restoreAllMocks();
    mockAxios(500);

    const thumbsUpIcon = screen.getByRole("button", { name: "Good response" });
    await act(async () => fireEvent.click(thumbsUpIcon));
    const alert = view.container.querySelector(".pf-v6-c-alert__description");
    const textContent = alert?.textContent;
    expect(textContent).toEqual("Feedback API returned status_code 500");
  });

  it("Feedback API returns an unexpected error", async () => {
    mockAxios(200);
    const view = renderApp();
    const textArea = screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = screen.getByLabelText("Send button");
    await act(async () => fireEvent.click(sendButton));
    expect(
      screen.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Create variables")).toBeInTheDocument();

    vi.restoreAllMocks();
    mockAxios(-1, true);

    const thumbsUpIcon = screen.getByRole("button", { name: "Good response" });
    await act(async () => fireEvent.click(thumbsUpIcon));
    const alert = view.container.querySelector(".pf-v6-c-alert__description");
    const textContent = alert?.textContent;
    expect(textContent).toEqual(
      "An unexpected error occured: Error: mocked error",
    );
  });

  it("Color theme switch", async () => {
    mockAxios(200);
    const view = renderApp();
    const colorThemeSwitch: HTMLInputElement | null =
      view.container.querySelector("#color-theme-switch");
    expect(ColorThemeSwitch).not.toBeNull();
    if (colorThemeSwitch) {
      expect(colorThemeSwitch.checked).toBeFalsy();

      // "getComputedStyle" does not seem to work...
      //
      // const showLight = app.container.querySelector(".show-light");
      // const showDark = app.container.querySelector(".show-dark");
      // expect(getComputedStyle(showLight!).display).toEqual("block")
      // expect(getComputedStyle(showDark!).display).toEqual("none")

      await act(async () => fireEvent.click(colorThemeSwitch));
      expect(colorThemeSwitch.checked).toBeTruthy();

      // expect(getComputedStyle(showLight!).display).toEqual("none")
      // expect(getComputedStyle(showDark!).display).toEqual("block")
    }
  });

  it("Debug mode test", async () => {
    mockAxios(200);

    renderApp(true);

    const textArea = screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = screen.getByLabelText("Send button");
    await act(async () => fireEvent.click(sendButton));
    expect(
      screen.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Create variables")).toBeInTheDocument();
  });
});
