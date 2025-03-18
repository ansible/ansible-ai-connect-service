import React, { useEffect, useRef, useState } from "react";

import {
  Bullseye,
  Brand,
  DropdownList,
  DropdownItem,
} from "@patternfly/react-core";

import ChatbotContent from "@patternfly/chatbot/dist/dynamic/ChatbotContent";
import ChatbotWelcomePrompt from "@patternfly/chatbot/dist/dynamic/ChatbotWelcomePrompt";
import ChatbotFooter, {
  ChatbotFootnote,
} from "@patternfly/chatbot/dist/dynamic/ChatbotFooter";
import MessageBar from "@patternfly/chatbot/dist/dynamic/MessageBar";
import MessageBox from "@patternfly/chatbot/dist/dynamic/MessageBox";
import Message from "@patternfly/chatbot/dist/dynamic/Message";
import ChatbotHeader, {
  ChatbotHeaderTitle,
  ChatbotHeaderActions,
} from "@patternfly/chatbot/dist/dynamic/ChatbotHeader";

import lightspeedLogo from "../assets/lightspeed.svg";
import lightspeedLogoDark from "../assets/lightspeed_dark.svg";

import "./AnsibleChatbot.scss";
import {
  inDebugMode,
  isStreamingSupported,
  modelsSupported,
  useChatbot,
} from "../useChatbot/useChatbot";
import { ReferencedDocuments } from "../ReferencedDocuments/ReferencedDocuments";

import type { ExtendedMessage } from "../types/Message";
import {
  Chatbot,
  ChatbotAlert,
  ChatbotConversationHistoryNav,
  ChatbotDisplayMode,
  ChatbotHeaderMain,
  ChatbotHeaderMenu,
  ChatbotHeaderSelectorDropdown,
  ChatbotToggle,
  Conversation,
} from "@patternfly/chatbot";
import {
  CHAT_HISTORY_HEADER,
  FOOTNOTE_DESCRIPTION,
  FOOTNOTE_LABEL,
  FOOTNOTE_TITLE,
} from "../Constants";
import { SystemPromptModal } from "../SystemPromptModal/SystemPromptModal";

const footnoteProps = {
  label: FOOTNOTE_LABEL,
  popover: {
    title: FOOTNOTE_TITLE,
    description: FOOTNOTE_DESCRIPTION,
    bannerImage: {
      src: lightspeedLogo,
      alt: "Lightspeed logo",
    },
    cta: {
      label: "Got it",
      onClick: () => {},
    },
    link: {
      label: "Learn more",
      url: "https://www.redhat.com/",
    },
  },
};

const conversationList: { [key: string]: Conversation[] } = {};
conversationList[CHAT_HISTORY_HEADER] = [];

const conversationStore: Map<string, ExtendedMessage[]> = new Map();

const findMatchingItems = (targetValue: string) => {
  let filteredConversations = Object.entries(conversationList).reduce(
    (acc: any, [key, items]) => {
      const filteredItems = items.filter((item) => {
        const target = targetValue.toLowerCase();
        if (target.length === 0) {
          return true;
        }
        const msgs = conversationStore.get(item.id);
        if (!msgs) {
          return false;
        } else {
          for (const msg of msgs) {
            if (msg.content?.toLowerCase().includes(target)) {
              return true;
            }
          }
        }
        return false;
      });
      if (filteredItems.length > 0) {
        acc[key] = filteredItems;
      }
      return acc;
    },
    {},
  );

  // append message if no items are found
  if (Object.keys(filteredConversations).length === 0) {
    filteredConversations = [
      { id: "13", noIcon: true, text: "No results found" },
    ];
  }
  return filteredConversations;
};

export interface ChatbotContext {
  username?: string | undefined;
}

