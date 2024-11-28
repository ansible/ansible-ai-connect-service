import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AppHeader } from "../AppHeader";
import { BrowserRouter } from 'react-router-dom';

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
    render(
      <BrowserRouter>
        <AppHeader userName={"Batman"} />
      </BrowserRouter>
    );
    const accountMenu = await screen.findByTestId("page-masthead-dropdown__button");
    expect(accountMenu).toBeInTheDocument();
    expect(accountMenu).toHaveTextContent("Batman");

    // Check "Logout" option is not present
    expect(screen.queryByText("Logout")).toBeNull();
  });
});
