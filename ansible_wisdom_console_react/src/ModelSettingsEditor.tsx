import React, {useMemo, useState} from 'react';
import {
    Alert,
    Breadcrumb,
    BreadcrumbItem,
    Button,
    Icon,
    PageSection,
    PageSectionVariants,
    Panel,
    PanelMain,
    PanelMainBody,
    Split,
    SplitItem,
    Stack,
    StackItem,
    Text,
    TextContent,
    Tooltip
} from "@patternfly/react-core";
import {useTranslation} from "react-i18next";
import {CheckCircleIcon, OutlinedQuestionCircleIcon} from "@patternfly/react-icons";
import './ModelSettings.css';
import {ErrorModal, HasError, NO_ERROR} from "./ErrorModal";
import {BusyButton} from "./BusyButton";
import {SingleInlineEdit} from "./SingleInlineEdit";

interface ModelSettingsEditorCaptionIds {

    readonly errorModalCaption: string;
    readonly invalidAlertCaption: string;
    readonly setValueTitle: string;
    readonly updateValueTitle: string;
    readonly fieldCaption: string;
    readonly fieldCaptionTooltip: string;
    readonly fieldInputCaption: string;
    readonly fieldInputPlaceholder: string;

}

interface ModelSettingsEditorProps {

    readonly hasValue: boolean;
    readonly isSaving: boolean;
    readonly isValueInvalid: boolean;
    readonly clearInvalidState: () => void;
    readonly errorState: HasError;
    readonly setErrorState: (state: HasError) => void;
    readonly save: (value: string) => void;
    readonly cancel: () => void;
    readonly captions: ModelSettingsEditorCaptionIds
}

export const ModelSettingsEditor = (props: ModelSettingsEditorProps) => {
    const {t} = useTranslation();
    const {
        hasValue,
        isSaving,
        isValueInvalid,
        clearInvalidState,
        errorState,
        setErrorState,
        save,
        cancel,
        captions
    } = props;

    const {
        errorModalCaption,
        invalidAlertCaption,
        setValueTitle,
        updateValueTitle,
        fieldCaption,
        fieldCaptionTooltip,
        fieldInputCaption,
        fieldInputPlaceholder
    } = captions;

    const [value, setValue] = useState<string>("");
    const isSaveDisabled: boolean = useMemo(() => value?.trim().length === 0 || isSaving, [value, isSaving]);

    return (
        <>
            <ErrorModal
                caption={t(errorModalCaption)}
                hasError={errorState}
                close={() => setErrorState(NO_ERROR)}
            />
            <PageSection
                variant={PageSectionVariants.light}
                isWidthLimited
                data-testid={"model-settings-editor__bread-crumbs"}
            >
                <Stack hasGutter={true}>
                    <StackItem>
                        <Breadcrumb>
                            <BreadcrumbItem to="/console/admin/settings">{t("ModelSettings")}</BreadcrumbItem>
                            <BreadcrumbItem isActive>{hasValue ? t(updateValueTitle) : t(setValueTitle)}</BreadcrumbItem>
                        </Breadcrumb>
                    </StackItem>
                    <StackItem>
                        <TextContent>
                            {!hasValue && (
                                <Text component="h1">{t(setValueTitle)}</Text>
                            )}
                            {hasValue && (
                                <Text component="h1">{t(updateValueTitle)}</Text>
                            )}
                        </TextContent>
                    </StackItem>
                </Stack>
            </PageSection>
            <PageSection data-testid={"model-settings-editor__editor"}>
                <Panel variant={"bordered"}>
                    <PanelMain>
                        <PanelMainBody>
                            <Stack hasGutter={true}>
                                {isValueInvalid && (
                                    <StackItem>
                                        <Alert
                                            variant="warning"
                                            title={t(invalidAlertCaption)}
                                            data-testid={"model-settings-editor__alert-invalid"}
                                        />
                                    </StackItem>
                                )}
                                <StackItem>
                                    <TextContent>
                                        <Text component={"h3"}>
                                            {t(fieldCaption)}
                                            <Tooltip aria="none" aria-live="polite" content={t(fieldCaptionTooltip)}>
                                                <Icon>
                                                    <OutlinedQuestionCircleIcon className={"Info-icon"}/>
                                                </Icon>
                                            </Tooltip>
                                        </Text>
                                    </TextContent>
                                </StackItem>
                                <StackItem>
                                    <SingleInlineEdit
                                        value={value}
                                        onChange={(value) => {
                                            setValue(value);
                                            clearInvalidState();
                                        }}
                                        aria-label={t(fieldInputCaption)}
                                        placeholder={t(fieldInputPlaceholder)}
                                        isDisabled={isSaving}
                                    />
                                </StackItem>
                                <StackItem>
                                    <Split hasGutter={true}>
                                        <SplitItem>
                                            <BusyButton
                                                variant={"primary"}
                                                icon={<CheckCircleIcon/>}
                                                onClick={() => save(value)}
                                                isBusy={isSaving}
                                                isDisabled={isSaveDisabled}
                                                data-testid={"model-settings-editor__save-button"}
                                            >
                                                {t("Save")}
                                            </BusyButton>
                                        </SplitItem>
                                        <SplitItem>
                                            <Button
                                                variant={"secondary"}
                                                onClick={cancel}
                                                isDisabled={isSaving}
                                                data-testid={"model-settings-editor__cancel-button"}
                                            >
                                                {t("Cancel")}
                                            </Button>
                                        </SplitItem>
                                    </Split>
                                </StackItem>
                            </Stack>
                        </PanelMainBody>
                    </PanelMain>
                </Panel>
            </PageSection>
        </>
    )
}
