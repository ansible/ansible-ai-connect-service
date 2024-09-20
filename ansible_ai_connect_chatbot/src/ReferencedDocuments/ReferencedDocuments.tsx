import "./ReferencedDocuments.scss";

export const ReferencedDocuments = (props: any) => {
  const { referenced_documents, caption } = props;
  if (referenced_documents.length === 0) {
    return <></>;
  }
  return (
    <div className="pf-chatbot__message pf-chatbot__message--bot">
      <div className="avatar-spacer pf-v6-c-avatar"></div>
      <div className="pf-chatbot__message-contents">
        <div className="pf-chatbot__message-response">
          <div className="pf-chatbot__message-text">
            <div className="pf-v6-c-contents--p">
              {caption}
              <ul>
                {referenced_documents.map((doc: any, index: number) => (
                  <li key={index}>
                    <a
                      href={doc.docs_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {doc.title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
