import { vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";
import { ColorThemeSwitch } from "./ColorThemeSwitch/ColorThemeSwitch";
import userEvent from "@testing-library/user-event";
import axios from "axios";

describe("App tests", () => {
  const renderApp = () => {
    return render(
      <MemoryRouter>
        <div className="pf-v6-l-flex pf-m-column pf-m-gap-lg ws-full-page-utils pf-v6-m-dir-ltr ">
          <ColorThemeSwitch />
        </div>
        <App />
      </MemoryRouter>,
    );
  };
  const mockAxios = (status: number, reject = false) => {
    const spy = vi.spyOn(axios, "post");
    if (reject) {
      spy.mockImplementationOnce(() => {
        return Promise.reject(new Error("mocked error"));
      });
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
  });

  it("App renders", () => {
    renderApp();
    expect(screen.getByText("Hello, Ansible User")).toBeInTheDocument();
  });

  it("Basic chatbot interaction", async () => {
    mockAxios(200);
    renderApp();
    const textArea = await screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = await screen.getByLabelText("Send Button");
    await act(async () => fireEvent.click(sendButton));
    expect(
      screen.getByText(
        "In Ansible, the precedence of variables is determined by the order...",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Create variables")).toBeInTheDocument();
  });

  it("Chat service returns 500", async () => {
    mockAxios(500);
    const app = renderApp();
    const textArea = await screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = await screen.getByLabelText("Send Button");
    await act(async () => fireEvent.click(sendButton));
    const alert = app.container.querySelector(".pf-v6-c-alert__description");
    const textContent = alert?.textContent;
    expect(textContent).toEqual("Bot returned status_code 500");
  });

  it("Chat service returns an unexpected error", async () => {
    mockAxios(-1, true);
    const app = renderApp();
    const textArea = await screen.getByLabelText("Send a message...");
    await act(async () => userEvent.type(textArea, "Hello"));
    const sendButton = await screen.getByLabelText("Send Button");
    await act(async () => fireEvent.click(sendButton));
    const alert = app.container.querySelector(".pf-v6-c-alert__description");
    const textContent = alert?.textContent;
    expect(textContent).toEqual(
      "An unexpected error occured: Error: mocked error",
    );
  });

  it("Color theme switch", async () => {
    mockAxios(200);
    const app = renderApp();
    const colorThemeSwitch: any = app.container.querySelector(
      "#color-theme-switch",
    );
    expect(colorThemeSwitch).toBeTruthy();
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
  });
});
