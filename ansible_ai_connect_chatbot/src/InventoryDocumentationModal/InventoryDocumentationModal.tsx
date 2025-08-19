import React from "react";
import {
  Button,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  ModalVariant,
  Brand,
  Title,
  List,
  ListItem,
} from "@patternfly/react-core";
import ExternalLinkAltIcon from "@patternfly/react-icons/dist/esm/icons/external-link-alt-icon";
import lightspeedLogo from "../assets/lightspeed.svg";
import lightspeedLogoDark from "../assets/lightspeed_dark.svg";

export const InventoryDocumentationModal: React.FunctionComponent = () => {
  const [isModalOpen, setModalOpen] = React.useState(false);

  const handleModalToggle = (_event: KeyboardEvent | React.MouseEvent) => {
    setModalOpen(!isModalOpen);
  };

  const LightspeedIcon = () => (
    <div style={{ display: "flex", alignItems: "center" }}>
      <div className="show-light">
        <Brand
          src={lightspeedLogo}
          alt="Ansible Lightspeed"
          style={{ height: "24px" }}
        />
      </div>
      <div className="show-dark">
        <Brand
          src={lightspeedLogoDark}
          alt="Ansible Lightspeed"
          style={{ height: "24px" }}
        />
      </div>
    </div>
  );

  return (
    <React.Fragment>
      <Button
        variant="link"
        aria-label="Generate Inventory File User Documentation"
        icon={<ExternalLinkAltIcon />}
        onClick={handleModalToggle}
      >
        Generate Inventory File User Documentation
      </Button>
      <Modal
        variant={ModalVariant.large}
        isOpen={isModalOpen}
        onClose={handleModalToggle}
        aria-labelledby="inventory-docs-modal-title"
        aria-describedby="inventory-docs-modal-description"
      >
        <ModalHeader
          title="Red Hat AI-assisted Ansible Installer Inventory File Builder Documentation"
          description="This AI-powered chat assistant helps you effortlessly create the correct inventory file needed for your Ansible Automation Platform installation.  It uses generative AI to build and accurate and ready-to-use file based on your conversation."
          descriptorId="inventory-docs-modal-description"
          labelId="inventory-docs-modal-title"
          titleIconVariant={LightspeedIcon}
        />
        <ModalBody>
          <div>
            <Title headingLevel="h3" size="lg">
              Overview
            </Title>
            <p>
              This chat assistant helps you create an inventory file for Ansible
              Automation Platform installation. It uses generative AI to build
              an accurate, ready-to-use file from your conversations quickly. It
              walks you through the initial setup questions and then creates a
              complete, custom inventory file that you can use right away for
              your installation.
            </p>
            <br />
            <p>
              <strong>Important:</strong> The chat assistant generates an
              inventory file tailored to your environment; it does not perform
              the installation itself. You must use the generated inventory file
              to then install the Ansible Automation Platform (RPM or
              containerized).
            </p>
            <br />
            <Title headingLevel="h3" size="lg">
              Procedure
            </Title>
            <ol style={{ paddingLeft: "20px" }}>
              <li style={{ marginBottom: "16px" }}>
                Click <strong>Installing Ansible Automation Platform.</strong>
              </li>
              <li style={{ marginBottom: "16px" }}>
                Specify your installation type and basic requirements.
                <br />
                To get more focused guidance from the chat assistant from the
                start, provide clear and direct statements.
                <br />
                <br />
                Here are some example prompts:
                <List>
                  <ListItem>
                    I want to install AAP using the containerized installer
                  </ListItem>
                  <ListItem>
                    I need help with an RPM installation of Ansible Automation
                    Platform
                  </ListItem>
                  <ListItem>
                    Help me create an inventory file for my AAP setup
                  </ListItem>
                </List>
              </li>
              <li style={{ marginBottom: "16px" }}>
                Specify your infrastructure requirements.
                <br />
                The chatbot will then systemically gather details about your
                environment and create an inventory file that aligns with those
                requirements.
                <br />
                <br />
                Examples of infrastructure requirements include:
                <List>
                  <ListItem>Number of servers you're installing</ListItem>
                  <ListItem>
                    Specific roles each server will play (such as controllers,
                    execution nodes, or database servers)
                  </ListItem>
                  <ListItem>
                    IP addresses or hostnames for each machine
                  </ListItem>
                  <ListItem>Network configuration</ListItem>
                  <ListItem>
                    External database details, if you're not using the built-in
                    database
                  </ListItem>
                  <ListItem>
                    Any special networking requirements for your environment
                  </ListItem>
                </List>
              </li>
              <li style={{ marginBottom: "16px" }}>
                Specify advanced requirements.
                <br />
                Specify any further production environment requirements that
                extend beyond the basic installation needs. The chatbot
                incorporates these requirements into the inventory file and
                explains the implications of each configuration choice.
                <br />
                <br />
                Examples of advanced requirements include:
                <List>
                  <ListItem>High Availability (HA) configurations</ListItem>
                  <ListItem>
                    Load balancing setups for multiple controller nodes
                  </ListItem>
                  <ListItem>SSL/TLS certificate requirements</ListItem>
                  <ListItem>
                    Any custom variables specific to your organization's
                    standards
                  </ListItem>
                </List>
              </li>
              <li style={{ marginBottom: "16px" }}>
                Review and refine your inventory file.
                <br />
                After the chatbot generates an inventory file, you can refine it
                further by asking for changes. You can ask for changes like "Can
                you add another execution node?" You can also request
                explanations about specific variables by asking questions like
                "What does this variable do?"
                <br />
                <br />
                If your inventory file contains all your infrastructure
                requirements, you can ask the chatbot to validate it by asking
                questions like "Is this configuration correct for production?".
                The chatbot will then explain the reasoning behind configuration
                choices and suggest improvements based on best practices.
              </li>
              <li style={{ marginBottom: "16px" }}>
                Save your inventory file.
                <br />
                After you are satisfied with the inventory file configuration,
                ask the chatbot to provide the complete inventory file in a
                format that you can copy and save in your environment as
                inventory.ini or with any other name (but with an .ini extension
                only).
              </li>
              <li style={{ marginBottom: "16px" }}>
                Know the next steps in the installation process.
                <br />
                You can ask the chatbot to explain the next steps in your
                installation process and help troubleshoot potential issues you
                might encounter. Questions like "What do I do after creating
                this inventory?" or "What if I encounter errors during
                installation?" can provide valuable guidance for the
                implementation phase.
              </li>
            </ol>
            <div>
              <p>Here are some example conversation prompts:</p>
              <p>
                <strong>For Containerized installation:</strong> I want to
                install AAP 2.5 using containers on 3 RHEL 9 servers. I need one
                controller and two execution nodes.
              </p>
              <p>
                <strong>For RPM installation:</strong> Help me create an
                inventory for RPM installation with HA controllers and an
                external PostgreSQL database.
              </p>
            </div>
            <br />
            <Title headingLevel="h3" size="lg">
              Best Practices for Optimal Results
            </Title>
            <p>To get the most accurate and useful inventory files:</p>
            <List>
              <ListItem>
                Be as specific as possible when describing your infrastructure.
                Provide exact server details, IP addresses, and hostnames rather
                than vague descriptions.
              </ListItem>
              <ListItem>
                Ask follow-up questions if something isn't clear. The assistant
                can clarify configuration options and explain the reasoning
                behind recommendations.
              </ListItem>
              <ListItem>
                Always ask the chatbot to validate your setup and explain why
                certain configurations are recommended for your specific use
                case.
              </ListItem>
              <ListItem>
                Consider starting with a simple setup and gradually adding
                complexity as you become more comfortable with the process.
              </ListItem>
            </List>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button
            key="close"
            variant="primary"
            onClick={handleModalToggle}
            aria-label="Close inventory documentation modal"
          >
            Close
          </Button>
        </ModalFooter>
      </Modal>
    </React.Fragment>
  );
};

InventoryDocumentationModal.displayName = "InventoryDocumentationModal";
