import { MessageProps } from "@patternfly/chatbot";
import { Sentiment } from "../Constants";

// Types for OLS (OpenShift lightspeed-service) POST /v1/query API
type LLMRequest = {
  query: string;
  conversation_id?: string | null;
  provider?: string | null;
  model?: string | null;
  attachments?: object[] | null;
};

type LLMResponse = {
  conversation_id: string;
  response: string;
  referenced_documents: ReferencedDocument[];
  truncated: boolean;
};

// Type for Ansible AI Connct service /api/v0/ai/talk API
// Currently they are defined in the same way as OLS API
export type ChatRequest = LLMRequest;
export type ChatResponse = LLMResponse;

export type ReferencedDocument = {
  docs_url: string;
  title: string;
};

export type ReferencedDocumentsProp = {
  referenced_documents: ReferencedDocument[];
  caption: string;
};

export type ExtendedMessage = MessageProps & {
  referenced_documents: ReferencedDocument[];
};

export type ChatFeedback = {
  query: string;
  response: ChatResponse;
  sentiment: Sentiment;
};
