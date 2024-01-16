import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { PageSidebar } from "../PageSidebar";
import { MemoryRouter } from "react-router-dom";
import { PageMastheadToggle } from "@ansible/ansible-ui-framework";
import userEvent from "@testing-library/user-event";

describe("PageSidebar", () => {
  it("Rendering", async () => {
    const { container } = render(
      <MemoryRouter>
        <PageSidebar
          navigation={[
            {
              id: "nav-item__id",
              label: "nav-item__label",
              path: "/nav-item",
              element: <div />,
              children: [],
            },
          ]}
        />
      </MemoryRouter>,
    );
    const brand = await screen.findByTestId("page-sidebar__brand");
    expect(brand).toBeInTheDocument();

    const navigation = await screen.findByTestId("page-sidebar__navigation");
    expect(navigation).toBeInTheDocument();

    // These are really horrible checks but <PageNavigation/> doesn't have much to query against.
    // eslint-disable-next-line testing-library/no-container, testing-library/no-node-access
    const navItemElement = container.querySelector(".pf-c-nav__link");
    expect(navItemElement).not.toBeNull();
    expect(navItemElement?.getAttribute("id")).toEqual("nav-item__id");
    expect(navItemElement?.textContent).toEqual("nav-item__label");
  });

  it("Rendering::ToggleState", async () => {
    render(
      <MemoryRouter>
        <PageMastheadToggle />
        <PageSidebar
          navigation={[
            {
              id: "nav-item__id",
              label: "nav-item__label",
              path: "/nav-item",
              element: <div />,
              children: [],
            },
          ]}
        />
      </MemoryRouter>,
    );
    // This is really horrible but <PageMasthead/> doesn't have much to query against.
    const toggleButton = screen.getByText(
      (content, element) => element?.tagName.toLowerCase() === "button",
    );

    // Emulate collapse
    await userEvent.click(toggleButton);
    let brand = await screen.findByTestId("page-sidebar__brand");
    expect(brand.className).toContain("pf-m-collapsed");

    let navigation = await screen.findByTestId("page-sidebar__navigation");
    // eslint-disable-next-line testing-library/no-node-access
    expect(navigation.children[0].className).toContain("pf-m-collapsed");

    // Emulate expansion
    await userEvent.click(toggleButton);
    brand = await screen.findByTestId("page-sidebar__brand");
    expect(brand.className).toContain("pf-m-collapsed");

    navigation = await screen.findByTestId("page-sidebar__navigation");
    // eslint-disable-next-line testing-library/no-node-access
    expect(navigation.children[0].className).toContain("pf-m-collapsed");
  });
});
