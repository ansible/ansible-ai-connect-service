import React, { useEffect, useRef, useState } from "react";

import {
  Bullseye,
  Brand,
  DropdownList,
  DropdownItem,
  DropdownGroup,
} from "@patternfly/react-core";

import Chatbot, {
  ChatbotDisplayMode,
} from "@patternfly/virtual-assistant/dist/dynamic/Chatbot";
import ChatbotContent from "@patternfly/virtual-assistant/dist/dynamic/ChatbotContent";
import ChatbotWelcomePrompt from "@patternfly/virtual-assistant/dist/dynamic/ChatbotWelcomePrompt";
import ChatbotFooter, {
  ChatbotFootnote,
} from "@patternfly/virtual-assistant/dist/dynamic/ChatbotFooter";
import MessageBar from "@patternfly/virtual-assistant/dist/dynamic/MessageBar";
import MessageBox from "@patternfly/virtual-assistant/dist/dynamic/MessageBox";
import Message from "@patternfly/virtual-assistant/dist/dynamic/Message";
import ChatbotHeader, {
  ChatbotHeaderTitle,
  ChatbotHeaderActions,
  ChatbotHeaderOptionsDropdown,
} from "@patternfly/virtual-assistant/dist/dynamic/ChatbotHeader";

import ExpandIcon from "@patternfly/react-icons/dist/esm/icons/expand-icon";
import OpenDrawerRightIcon from "@patternfly/react-icons/dist/esm/icons/open-drawer-right-icon";
import OutlinedWindowRestoreIcon from "@patternfly/react-icons/dist/esm/icons/outlined-window-restore-icon";

import AnsibleLogo from "./AAP2LineLightMode.png";
import AnsibleLogoDark from "./AAP2LineDarkMode.png";

import "./AnsibleChatbot.scss";
import { botMessage, useChatbot } from "../useChatbot/useChatbot";
import { ReferencedDocuments } from "../ReferencedDocuments/ReferencedDocuments";

import type { ExtendedMessage } from "../types/Message";
import {
  ChatbotAlert,
  ChatbotToggle,
  FileDropZone,
} from "@patternfly/virtual-assistant";

const footnoteProps = {
  label: "Lightspeed uses AI. Check for mistakes.",
  popover: {
    title: "Verify accuracy",
    description: `While Lightspeed strives for accuracy, there's always a possibility of errors. It's a good practice to verify critical information from reliable sources, especially if it's crucial for decision-making or actions.`,
    bannerImage: {
      src: "https://cdn.dribbble.com/userupload/10651749/file/original-8a07b8e39d9e8bf002358c66fce1223e.gif",
      alt: "Example image for footnote popover",
    },
    cta: {
      label: "Got it",
      onClick: () => {
        alert("Do something!");
      },
    },
    link: {
      label: "Learn more",
      url: "https://www.redhat.com/",
    },
  },
};

export const AnsibleChatbot: React.FunctionComponent = () => {
  const { messages, isLoading, handleSend, alertMessage, setAlertMessage } =
    useChatbot();
  const [chatbotVisible, setChatbotVisible] = useState<boolean>(true);
  const [displayMode, setDisplayMode] = useState<ChatbotDisplayMode>(
    ChatbotDisplayMode.default,
  );

  // https://stackoverflow.com/questions/37620694/how-to-scroll-to-bottom-in-react
  const messagesEndRef = useRef<null | HTMLDivElement>(null);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const onSelectDisplayMode = (
    _event: React.MouseEvent<Element, MouseEvent> | undefined,
    value: string | number | undefined,
  ) => {
    setDisplayMode(value as ChatbotDisplayMode);
  };

  const handleFileDrop = () => {}; // no-op for now

  return (
    <>
      <ChatbotToggle
        toolTipLabel="Chatbot"
        isChatbotVisible={chatbotVisible}
        onToggleChatbot={() => setChatbotVisible(!chatbotVisible)}
      />
      <Chatbot isVisible={chatbotVisible} displayMode={displayMode}>
        <ChatbotHeader>
          {/* <ChatbotHeaderMenu
          onMenuToggle={() => alert("Menu toggle clicked")}
        /> */}
          <ChatbotHeaderTitle>
            <Bullseye>
              <div className="show-light">
                <Brand src={AnsibleLogo} alt="Ansible" />
              </div>
              <div className="show-dark">
                <Brand src={AnsibleLogoDark} alt="Ansible" />
              </div>
            </Bullseye>
          </ChatbotHeaderTitle>
          <ChatbotHeaderActions>
            <ChatbotHeaderOptionsDropdown onSelect={onSelectDisplayMode}>
              <DropdownGroup label="Display mode">
                <DropdownList>
                  <DropdownItem
                    value={ChatbotDisplayMode.default}
                    key="switchDisplayOverlay"
                    icon={<OutlinedWindowRestoreIcon aria-hidden />}
                    isSelected={displayMode === ChatbotDisplayMode.default}
                  >
                    <span>Overlay</span>
                  </DropdownItem>
                  <DropdownItem
                    value={ChatbotDisplayMode.docked}
                    key="switchDisplayDock"
                    icon={<OpenDrawerRightIcon aria-hidden />}
                    isSelected={displayMode === ChatbotDisplayMode.docked}
                  >
                    <span>Dock to window</span>
                  </DropdownItem>
                  <DropdownItem
                    value={ChatbotDisplayMode.fullscreen}
                    key="switchDisplayFullscreen"
                    icon={<ExpandIcon aria-hidden />}
                    isSelected={displayMode === ChatbotDisplayMode.fullscreen}
                  >
                    <span>Fullscreen</span>
                  </DropdownItem>
                </DropdownList>
              </DropdownGroup>
            </ChatbotHeaderOptionsDropdown>
          </ChatbotHeaderActions>
        </ChatbotHeader>
        <FileDropZone onFileDrop={handleFileDrop} displayMode={displayMode}>
          <ChatbotContent>
            <MessageBox>
              <ChatbotWelcomePrompt
                title="Hello, Ansible User"
                description="How may I help you today?"
              />
              {alertMessage && (
                <ChatbotAlert
                  variant={alertMessage.variant}
                  onClose={() => {
                    setAlertMessage(undefined);
                  }}
                  title={alertMessage.title}
                >
                  {alertMessage.message}
                </ChatbotAlert>
              )}
              {messages.map(
                (
                  { referenced_documents, ...message }: ExtendedMessage,
                  index,
                ) => (
                  <div key={`m_div_${index}`}>
                    <Message key={`m_msg_${index}`} {...message} />
                    <ReferencedDocuments
                      key={`m_docs_${index}`}
                      caption="Refer to the following for more information:"
                      referenced_documents={referenced_documents}
                    />
                  </div>
                ),
              )}
              {isLoading ? (
                <Message key="9999" isLoading={true} {...botMessage("....")} />
              ) : (
                <></>
              )}
              <div ref={messagesEndRef} />
            </MessageBox>
          </ChatbotContent>
          <ChatbotFooter>
            <MessageBar onSendMessage={handleSend} />
            <ChatbotFootnote {...footnoteProps} />
          </ChatbotFooter>
        </FileDropZone>
      </Chatbot>
    </>
  );
};
AnsibleChatbot.displayName = "AnsibleChatbot";
