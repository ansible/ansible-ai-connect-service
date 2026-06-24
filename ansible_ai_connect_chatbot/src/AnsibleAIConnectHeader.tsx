import React from "react";
import {
  Bullseye,
  Brand,
  DropdownList,
  DropdownItem,
  Label,
  Tooltip,
} from "@patternfly/react-core";
import ChatbotHeader, {
  ChatbotHeaderActions,
  ChatbotHeaderNewChatButton,
  ChatbotHeaderTitle,
} from "@patternfly/chatbot/dist/dynamic/ChatbotHeader";
import InfoCircleIcon from "@patternfly/react-icons/dist/esm/icons/info-circle-icon";
import {
  ChatbotHeaderMain,
  ChatbotHeaderMenu,
  ChatbotHeaderSelectorDropdown,
} from "@patternfly/chatbot";
import { DebugSettingsModal } from "@ansible/ansible-ai-connect-chatbot";
import type { HeaderRenderProps } from "@ansible/ansible-ai-connect-chatbot";
import { InventoryDocumentationModal } from "./InventoryDocumentationModal/InventoryDocumentationModal";
import lightspeedLogo from "./assets/lightspeed.svg";
import lightspeedLogoDark from "./assets/lightspeed_dark.svg";

export const AnsibleAIConnectHeader: React.FC<HeaderRenderProps> = (props) => {
  const onSelectModel = (
    _event: React.MouseEvent<Element, MouseEvent> | undefined,
    value: string | number | undefined,
  ) => {
    props.setSelectedModel(value as string);
  };

  return (
    <ChatbotHeader>
      <ChatbotHeaderMain>
        <ChatbotHeaderMenu
          ref={props.historyRef}
          aria-expanded={props.isDrawerOpen}
          onMenuToggle={() => props.setIsDrawerOpen(!props.isDrawerOpen)}
          tooltipProps={{ appendTo: props.bodyElement, content: "Menu" }}
        />
        <ChatbotHeaderNewChatButton
          data-testid="header-new-chat-button"
          onClick={() => props.setCurrentConversation(undefined, [])}
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
        {props.inDebugMode && (
          <DebugSettingsModal
            bypassTools={props.bypassTools}
            setBypassTools={props.setBypassTools}
          />
        )}
        {props.inDebugMode && (
          <ChatbotHeaderSelectorDropdown
            value={props.selectedModel}
            onSelect={onSelectModel}
          >
            <DropdownList>
              {props.models.map((m) => (
                <DropdownItem value={m.model} key={m.model}>
                  {m.model}
                </DropdownItem>
              ))}
            </DropdownList>
          </ChatbotHeaderSelectorDropdown>
        )}
      </ChatbotHeaderActions>
    </ChatbotHeader>
  );
};

AnsibleAIConnectHeader.displayName = "AnsibleAIConnectHeader";
