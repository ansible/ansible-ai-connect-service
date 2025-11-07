import React, { useEffect, useRef, useState } from "react";

import {
  Bullseye,
  Brand,
  DropdownList,
  DropdownItem,
  ExpandableSection,
  Label,
  Tooltip,
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
  ChatbotHeaderActions,
  ChatbotHeaderNewChatButton,
  ChatbotHeaderTitle,
} from "@patternfly/chatbot/dist/dynamic/ChatbotHeader";

import InfoCircleIcon from "@patternfly/react-icons/dist/esm/icons/info-circle-icon";
import lightspeedLogo from "../assets/lightspeed.svg";
import lightspeedLogoDark from "../assets/lightspeed_dark.svg";

import "./AnsibleChatbot.scss";
import {
  bodyElement,
  inDebugMode,
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
  ChatbotFootnoteProps,
  ChatbotHeaderMain,
  ChatbotHeaderMenu,
  ChatbotHeaderSelectorDropdown,
  ChatbotToggle,
  Conversation,
} from "@patternfly/chatbot";
import {
  CHAT_HISTORY_HEADER,
  FOOTNOTE_LABEL,
  REFERENCED_DOCUMENTS_CAPTION,
} from "../Constants";
import { SystemPromptModal } from "../SystemPromptModal/SystemPromptModal";
import { InventoryDocumentationModal } from "../InventoryDocumentationModal/InventoryDocumentationModal";

const footnoteProps: ChatbotFootnoteProps = {
  label: FOOTNOTE_LABEL,
};

const conversationList: { [key: string]: Conversation[] } = {};
conversationList[CHAT_HISTORY_HEADER] = [];

export const conversationStore: Map<string, ExtendedMessage[]> = new Map();

const resetConversationState = () => {
  conversationList[CHAT_HISTORY_HEADER] = [];
  conversationStore.clear();
};

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

export const AnsibleChatbot: React.FunctionComponent = () => {
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
    isStreamingSupported,
    bypassTools,
    setBypassTools,
  } = useChatbot();

  const welcomePrompts = [
    {
      title: "Using Ansible Automation Platform",
      message: "I have a question about using Ansible Automation Platform",
    },
    {
      title: "Installing Ansible Automation Platform",
      message:
        "I want to learn more about installing Ansible Automation Platform",
    },
    {
      title: "Operating Ansible Automation Platform",
      message:
        "I want to learn how to operate and monitor Ansible Automation Platform",
    },
  ].map((prompt) => ({
    title: prompt.title,
    message: prompt.message,
    onClick: () => handleSend(prompt.message),
  }));

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

  useEffect(
    () =>
      // Fired on component mount (componentDidMount)
      () => {
        // Anything in here is fired on component unmount (componentWillUnmount)
        resetConversationState();
      },
    [],
  );

  useEffect(() => {
    // Only auto-scroll if the last message has scrollToHere flag set
    // This prevents unwanted scrolling when feedback messages are added inline
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.scrollToHere) {
      scrollToBottom();
    }
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
                    tooltipProps={{ appendTo: bodyElement, content: "Menu" }}
                  />
                  <ChatbotHeaderActions>
                    {inDebugMode() && (
                      <SystemPromptModal
                        systemPrompt={systemPrompt}
                        setSystemPrompt={setSystemPrompt}
                        bypassTools={bypassTools}
                        setBypassTools={setBypassTools}
                      />
                    )}
                  </ChatbotHeaderActions>
                  <ChatbotHeaderNewChatButton
                    data-testid="header-new-chat-button"
                    onClick={() => setCurrentConversation(undefined, [])}
                  />
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
                  <Tooltip
                    content="This is a Developer Preview feature containing functionality that Red Hat is considering for possible inclusion into supported versions. Developer Preview versions are not fully tested and are not intended for production use. Features may change or be removed at any time."
                    position="left"
                    maxWidth="25rem"
                    isContentLeftAligned
                  >
                    <Label color="orange" icon={<InfoCircleIcon />}>
                      Preview
                    </Label>
                  </Tooltip>
                  <InventoryDocumentationModal />
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
              {alertMessage && (
                <div className="ansible-chatbot-alert-outer">
                  <div className="ansible-chatbot-alert-inner">
                    <ChatbotAlert
                      variant={alertMessage.variant}
                      onClose={() => {
                        setAlertMessage(undefined);
                      }}
                      title={alertMessage.title}
                    >
                      {alertMessage.message}
                    </ChatbotAlert>
                  </div>
                </div>
              )}
              <ChatbotContent>
                <MessageBox>
                  <ChatbotWelcomePrompt
                    title="Hello, Ansible User"
                    description="How may I help you today?"
                    prompts={welcomePrompts}
                  />
                  {(conversationId &&
                    setCurrentConversation(conversationId, messages)) || <></>}
                  {messages.map(
                    (
                      {
                        referenced_documents,
                        scrollToHere,
                        collapse,
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
                        {collapse ? (
                          <div key={`m_div_${index}`}>
                            <ExpandableSection
                              toggleTextCollapsed="Show more"
                              toggleTextExpanded="Show less"
                            >
                              <Message
                                key={`m_msg_${index}`}
                                {...message}
                                isLoading={isLoading && !message.content}
                              />
                              <ReferencedDocuments
                                key={`m_docs_${index}`}
                                caption={REFERENCED_DOCUMENTS_CAPTION}
                                referenced_documents={referenced_documents}
                              />
                            </ExpandableSection>
                          </div>
                        ) : (
                          <div key={`m_div_${index}`}>
                            <Message key={`m_msg_${index}`} {...message} />
                            <ReferencedDocuments
                              key={`m_docs_${index}`}
                              caption={REFERENCED_DOCUMENTS_CAPTION}
                              referenced_documents={referenced_documents}
                            />
                          </div>
                        )}
                      </div>
                    ),
                  )}
                  {messages.at(-1)?.role === "user" && isLoading ? (
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
                  buttonProps={{
                    send: {
                      // @ts-ignore
                      props: { tooltipProps: { appendTo: bodyElement } },
                    },
                    stop: {
                      // @ts-ignore
                      props: { tooltipProps: { appendTo: bodyElement } },
                    },
                  }}
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