export const AnsibleChatbot: React.FunctionComponent<ChatbotContext> = (
  context,
) => {
  const {
    messages,
    setMessages,
    botMessage,
    isLoading,
    handleSend,
    alertMessage,
    setAlertMessage,
    selectedModel,
    setSelectedModel,
    conversationId,
    setConversationId,
    systemPrompt,
    setSystemPrompt,
    hasStopButton,
    handleStopButton,
  } = useChatbot();
  const [chatbotVisible, setChatbotVisible] = useState<boolean>(true);
  const [displayMode] = useState<ChatbotDisplayMode>(
    ChatbotDisplayMode.fullscreen,
  );
  const [isDrawerOpen, setIsDrawerOpen] = React.useState(false);
  const [conversations, setConversations] = React.useState<
    Conversation[] | { [key: string]: Conversation[] }
  >(conversationList);
  const historyRef = React.useRef<HTMLButtonElement>(null);

  // https://stackoverflow.com/questions/37620694/how-to-scroll-to-bottom-in-react
  const messagesEndRef = useRef<null | HTMLDivElement>(null);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const onSelectModel = (
    _event: React.MouseEvent<Element, MouseEvent> | undefined,
    value: string | number | undefined,
  ) => {
    setSelectedModel(value as string);
  };

  const setCurrentConversation = (
    newConversationId: string | undefined,
    newMessages: ExtendedMessage[],
  ) => {
    if (messages.length > 0 && conversationId) {
      const chatHistory = conversationList[CHAT_HISTORY_HEADER];
      let found = false;
      for (const chat of chatHistory) {
        if (chat.id === conversationId) {
          found = true;
          break;
        }
      }
      if (!found) {
        chatHistory.push({
          id: conversationId,
          text: messages[0].content || "<<empty>>",
        });
        setConversations(conversationList);
      }
      conversationStore.set(conversationId, messages);
    }
    if (newMessages !== messages) {
      setMessages(newMessages);
    }
    if (newConversationId !== conversationId) {
      setConversationId(newConversationId);
    }
  };

  return (
    <>
      <ChatbotToggle
        tooltipLabel="Chatbot"
        isChatbotVisible={chatbotVisible}
        onToggleChatbot={() => setChatbotVisible(!chatbotVisible)}
      />
      <Chatbot isVisible={chatbotVisible} displayMode={displayMode}>
        <ChatbotConversationHistoryNav
          displayMode={displayMode}
          onDrawerToggle={() => {
            setIsDrawerOpen(!isDrawerOpen);
            setConversations(conversationList);
          }}
          isDrawerOpen={isDrawerOpen}
          setIsDrawerOpen={setIsDrawerOpen}
          activeItemId="1"
          onSelectActiveItem={(e, selectedId: any) => {
            if (selectedId) {
              const retrievedMessages = conversationStore.get(selectedId);
              if (retrievedMessages) {
                setCurrentConversation(selectedId, retrievedMessages);
                setIsDrawerOpen(!isDrawerOpen);
                setConversations(conversationList);
              }
            }
          }}
          conversations={conversations}
          onNewChat={() => {
            setIsDrawerOpen(!isDrawerOpen);
            setCurrentConversation(undefined, []);
          }}
          handleTextInputChange={(value: string) => {
            if (value === "") {
              setConversations(conversationList);
            }
            // this is where you would perform search on the items in the drawer
            // and update the state
            const newConversations: { [key: string]: Conversation[] } =
              findMatchingItems(value);
            setConversations(newConversations);
          }}
          drawerContent={
            <>
              <ChatbotHeader>
                <ChatbotHeaderMain>
                  <ChatbotHeaderMenu
                    ref={historyRef}
                    aria-expanded={isDrawerOpen}
                    onMenuToggle={() => setIsDrawerOpen(!isDrawerOpen)}
                  />
                  <ChatbotHeaderActions>
                    {inDebugMode() && (
                      <SystemPromptModal
                        systemPrompt={systemPrompt}
                        setSystemPrompt={setSystemPrompt}
                      />
                    )}
                  </ChatbotHeaderActions>
                  <ChatbotHeaderTitle>
                    <Bullseye>
                      <div className="show-light">
                        <Brand src={lightspeedLogo} alt="Ansible" />
                      </div>
                      <div className="show-dark">
                        <Brand src={lightspeedLogoDark} alt="Ansible" />
                      </div>
                    </Bullseye>
                  </ChatbotHeaderTitle>
                </ChatbotHeaderMain>
                <ChatbotHeaderActions>
                  {inDebugMode() && (
                    <ChatbotHeaderSelectorDropdown
                      value={selectedModel}
                      onSelect={onSelectModel}
                    >
                      <DropdownList>
                        {modelsSupported.map((m) => (
                          <DropdownItem value={m.model} key={m.model}>
                            {m.model}
                          </DropdownItem>
                        ))}
                      </DropdownList>
                    </ChatbotHeaderSelectorDropdown>
                  )}
                </ChatbotHeaderActions>
              </ChatbotHeader>
              <ChatbotContent>
                <MessageBox>
                  <ChatbotWelcomePrompt
                    title={"Hello " + context?.username}
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
                  {(conversationId &&
                    setCurrentConversation(conversationId, messages)) || <></>}
                  {messages.map(
                    (
                      {
                        referenced_documents,
                        scrollToHere,
                        ...message
                      }: ExtendedMessage,
                      index,
                    ) => (
                      <div key={`m_container_div_${index}`}>
                        {scrollToHere && (
                          <div
                            key={`scroll_div_${index}`}
                            ref={messagesEndRef}
                          />
                        )}
                        <div key={`m_div_${index}`}>
                          <Message key={`m_msg_${index}`} {...message} />
                          <ReferencedDocuments
                            key={`m_docs_${index}`}
                            caption="Refer to the following for more information:"
                            referenced_documents={referenced_documents}
                          />
                        </div>
                      </div>
                    ),
                  )}
                  {isLoading ? (
                    <Message
                      key="9999"
                      isLoading={true}
                      {...botMessage("....")}
                    />
                  ) : (
                    <></>
                  )}
                  {isStreamingSupported() && (
                    <div key={`scroll_div_9999`} ref={messagesEndRef} />
                  )}
                </MessageBox>
              </ChatbotContent>
              <ChatbotFooter>
                <MessageBar
                  onSendMessage={handleSend}
                  hasAttachButton={false}
                  hasStopButton={hasStopButton}
                  handleStopButton={handleStopButton}
                />
                <ChatbotFootnote {...footnoteProps} />
              </ChatbotFooter>
            </>
          }
        ></ChatbotConversationHistoryNav>
      </Chatbot>
    </>
  );
};
AnsibleChatbot.displayName = "AnsibleChatbot";
