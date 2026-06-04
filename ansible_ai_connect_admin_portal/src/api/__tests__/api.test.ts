import "@testing-library/jest-dom";
import { readCookie, readCsrfCookie } from "../api";

// Browsers reject __Host- prefixed cookies on non-HTTPS pages, so we mock
// document.cookie getter instead of setting real cookies.
describe("API", () => {
  let cookieSpy: jest.SpyInstance;

  beforeEach(() => {
    cookieSpy = jest.spyOn(document, "cookie", "get");
  });

  afterEach(() => {
    cookieSpy.mockRestore();
  });

  describe("readCookie", () => {
    it("Cookie extraction::Empty string", () => {
      cookieSpy.mockReturnValue("");
      const cookie = readCookie("__Host-csrftoken");
      expect(cookie).toBeNull();
    });

    it("Cookie extraction::Single::With whitespace", () => {
      cookieSpy.mockReturnValue("__Host-csrftoken=12345   ");
      const cookie = readCookie("__Host-csrftoken");
      expect(cookie).toEqual("12345");
    });

    it("Cookie extraction::Single::Without whitespace", () => {
      cookieSpy.mockReturnValue("__Host-csrftoken=12345");
      const cookie = readCookie("__Host-csrftoken");
      expect(cookie).toEqual("12345");
    });

    it("Cookie extraction::Multiple::With whitespace", () => {
      cookieSpy.mockReturnValue("smurf=abcdef  ; __Host-csrftoken=12345   ");
      const cookie = readCookie("__Host-csrftoken");
      expect(cookie).toEqual("12345");
    });

    it("Cookie extraction::Multiple::Without whitespace", () => {
      cookieSpy.mockReturnValue("smurf=abcdef;__Host-csrftoken=12345");
      const cookie = readCookie("__Host-csrftoken");
      expect(cookie).toEqual("12345");
    });

    it("does not match partial cookie names", () => {
      cookieSpy.mockReturnValue("__Host-csrftoken_extra=wrong");
      expect(readCookie("__Host-csrftoken")).toBeNull();
    });
  });

  describe("readCsrfCookie", () => {
    it("returns __Host-csrftoken when present", () => {
      cookieSpy.mockReturnValue("__Host-csrftoken=prod_token");
      expect(readCsrfCookie()).toEqual("prod_token");
    });

    it("falls back to csrftoken when __Host-csrftoken is absent", () => {
      cookieSpy.mockReturnValue("csrftoken=dev_token");
      expect(readCsrfCookie()).toEqual("dev_token");
    });

    it("prefers __Host-csrftoken over csrftoken", () => {
      cookieSpy.mockReturnValue(
        "csrftoken=dev_token; __Host-csrftoken=prod_token",
      );
      expect(readCsrfCookie()).toEqual("prod_token");
    });

    it("falls back to DOM csrf_token element when no cookie", () => {
      cookieSpy.mockReturnValue("");
      const div = document.createElement("div");
      div.id = "csrf_token";
      div.textContent = "dom_csrf_token";
      document.body.appendChild(div);
      expect(readCsrfCookie()).toEqual("dom_csrf_token");
      document.body.removeChild(div);
    });

    it("returns null when neither cookie nor DOM element is present", () => {
      cookieSpy.mockReturnValue("");
      expect(readCsrfCookie()).toBeNull();
    });
  });
});
