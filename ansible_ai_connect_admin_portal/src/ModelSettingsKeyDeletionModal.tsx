import { useTranslation } from "react-i18next";
import { Button, Modal, ModalVariant, Text } from "@patternfly/react-core";
import { useState } from "react";
import { DELAY } from "./api/globals";
import { APIException } from "./api/types";
import { deleteWcaKey } from "./api/api";
import { AxiosError } from "axios";
import { HasError, NO_ERROR } from "./ErrorModal";
import { BusyButton } from "./BusyButton";

interface ModelSettingsKeyDeletionModalProps {
  readonly isModalOpen: boolean;
  readonly setIsModalOpen: (isOpen: boolean) => void;
  readonly handleModalToggle: () => void;
  readonly reloadParent: () => void;
}

export const ModelSettingsKeyDeletionModal = (
  props: ModelSettingsKeyDeletionModalProps,
) => {
  const { t } = useTranslation();
  const { isModalOpen, setIsModalOpen, handleModalToggle, reloadParent } =
    props;
  const [isDeleting, setDeleting] = useState<boolean>(false);
  const [keyError, setKeyError] = useState<HasError>(NO_ERROR);

  const deleteKey = () => {
    const timeoutId = setTimeout(() => setDeleting(true), DELAY);
    deleteWcaKey()
      .then((_) => {
        reloadParent();
        handleCancel();
      })
      .catch((error: AxiosError<APIException, any>) => {
        setKeyError({
          inError: true,
          message: error.message,
          detail: error.response?.data?.detail ?? "",
        });
      })
      .finally(() => {
        setDeleting(false);
        clearTimeout(timeoutId);
      });
  };

  const handleCancel = () => {
    setKeyError({
      inError: false,
    });
    setIsModalOpen(false);
  };

  return (
    <Modal
      variant={ModalVariant.small}
      title="Delete Confirmation"
      isOpen={isModalOpen}
      onClose={handleModalToggle}
      actions={[
        <BusyButton
          key="delete"
          variant="danger"
          onClick={deleteKey}
          isBusy={isDeleting}
        >
          {t("Delete")}
        </BusyButton>,
        <Button key="cancel" variant="link" onClick={handleCancel}>
          {t("Cancel")}
        </Button>,
      ]}
    >
      {t("APIKeyDeletionConfirmation")}
      {keyError.inError && (
        <Text component="p" style={{ color: "red" }}>
          {t("KeyDeletionError")}: {keyError.message}
        </Text>
      )}
    </Modal>
  );
};
