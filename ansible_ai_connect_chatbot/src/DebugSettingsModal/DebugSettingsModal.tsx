import React from "react";
import {
  Button,
  Checkbox,
  Form,
  FormGroup,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  ModalVariant,
} from "@patternfly/react-core";
import WrenchIcon from "@patternfly/react-icons/dist/esm/icons/wrench-icon";

interface DebugSettingsModalProps {
  bypassTools: boolean;
  setBypassTools: (b: boolean) => void;
}

export const DebugSettingsModal: React.FunctionComponent<
  DebugSettingsModalProps
> = (props) => {
  const [isModalOpen, setModalOpen] = React.useState(false);
  const { bypassTools, setBypassTools } = props;

  const handleModalToggle = (_event: KeyboardEvent | React.MouseEvent) => {
    setModalOpen(!isModalOpen);
  };

  const handleBypassToolsChange = (_event: any, value: boolean) => {
    setBypassTools(value);
  };

  return (
    <React.Fragment>
      <Button
        variant="link"
        aria-label="DebugSettings"
        icon={<WrenchIcon />}
        onClick={handleModalToggle}
      ></Button>
      <Modal
        variant={ModalVariant.small}
        isOpen={isModalOpen}
        onClose={handleModalToggle}
        aria-labelledby="debug-settings-form-title"
        aria-describedby="debug-settings-description-form"
      >
        <ModalHeader
          title="Debug Settings"
          description="Configure debug options for the chatbot."
          descriptorId="debug-settings-description-form"
          labelId="debug-settings-form-title"
        />
        <ModalBody>
          <Form id="debug-settings-form">
            <FormGroup fieldId="bypass-tools">
              <Checkbox
                id="bypass-tools"
                label="Bypass Tools"
                isChecked={bypassTools}
                aria-label="bypass-tools-checkbox"
                onChange={handleBypassToolsChange}
              ></Checkbox>
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            key="close"
            variant="primary"
            form="debug-settings-form"
            onClick={handleModalToggle}
            aria-label="debug-settings-form-button"
          >
            Close
          </Button>
        </ModalFooter>
      </Modal>
    </React.Fragment>
  );
};
DebugSettingsModal.displayName = "DebugSettingsModal";
