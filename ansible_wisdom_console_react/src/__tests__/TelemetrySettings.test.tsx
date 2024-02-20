import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { TelemetrySettings } from "../TelemetrySettings";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { API_TELEMETRY_PATH } from "../api/api";

jest.mock("axios", () => ({
  get: jest.fn(),
  post: jest.fn(),
}));

describe("TelemetrySettings", () => {
  beforeEach(() => jest.resetAllMocks());

  it("Loading", async () => {
    (axios.get as jest.Mock).mockResolvedValue({ optOut: "false" });
    render(
      <TelemetrySettings adminDashboardUrl={"http://admin_dashboard-url/"} />,
    );
    expect(axios.get as jest.Mock).toBeCalledWith(API_TELEMETRY_PATH);
    expect(
      await screen.findByTestId("telemetry-settings__telemetry-loading"),
    ).toBeInTheDocument();
  });

  it("Loaded::Found", async () => {
    (axios.get as jest.Mock).mockResolvedValue({ data: { optOut: true } });
    render(
      <TelemetrySettings adminDashboardUrl={"http://admin_dashboard-url/"} />,
    );
    expect(axios.get as jest.Mock).toBeCalledWith(API_TELEMETRY_PATH);
    expect(
      await screen.findByTestId("telemetry-settings__opt_in_radiobutton"),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("telemetry-settings__opt_out_radiobutton"),
    ).toBeInTheDocument();

    const saveButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__save-button",
    );
    const cancelButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__cancel-button",
    );
    expect(saveButton).toBeInTheDocument();
    expect(cancelButton).toBeInTheDocument();
    expect(saveButton.disabled).toBeFalsy();
    expect(cancelButton.disabled).toBeTruthy();

    const adminDashboardUrl: HTMLAnchorElement = await screen.findByTestId(
      "telemetry-settings__admin_dashboard_url",
    );
    expect(adminDashboardUrl).toBeInTheDocument();
    expect(adminDashboardUrl.href).toEqual("http://admin_dashboard-url/");
  });

  it("Click::Save::Success", async () => {
    (axios.get as jest.Mock).mockResolvedValue({ data: { optOut: false } });
    (axios.post as jest.Mock).mockResolvedValue({});

    render(
      <TelemetrySettings adminDashboardUrl={"http://admin_dashboard-url/"} />,
    );

    // Check initial settings
    let optInRadioButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__opt_in_radiobutton",
    );
    let optOutRadioButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__opt_out_radiobutton",
    );
    expect(optInRadioButton.checked).toEqual(true);
    expect(optOutRadioButton.checked).toEqual(false);

    // Emulate click on "Opt Out" radio button
    await userEvent.click(optOutRadioButton);

    // Check settings have changed
    optInRadioButton = await screen.findByTestId(
      "telemetry-settings__opt_in_radiobutton",
    );
    optOutRadioButton = await screen.findByTestId(
      "telemetry-settings__opt_out_radiobutton",
    );
    expect(optInRadioButton.checked).toEqual(false);
    expect(optOutRadioButton.checked).toEqual(true);

    // Check action button states
    const saveButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__save-button",
    );
    const cancelButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__cancel-button",
    );
    expect(saveButton).toBeInTheDocument();
    expect(cancelButton).toBeInTheDocument();
    expect(saveButton.disabled).toBeFalsy();
    expect(cancelButton.disabled).toBeFalsy();

    // Emulate click on "Save" button
    await userEvent.click(saveButton);

    expect(axios.post as jest.Mock).toBeCalledWith(
      API_TELEMETRY_PATH,
      { optOut: true },
      { headers: { "X-CSRFToken": null } },
    );
  });

  it("Click::Save::Failure::Error", async () => {
    (axios.get as jest.Mock).mockResolvedValue({ data: { optOut: false } });
    (axios.post as jest.Mock).mockRejectedValue({ response: { status: 500 } });

    render(
      <TelemetrySettings adminDashboardUrl={"http://admin_dashboard-url/"} />,
    );

    // Emulate click on "Opt Out" radio button
    const optOutRadioButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__opt_out_radiobutton",
    );
    expect(optOutRadioButton.checked).toEqual(false);
    await userEvent.click(optOutRadioButton);

    // Emulate click on "Save" button
    const saveButton = await screen.findByTestId(
      "telemetry-settings__save-button",
    );
    await userEvent.click(saveButton);

    expect(axios.post as jest.Mock).toBeCalledWith(
      API_TELEMETRY_PATH,
      { optOut: true },
      { headers: { "X-CSRFToken": null } },
    );

    // Modals are added to the 'document.body' so perform a basic check for a known field.
    expect(document.body).toHaveTextContent("TelemetryError");
  });

  it("Click::Cancel", async () => {
    (axios.get as jest.Mock).mockResolvedValue({ data: { optOut: false } });

    render(
      <TelemetrySettings adminDashboardUrl={"http://admin_dashboard-url/"} />,
    );

    // Check initial settings
    let optInRadioButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__opt_in_radiobutton",
    );
    let optOutRadioButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__opt_out_radiobutton",
    );
    expect(optInRadioButton.checked).toEqual(true);
    expect(optOutRadioButton.checked).toEqual(false);

    // Emulate click on "Opt Out" radio button
    await userEvent.click(optOutRadioButton);

    // Check settings have changed
    optInRadioButton = await screen.findByTestId(
      "telemetry-settings__opt_in_radiobutton",
    );
    optOutRadioButton = await screen.findByTestId(
      "telemetry-settings__opt_out_radiobutton",
    );
    expect(optInRadioButton.checked).toEqual(false);
    expect(optOutRadioButton.checked).toEqual(true);

    // Emulate click on "Cancel" button
    const cancelButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__cancel-button",
    );
    await userEvent.click(cancelButton);

    // Check original settings are restored
    optInRadioButton = await screen.findByTestId(
      "telemetry-settings__opt_in_radiobutton",
    );
    optOutRadioButton = await screen.findByTestId(
      "telemetry-settings__opt_out_radiobutton",
    );
    expect(optInRadioButton.checked).toEqual(true);
    expect(optOutRadioButton.checked).toEqual(false);

    // Check action button states
    const saveButton: HTMLInputElement = await screen.findByTestId(
      "telemetry-settings__save-button",
    );
    expect(saveButton.disabled).toBeFalsy();
    expect(cancelButton.disabled).toBeTruthy();
  });
});
