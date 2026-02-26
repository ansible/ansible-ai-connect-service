import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AppHeader } from "../AppHeader";
import { BrowserRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";

describe("AppHeader", () => {
  let submitSpy: jest.SpyInstance;

  beforeAll(() => {
    submitSpy = jest
      .spyOn(HTMLFormElement.prototype, "submit")
      .mockImplementation(() => {});
  });

  afterAll(() => {
    submitSpy.mockRestore();
  });

  afterEach(() => {
    submitSpy.mockClear();
  });

  it("Rendering", async () => {
    render(
      <BrowserRouter>
        <AppHeader userName={"Batman"} />
      </BrowserRouter>,
    );
    const accountMenu = await screen.findByTestId(
      "page-masthead-dropdown__button",
    );
    expect(accountMenu).toBeInTheDocument();
    expect(accountMenu).toHaveTextContent("Batman");

    // Check "Logout" option is not present
    expect(screen.queryByText("Logout")).toBeNull();

    // Emulate click on menu button
    await userEvent.click(accountMenu);

    // "Logout" menu option should now be present
    const logoutMenuButton = await screen.findByText("Logout");
    expect(logoutMenuButton).toBeInTheDocument();

    // Emulate clicking on the logout button
    await userEvent.click(logoutMenuButton);

    expect(submitSpy).toHaveBeenCalled();
    const form = submitSpy.mock.contexts[0] as HTMLFormElement;
    expect(form).toHaveAttribute("action", "/logout/");
    expect(form).toHaveAttribute("method", "POST");
    expect(form).toHaveFormValues({ csrfmiddlewaretoken: "" });
  });
});
