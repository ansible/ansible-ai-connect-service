import type { MessageProps } from "@patternfly/virtual-assistant/dist/dynamic/Message";

export type LLMRequest = {
  query: string;
  conversation_id?: string | null;
  provider?: string | null;
  model?: string | null;
  attachments?: object[] | null;
};

export type ReferencedDocument = {
  docs_url: string;
  title: string;
};

export type LLMResponse = {
  conversation_id: string;
  response: string;
  referenced_documents: ReferencedDocument[];
  truncated: boolean;
};

export type ExtendedMessage = MessageProps & {
  referenced_documents: ReferencedDocument[];
};
