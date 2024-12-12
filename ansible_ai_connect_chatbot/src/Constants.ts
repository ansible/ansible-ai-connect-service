/* Slightly lower than CloudFront's timeout which is 30s. */
export const API_TIMEOUT = 28000;

/* Timeout message */
export const TIMEOUT_MSG =
  "_Chatbot service is taking too long to respond to your query. " +
  "Try to submit a different query or try again later._";

/* Too many request message */
export const TOO_MANY_REQUESTS_MSG =
  "_Chatbot service is busy with too many requests. Please try again later._";

/* Footnote label */
export const FOOTNOTE_LABEL = "Lightspeed uses AI. Check for mistakes.";

/* Footnote title */
export const FOOTNOTE_TITLE = "Verify accuracy";

/* Footnote description */
export const FOOTNOTE_DESCRIPTION =
  "While Lightspeed strives for accuracy, there's always a possibility of errors. It's a good practice to verify critical information from reliable sources, especially if it's crucial for decision-making or actions.";

/* Sentiments */
export enum Sentiment {
  THUMBS_UP = 0,
  THUMBS_DOWN = 1,
}

export const GITHUB_NEW_ISSUE_BASE_URL =
  "https://github.com/ansible/ansible-lightspeed-va-feedback/issues/new";
