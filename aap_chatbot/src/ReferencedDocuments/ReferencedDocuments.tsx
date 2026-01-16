import React from "react";
import ExternalLinkAltIcon from "@patternfly/react-icons/dist/esm/icons/external-link-alt-icon";
import type {
  ReferencedDocument,
  ReferencedDocumentsProp,
} from "../types/Message";
import "./ReferencedDocuments.scss";

export const ReferencedDocuments = (props: ReferencedDocumentsProp) => {
  const { referenced_documents, caption } = props;
  if (
    !Array.isArray(referenced_documents) ||
    referenced_documents.length === 0
  ) {
    return <></>;
  }
  return (
    <div className="pf-chatbot__message pf-chatbot__message--bot">
      <div className="avatar-spacer pf-v6-c-avatar"></div>
      <div className="pf-chatbot__message-contents">
        <div className="pf-chatbot__message-response">
          <div className="pf-chatbot__message-text">
            <div className="pf-v6-c-content--p">
              {caption}
              <ul>
                {referenced_documents.map(
                  (doc: ReferencedDocument, index: number) => (
                    <li key={index}>
                      <a
                        href={doc.docs_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {doc.title}
                        &nbsp;
                        <ExternalLinkAltIcon />
                      </a>
                    </li>
                  ),
                )}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
