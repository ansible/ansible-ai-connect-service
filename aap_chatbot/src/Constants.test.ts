import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  getProductName,
  getSystemInstruction,
  getInitialNotice,
} from "./Constants";

const DEFAULT_NAME = "Ansible Lightspeed Intelligent Assistant";

describe("getProductName", () => {
  afterEach(() => {
    document.getElementById("bot_name")?.remove();
  });

  it("should return the default name when no DOM element exists", () => {
    expect(getProductName()).toBe(DEFAULT_NAME);
  });

  it("should return the name from the DOM element when present", () => {
    const el = document.createElement("span");
    el.id = "bot_name";
    el.innerText = "Automation Intelligent Assistant";
    document.body.appendChild(el);

    expect(getProductName()).toBe("Automation Intelligent Assistant");
  });
});

describe("getSystemInstruction", () => {
  afterEach(() => {
    document.getElementById("bot_name")?.remove();
  });

  it("should include the default product name in the system instruction", () => {
    const instruction = getSystemInstruction();
    expect(instruction).toContain(DEFAULT_NAME);
    expect(instruction).toContain("<SYSTEM_ROLE>");
  });

  it("should use the DOM-provided name in the system instruction", () => {
    const el = document.createElement("span");
    el.id = "bot_name";
    el.innerText = "Custom Bot Name";
    document.body.appendChild(el);

    const instruction = getSystemInstruction();
    expect(instruction).toContain("Custom Bot Name");
    expect(instruction).not.toContain(DEFAULT_NAME);
  });
});

describe("getInitialNotice", () => {
  afterEach(() => {
    document.getElementById("bot_name")?.remove();
  });

  it("should return an alert message with the default product name", () => {
    const notice = getInitialNotice();
    expect(notice.title).toBe("Important");
    expect(notice.variant).toBe("info");
    expect(notice.message).toContain(DEFAULT_NAME);
  });

  it("should use the DOM-provided name in the notice", () => {
    const el = document.createElement("span");
    el.id = "bot_name";
    el.innerText = "Automation Intelligent Assistant";
    document.body.appendChild(el);

    const notice = getInitialNotice();
    expect(notice.message).toContain("Automation Intelligent Assistant");
    expect(notice.message).not.toContain(DEFAULT_NAME);
  });
});
