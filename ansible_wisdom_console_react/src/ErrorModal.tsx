import React, {useMemo} from 'react';
import {Button, ExpandableSection, Modal, ModalVariant, Text, TextContent} from '@patternfly/react-core';
import {useTranslation} from "react-i18next";
import './ErrorModal.css';

interface ErrorModalProps {
    readonly caption: string,
    readonly  hasError: HasError,
    readonly close: () => void
}

export type HasError = { inError: false } | { inError: true, message: string, detail: string };
export const NO_ERROR: HasError = {inError: false};

export const ErrorModal = (props: ErrorModalProps) => {
    const {t} = useTranslation();
    const {caption, hasError, close} = props;
    const _error = useMemo<string>(() => {
        if ('message' in hasError) {
            return hasError.message;
        }
        return "";
    }, [hasError]);
    const _detail = useMemo<string>(() => {
        if ('detail' in hasError) {
            return hasError.detail;
        }
        return "";
    }, [hasError]);

    return (
        <Modal
            className={"Error-Modal"}
            variant={ModalVariant.small}
            title={t("Error")}
            description={caption}
            titleIconVariant="danger"
            isOpen={hasError.inError}
            onClose={close}
            actions={[
                <Button key="confirm" variant="secondary" onClick={close}>
                    {t("Close")}
                </Button>,
            ]}
        >
            <ExpandableSection toggleText={t("ErrorDetails")} className={"Error-Modal__container"}>
                <TextContent>
                    <Text component={"pre"} className={"Error-Model__detail"}>
                        {_error}
                    </Text>
                    <Text component={"pre"} className={"Error-Model__detail"}>
                        {_detail}
                    </Text>
                </TextContent>
            </ExpandableSection>
        </Modal>
    );
};
