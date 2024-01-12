import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AppDenied } from "../AppDenied";

describe("App", () => {
  it("Rendering::With Username", async () => {
    window.history.pushState({}, "Test page", "/console");
    render(<AppDenied userName={"Batman"} hasSubscription={true} />);
    const accountMenu = await screen.findByTestId("page-masthead-dropdown");
    expect(accountMenu).toBeInTheDocument();
    expect(accountMenu).toHaveTextContent("Batman");
  });

  it("Rendering::Without Username", async () => {
    window.history.pushState({}, "Test page", "/console");
    render(<AppDenied hasSubscription={false} />);
    const accountMenu = await screen.findByTestId("page-masthead-dropdown");
    expect(accountMenu).toBeInTheDocument();
    expect(accountMenu).toHaveTextContent("UnknownUser");
  });
});
