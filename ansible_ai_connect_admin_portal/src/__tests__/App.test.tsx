import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { App } from "../App";

describe("App", () => {
  it("Rendering::With Username", async () => {
    global.ResizeObserver = jest.fn().mockImplementation(() => ({
      observe: jest.fn(),
      unobserve: jest.fn(),
      disconnect: jest.fn(),
    }));
    window.history.pushState({}, "Test page", "/console");
    render(
      <App
        userName={"Batman"}
        adminDashboardUrl={"http://admin_dashboard-url/"}
      />,
    );
    const accountMenu = await screen.findByTestId("page-masthead-dropdown__button");
    expect(accountMenu).toBeInTheDocument();
    expect(accountMenu).toHaveTextContent("Batman");
  });
});
