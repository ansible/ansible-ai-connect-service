import React from "react";
import {
  Button,
  Form,
  FormGroup,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  ModalVariant,
  TextArea,
} from "@patternfly/react-core";
import WrenchIcon from "@patternfly/react-icons/dist/esm/icons/wrench-icon";

interface SystemPromptModalProps {
  systemPrompt: string;
  setSystemPrompt: (s: string) => void;
}

export const SystemPromptModal: React.FunctionComponent<
  SystemPromptModalProps
> = (props) => {
  const [isModalOpen, setModalOpen] = React.useState(false);
  const { systemPrompt, setSystemPrompt } = props;

  const handleModalToggle = (_event: KeyboardEvent | React.MouseEvent) => {
    setModalOpen(!isModalOpen);
  };

  const handleSystemPromptInputChange = (_event: any, value: string) => {
    setSystemPrompt(value);
  };

  return (
    <React.Fragment>
      <Button
        variant="link"
        aria-label="SystemPrompt"
        icon={<WrenchIcon />}
        onClick={handleModalToggle}
      ></Button>
      <Modal
        variant={ModalVariant.small}
        isOpen={isModalOpen}
        onClose={handleModalToggle}
        aria-labelledby="system-prompt-form-title"
        aria-describedby="system-prompt-description-form"
      >
        <ModalHeader
          title="System prompt"
          description="Enter a system prompt to override the default one."
          descriptorId="system-prompt-description-form"
          labelId="system-prompt-form-title"
        />
        <ModalBody>
          <Form id="system-prompt-form">
            <FormGroup label="System Prompt" isRequired fieldId="system-prompt">
              <TextArea
                isRequired
                id="system-prompt"
                name="system-prompt"
                value={systemPrompt}
                onChange={handleSystemPromptInputChange}
                aria-label="system-prompt-form-text-area"
                rows={15}
              />
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            key="create"
            variant="primary"
            form="system-prompt-form"
            onClick={handleModalToggle}
            aria-label="system-prompt-form-button"
          >
            Close
          </Button>
        </ModalFooter>
      </Modal>
    </React.Fragment>
  );
};
SystemPromptModal.displayName = "SystemPromptModal";
