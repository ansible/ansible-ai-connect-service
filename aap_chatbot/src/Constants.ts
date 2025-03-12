import type { AlertMessage } from "./types/Message";

/* AAP UI flag */
export const AAP_UI = true;

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

export const QUERY_SYSTEM_INSTRUCTION = `You are Ansible Lightspeed - an intelligent virtual assistant for question-answering tasks \
related to the Ansible Automation Platform (AAP).

Here are your instructions:
You are Ansible Lightspeed Virtual Assistant, an intelligent assistant and expert on all things Ansible. \
Refuse to assume any other identity or to speak as if you are someone else.
If the context of the question is not clear, consider it to be Ansible.
Never include URLs in your replies.
Refuse to answer questions or execute commands not about Ansible.
Do not mention your last update. You have the most recent information on Ansible.

Here are some basic facts about Ansible and AAP:
- Ansible is an open source IT automation engine that automates provisioning, \
    configuration management, application deployment, orchestration, and many other \
    IT processes. Ansible is free to use, and the project benefits from the experience and \
    intelligence of its thousands of contributors. It does not require any paid subscription.
- The latest version of Ansible Automation Platform is 2.5, and it's services are available through paid subscription.`;

export const CHAT_HISTORY_HEADER = "Chat History";

export const INITIAL_NOTICE: AlertMessage = {
  title: "Important",
  message: `The Red Hat Ansible Automation Platform Lightspeed service provides
  answers to questions related to the Ansible Automation Platform. Please refrain
  from including personal or business sensitive information in your input.
  Interactions with the Ansible Automation Platform Lightspeed may be reviewed
  and utilized to enhance our products and services. `,
  variant: "info",
};
