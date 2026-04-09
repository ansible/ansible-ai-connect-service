/**
 * MarkdownLinkBuffer
 *
 * Buffers markdown URL patterns during streaming to prevent screen flickering.
 * When a markdown link like [title](url) is streamed character by character,
 * this buffer holds the URL portion until complete, showing only [title] to the user.
 */
export class MarkdownLinkBuffer {
  private buffer = "";
  private inUrl = false;

  /**
   * Process a chunk of text, buffering markdown URL patterns
   * @param chunk - The text chunk to process
   * @returns The processed text that should be displayed (excluding buffered URLs)
   */
  process(chunk: string): string {
    let processedChunk = "";
    let i = 0;

    while (i < chunk.length) {
      const char = chunk[i];

      if (this.inUrl) {
        // We're inside a markdown URL, buffer until we find ')'
        this.buffer += char;

        if (char === ")") {
          // Found closing parenthesis, flush the buffer
          processedChunk += this.buffer;
          this.buffer = "";
          this.inUrl = false;
        }
      } else {
        // Check if we're starting a markdown URL pattern ']('
        if (char === "]" && i + 1 < chunk.length && chunk[i + 1] === "(") {
          // Add ']' to processed chunk so user sees '[title]' immediately
          processedChunk += char;
          // Start buffering from '(' onwards
          this.buffer = chunk[i + 1];
          this.inUrl = true;
          i++; // Skip the '(' since we already processed it
        } else if (char === "]" && i + 1 >= chunk.length) {
          // ']' at the end of chunk, might be start of '](' in next chunk
          // Buffer it to check in next chunk
          this.buffer = char;
        } else if (this.buffer === "]") {
          // Previous chunk ended with ']', check if this starts with '('
          if (char === "(") {
            // Add buffered ']' to processed chunk so user sees it
            processedChunk += this.buffer;
            // Start buffering from '('
            this.buffer = char;
            this.inUrl = true;
          } else {
            // False alarm, flush the buffered ']' and continue
            processedChunk += this.buffer + char;
            this.buffer = "";
          }
        } else {
          // Normal character, add to processed chunk
          processedChunk += char;
        }
      }

      i++;
    }

    return processedChunk;
  }

  /**
   * Flush any remaining buffered content
   * This should be called when the stream ends to ensure no content is lost
   * @returns The buffered content
   */
  flush(): string {
    const content = this.buffer;
    this.buffer = "";
    this.inUrl = false;
    return content;
  }

  /**
   * Reset the buffer to its initial state
   * This should be called when starting a new message
   */
  reset(): void {
    this.buffer = "";
    this.inUrl = false;
  }

  /**
   * Check if there's any buffered content
   * @returns true if the buffer has content
   */
  hasBufferedContent(): boolean {
    return this.buffer.length > 0;
  }
}
