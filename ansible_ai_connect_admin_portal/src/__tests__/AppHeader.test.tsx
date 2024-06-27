import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AppHeader } from "../AppHeader";
import userEvent from "@testing-library/user-event";

describe("AppHeader", () => {
  // Store the original 'location' object so that it can be restored for other tests.
  const realLocation = window.location;

  beforeAll(() => {
    // Mock the 'location.assign' function so that we can monitor it.
    // @ts-ignore
    delete window.location;
    window.location = { ...realLocation, assign: jest.fn() };
  });

  afterAll(() => {
    // Restore original 'location' object
    window.location = realLocation;
  });

  it("Rendering", async () => {
    render(<AppHeader userName={"Batman"} />);
    const accountMenu = await screen.findByTestId("page-masthead-dropdown");
    expect(accountMenu).toBeInTheDocument();
    expect(accountMenu).toHaveTextContent("Batman");

    // Check "Logout" option is not present
    expect(screen.queryByText("Logout")).toBeNull();

    // Emulate click on menu button
    const accountMenuToggle = await screen.findByTestId(
      "page-masthead-dropdown__button",
    );
    await userEvent.click(accountMenuToggle);

    // "Logout" menu option should now be present
    expect(await screen.findByText("Logout")).toBeInTheDocument();

    // Emulate clicking on the logout button
    const logoutMenuItem = await screen.findByTestId("app-header__logout");
    await userEvent.click(logoutMenuItem);
    expect(window.location.assign).toBeCalledWith("/logout");
  });
});
