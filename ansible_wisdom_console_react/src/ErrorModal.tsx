import React, {useMemo} from 'react';
import {Button, ExpandableSection, Modal, ModalVariant} from '@patternfly/react-core';
import {useTranslation} from "react-i18next";
import './ErrorModal.css';

interface ErrorModalProps {
    message: string,
    hasError: HasError,
    close: () => void
}

export type HasError = { inError: false } | { inError: true, message: string };
export const NO_ERROR: HasError = {inError: false};

export const ErrorModal = (props: ErrorModalProps) => {
    const {t} = useTranslation();
    const {message, hasError, close} = props;
    const _error = useMemo<string>(() => {
        if ('message' in hasError) {
            return hasError.message;
        }
        return "";
    }, [hasError]);

    return (
        <Modal
            className={"Error-Modal"}
            variant={ModalVariant.small}
            title={t("Error")}
            description={message}
            titleIconVariant="danger"
            isOpen={hasError.inError}
            onClose={close}
            actions={[
                <Button key="confirm" variant="secondary" onClick={close}>
                    {t("Close")}
                </Button>,
            ]}
        >
            <ExpandableSection className={"Error-Modal-Detail"} toggleText={t("ErrorDetails")}>
                <pre>{_error}</pre>
            </ExpandableSection>
        </Modal>
    );
};
