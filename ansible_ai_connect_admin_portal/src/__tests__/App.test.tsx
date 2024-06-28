import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { App } from "../App";

describe("App", () => {
  it("Rendering::With Username", async () => {
    window.history.pushState({}, "Test page", "/console");
    render(
      <App
        userName={"Batman"}
        adminDashboardUrl={"http://admin_dashboard-url/"}
      />,
    );
    const accountMenu = await screen.findByTestId("page-masthead-dropdown");
    expect(accountMenu).toBeInTheDocument();
    expect(accountMenu).toHaveTextContent("Batman");
  });
});
