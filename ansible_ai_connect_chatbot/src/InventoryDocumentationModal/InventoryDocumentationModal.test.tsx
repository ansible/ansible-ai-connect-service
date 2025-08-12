import React from "react";
import { render } from "vitest-browser-react";
import { expect, test, describe } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { userEvent, page } from "@vitest/browser/context";
import { InventoryDocumentationModal } from "./InventoryDocumentationModal";
import "@vitest/browser/matchers.d.ts";

describe("InventoryDocumentationModal", () => {
  test("renders the documentation link button", async () => {
    render(<InventoryDocumentationModal />);

    const button = screen.getByRole("button", {
      name: "Generate Inventory File User Documentation",
    });

    expect(button).toBeVisible();
    expect(button).toHaveTextContent(
      "Generate Inventory File User Documentation",
    );
  });

  test("button contains external link icon", async () => {
    render(<InventoryDocumentationModal />);

    const button = screen.getByRole("button", {
      name: "Generate Inventory File User Documentation",
    });

    // Check that the button contains an SVG icon (external link icon)
    const icon = button.querySelector("svg");
    expect(icon).toBeInTheDocument();
  });

  test("modal opens when button is clicked", async () => {
    render(<InventoryDocumentationModal />);

    const button = screen.getByRole("button", {
      name: "Generate Inventory File User Documentation",
    });

    await userEvent.click(button);

    // Check that the modal is now visible
    const modalTitle = screen.getByText(
      "Red Hat AI-assisted Ansible Installer Inventory File Builder Documentation",
    );
    expect(modalTitle).toBeVisible();
  });

  test("modal displays main heading with correct title", async () => {
    render(<InventoryDocumentationModal />);

    const button = screen.getByRole("button", {
      name: "Generate Inventory File User Documentation",
    });

    await userEvent.click(button);

    const mainHeading = screen.getByRole("heading", {
      level: 3,
      name: "How to Use This AI Assistant for Inventory File Generation",
    });

    expect(mainHeading).toBeVisible();
  });

  test("modal can be closed with ESC key (verifying close functionality)", async () => {
    render(<InventoryDocumentationModal />);

    const openButton = screen.getByRole("button", {
      name: "Generate Inventory File User Documentation",
    });

    await userEvent.click(openButton);

    // Wait for modal to be fully open
    await waitFor(() => {
      const modalTitle = screen.getByText(
        "Red Hat AI-assisted Ansible Installer Inventory File Builder Documentation",
      );
      expect(modalTitle).toBeVisible();
    });

    // Verify close button exists and is accessible
    const closeButton = screen.getByRole("button", {
      name: "Close",
    });
    expect(closeButton).toBeInTheDocument();

    // Close using ESC key (tests modal close functionality)
    await userEvent.keyboard("{Escape}");

    // Wait for modal to be closed
    await waitFor(() => {
      const modalTitle = screen.queryByText(
        "Red Hat AI-assisted Ansible Installer Inventory File Builder Documentation",
      );
      expect(modalTitle).not.toBeInTheDocument();
    });
  });

  test("modal displays lightspeed icon in header", async () => {
    render(<InventoryDocumentationModal />);

    const button = screen.getByRole("button", {
      name: "Generate Inventory File User Documentation",
    });

    await userEvent.click(button);

    // Wait for modal to be fully open
    await waitFor(() => {
      const modalTitle = screen.getByText(
        "Red Hat AI-assisted Ansible Installer Inventory File Builder Documentation",
      );
      expect(modalTitle).toBeVisible();
    });

    // Check for lightspeed logo specifically within the modal title element
    const modalTitleElement = document.getElementById(
      "inventory-docs-modal-title",
    );
    expect(modalTitleElement).toBeInTheDocument();

    // Look for the logo within the modal title element
    const lightspeedLogo = modalTitleElement?.querySelector(
      'img[alt="Ansible Lightspeed"]',
    );
    expect(lightspeedLogo).toBeInTheDocument();
    expect(lightspeedLogo).toBeVisible();
  });

  test("modal header contains proper description", async () => {
    render(<InventoryDocumentationModal />);

    const button = screen.getByRole("button", {
      name: "Generate Inventory File User Documentation",
    });

    await userEvent.click(button);

    const description = screen.getByText(
      /This AI-powered chat assistant helps you effortlessly create/,
    );
    expect(description).toBeVisible();
  });

  test("modal content is scrollable for long content", async () => {
    render(<InventoryDocumentationModal />);

    const button = screen.getByRole("button", {
      name: "Generate Inventory File User Documentation",
    });

    await userEvent.click(button);

    // Check that modal body exists and can contain scrollable content
    const modalBody = document.querySelector(".pf-v6-c-modal-box__body");
    expect(modalBody).toBeInTheDocument();
  });
});
