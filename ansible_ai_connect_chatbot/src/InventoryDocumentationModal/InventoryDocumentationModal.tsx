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
              How to Use This AI Assistant for Inventory File Generation
            </Title>
            <p>
              This AI-powered chatbot helps you create accurate inventory files
              for your Ansible Automation Platform (AAP) installation. The
              assistant is designed to guide you through the entire process,
              from initial setup questions to generating a complete,
              ready-to-use inventory file tailored to your specific environment
              and requirements.
            </p>
            <br />
            <Title headingLevel="h4" size="md">
              Getting Started
            </Title>
            <p>
              Begin your interaction by clearly stating your installation type
              and basic requirements. The chatbot responds best to specific
              statements such as "I want to install AAP using the containerized
              installer," "I need help with an RPM installation of Ansible
              Automation Platform," or "Help me create an inventory file for my
              AAP setup." Being explicit about whether you're planning a
              containerized or RPM-based installation helps the assistant
              provide more targeted guidance from the start.
            </p>
            <br />
            <Title headingLevel="h4" size="md">
              Providing Infrastructure Information
            </Title>
            <p>
              The chatbot will systematically gather details about your
              environment to ensure the generated inventory matches your
              infrastructure. Be prepared to share the number of servers you're
              installing on, the specific roles each server will play (such as
              controllers, execution nodes, or database servers), and the IP
              addresses or hostnames for each machine. Additionally, provide
              information about your network configuration, any external
              database details if you're not using the built-in database, and
              any special networking requirements your environment may have.
            </p>
            <br />
            <Title headingLevel="h4" size="md">
              Specifying Advanced Requirements
            </Title>
            <p>
              For production deployments, you'll likely have additional
              requirements beyond basic installation. Tell the chatbot about any
              needs for High Availability (HA) configurations, load balancing
              setups for multiple controller nodes, SSL/TLS certificate
              requirements, or any custom variables specific to your
              organization's standards. The assistant can incorporate these
              requirements into the inventory file and explain the implications
              of each configuration choice.
            </p>
            <br />
            <Title headingLevel="h4" size="md">
              Reviewing and Refining Your Configuration
            </Title>
            <p>
              Once the chatbot generates an initial inventory file, you can work
              collaboratively to refine it. Ask for modifications like "Can you
              add another execution node?" or request explanations about
              specific variables with questions like "What does this variable
              do?" You can also validate your setup by asking "Is this
              configuration correct for production?" The assistant can explain
              the reasoning behind configuration choices and suggest
              improvements based on best practices.
            </p>
            <br />
            <Title headingLevel="h4" size="md">
              Finalizing Your Inventory
            </Title>
            <p>
              When you're satisfied with the configuration, ask the chatbot to
              provide the complete inventory file in a format you can copy and
              use immediately. The assistant can also explain the next steps in
              your installation process and help troubleshoot potential issues
              you might encounter. Questions like "What do I do after creating
              this inventory?" and "What if I encounter errors during
              installation?" can provide valuable guidance for the
              implementation phase.
            </p>
            <br />
            <Title headingLevel="h4" size="md">
              Example Conversation Approaches
            </Title>
            <div
              style={{
                backgroundColor: "#f6f8fa",
                padding: "16px",
                borderRadius: "6px",
                marginTop: "16px",
              }}
            >
              <p>
                <strong>For Containerized Installation:</strong> "I want to
                install AAP 2.4 using containers on 3 RHEL 9 servers. I need one
                controller and two execution nodes."
              </p>
              <p>
                <strong>For RPM Installation:</strong> "Help me create an
                inventory for RPM installation with HA controllers and an
                external PostgreSQL database."
              </p>
            </div>
            <br />
            <Title headingLevel="h4" size="md">
              Best Practices for Optimal Results
            </Title>
            <p>
              To get the most accurate and useful inventory files, be as
              specific as possible when describing your infrastructure. Provide
              exact server details, IP addresses, and hostnames rather than
              vague descriptions. Don't hesitate to ask follow-up questions if
              something isn't clear—the assistant can clarify configuration
              options and explain the reasoning behind recommendations. Always
              ask the chatbot to validate your setup and explain why certain
              configurations are recommended for your specific use case.
              Consider starting with a simple setup and gradually adding
              complexity as you become more comfortable with the process.
            </p>
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
