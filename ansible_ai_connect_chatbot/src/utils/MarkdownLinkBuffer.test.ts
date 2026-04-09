import { describe, it, expect, beforeEach } from "vitest";
import { MarkdownLinkBuffer } from "./MarkdownLinkBuffer";

describe("MarkdownLinkBuffer", () => {
  let buffer: MarkdownLinkBuffer;

  beforeEach(() => {
    buffer = new MarkdownLinkBuffer();
  });

  describe("process", () => {
    it("should return normal text unchanged", () => {
      const result = buffer.process("Hello world");
      expect(result).toBe("Hello world");
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should buffer markdown URL when ]( is in a single chunk", () => {
      const result1 = buffer.process("Check [link](");
      expect(result1).toBe("Check [link]");
      expect(buffer.hasBufferedContent()).toBe(true);

      const result2 = buffer.process("https://example.com");
      expect(result2).toBe("");
      expect(buffer.hasBufferedContent()).toBe(true);

      const result3 = buffer.process(")");
      expect(result3).toBe("(https://example.com)");
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should handle ] and ( split across chunks", () => {
      const result1 = buffer.process("Check [link]");
      expect(result1).toBe("Check [link");
      expect(buffer.hasBufferedContent()).toBe(true);

      const result2 = buffer.process("(https://example.com)");
      expect(result2).toBe("](https://example.com)");
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should handle false alarm when ] is not followed by (", () => {
      const result1 = buffer.process("Array[5]");
      expect(result1).toBe("Array[5");
      expect(buffer.hasBufferedContent()).toBe(true);

      const result2 = buffer.process(" is good");
      expect(result2).toBe("] is good");
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should handle multiple markdown links in sequence", () => {
      let result = buffer.process("[link1](");
      expect(result).toBe("[link1]");

      result = buffer.process("url1)");
      expect(result).toBe("(url1)");

      result = buffer.process(" and [link2](");
      expect(result).toBe(" and [link2]");

      result = buffer.process("url2)");
      expect(result).toBe("(url2)");
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should handle URL with query parameters and fragments", () => {
      let result = buffer.process("[docs](");
      expect(result).toBe("[docs]");

      result = buffer.process(
        "https://example.com/path?param=value&other=123#section",
      );
      expect(result).toBe("");

      result = buffer.process(")");
      expect(result).toBe(
        "(https://example.com/path?param=value&other=123#section)",
      );
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should handle incomplete URL without closing paren", () => {
      buffer.process("[link](");
      buffer.process("https://");
      buffer.process("example.com/path");
      buffer.process("?param=value");

      expect(buffer.hasBufferedContent()).toBe(true);
    });
  });

  describe("flush", () => {
    it("should return buffered content and reset state", () => {
      buffer.process("Check [link](");
      buffer.process("https://example.com");

      const flushed = buffer.flush();
      expect(flushed).toBe("(https://example.com");
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should return empty string when nothing is buffered", () => {
      const flushed = buffer.flush();
      expect(flushed).toBe("");
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should flush buffered ] character", () => {
      buffer.process("Array[5]");
      expect(buffer.hasBufferedContent()).toBe(true);

      const flushed = buffer.flush();
      expect(flushed).toBe("]");
      expect(buffer.hasBufferedContent()).toBe(false);
    });
  });

  describe("reset", () => {
    it("should clear buffered content", () => {
      buffer.process("[link](");
      buffer.process("https://example.com");
      expect(buffer.hasBufferedContent()).toBe(true);

      buffer.reset();
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should allow processing new content after reset", () => {
      buffer.process("[link1](https://url1");
      buffer.reset();

      const result = buffer.process("Normal text");
      expect(result).toBe("Normal text");
      expect(buffer.hasBufferedContent()).toBe(false);
    });
  });

  describe("hasBufferedContent", () => {
    it("should return false initially", () => {
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should return true when content is buffered", () => {
      buffer.process("[link](");
      expect(buffer.hasBufferedContent()).toBe(true);
    });

    it("should return false after flush", () => {
      buffer.process("[link](https://url");
      expect(buffer.hasBufferedContent()).toBe(true);

      buffer.flush();
      expect(buffer.hasBufferedContent()).toBe(false);
    });
  });

  describe("complex scenarios", () => {
    it("should handle streaming scenario with partial URL at end", () => {
      // Simulate realistic streaming where URL never completes
      let displayed = "";

      displayed += buffer.process("Check out this ");
      expect(displayed).toBe("Check out this ");

      displayed += buffer.process("[documentation](");
      expect(displayed).toBe("Check out this [documentation]");

      displayed += buffer.process("https://");
      expect(displayed).toBe("Check out this [documentation]");

      displayed += buffer.process("docs.example.com/guide");
      expect(displayed).toBe("Check out this [documentation]");

      // Stream ends, flush buffer
      displayed += buffer.flush();
      expect(displayed).toBe(
        "Check out this [documentation](https://docs.example.com/guide",
      );
    });

    it("should handle text with brackets but no links", () => {
      // ] is only buffered when it's at the END of a chunk
      let result = buffer.process("Use array[0");
      expect(result).toBe("Use array[0");
      expect(buffer.hasBufferedContent()).toBe(false);

      result = buffer.process("] to access");
      expect(result).toBe("] to access");
      expect(buffer.hasBufferedContent()).toBe(false);
    });

    it("should handle nested brackets", () => {
      const result1 = buffer.process("[[nested]]");
      expect(result1).toBe("[[nested]");

      const result2 = buffer.process(" text");
      expect(result2).toBe("] text");
      expect(buffer.hasBufferedContent()).toBe(false);
    });
  });
});
