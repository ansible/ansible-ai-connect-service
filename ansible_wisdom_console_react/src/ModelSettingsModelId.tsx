import React, {useCallback, useMemo, useState} from 'react';
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
    TextInput,
    Tooltip
} from "@patternfly/react-core";
import {useTranslation} from "react-i18next";
import {CheckCircleIcon, OutlinedQuestionCircleIcon} from "@patternfly/react-icons";
import './ModelSettings.css';
import {WcaModelId, WcaModelIdRequest} from "./api/types";
import {saveWcaModelId} from "./api/api";
import {ErrorModal, HasError, NO_ERROR} from "./ErrorModal";
import {DELAY} from "./api/globals";
import {BusyButton} from "./BusyButton";

interface ModelSettingsModelIdProps {
    wcaModelId: WcaModelId;
    cancel: () => void;
    reload: () => void;
}

export const ModelSettingsModelId = (props: ModelSettingsModelIdProps) => {
    const {t} = useTranslation();
    const {wcaModelId, cancel, reload} = props;

    const [value, setValue] = useState<string>("");
    const [isSaving, setSaving] = useState(false);
    const isSaveDisabled: boolean = useMemo(() => value?.trim().length === 0 || isSaving, [value, isSaving]);
    const hasWcaModelId = useMemo(() => wcaModelId !== undefined, [wcaModelId]);

    const [isModelIdInvalid, setIsModelIdInvalid] = useState<boolean>(false);
    const [modelIdError, setModelIdError] = useState<HasError>(NO_ERROR);

    const save = useCallback((value: string) => {
        const timeoutId = setTimeout(() => setSaving(true), DELAY);
        const wcaModelId: WcaModelIdRequest = {model_id: value};
        saveWcaModelId(wcaModelId)
            .then((_) => {
                reload();
            })
            .catch((error) => {
                if (error.response?.status === 400) {
                    setIsModelIdInvalid(true);
                } else if (error.response?.status === 500) {
                    setModelIdError({inError: true, message: error.response.data});
                } else {
                    setModelIdError({inError: true, message: error.message});
                }
            })
            .finally(() => {
                setSaving(false);
                clearTimeout(timeoutId);
            });
    }, [reload]);

    return (
        <>
            <ErrorModal
                message={t("ModelIdError")}
                hasError={modelIdError}
                close={() => setModelIdError(NO_ERROR)}
            />
            <PageSection
                variant={PageSectionVariants.light}
                isWidthLimited
                data-testid={"model-settings-model-id__bread-crumbs"}
            >
                <Stack hasGutter={true}>
                    <StackItem>
                        <Breadcrumb>
                            <BreadcrumbItem to="/console/admin/settings">{t("ModelSettings")}</BreadcrumbItem>
                            <BreadcrumbItem isActive>{t("AddModelIdTitle")}</BreadcrumbItem>
                        </Breadcrumb>
                    </StackItem>
                    <StackItem>
                        <TextContent>
                            {!hasWcaModelId && (
                                <Text component="h1">{t("AddModelIdTitle")}</Text>
                            )}
                            {hasWcaModelId && (
                                <Text component="h1">{t("UpdateModelIdTitle")}</Text>
                            )}
                            <Text component="h1">{t("")}</Text>
                        </TextContent>
                    </StackItem>
                </Stack>
            </PageSection>
            <PageSection data-testid={"model-settings-model-id__editor"}>
                <Panel variant={"bordered"}>
                    <PanelMain>
                        <PanelMainBody>
                            <Stack hasGutter={true}>
                                {isModelIdInvalid && (
                                    <StackItem>
                                        <Alert
                                            variant="warning"
                                            title={t("ModelIdInvalidAlert")}
                                            data-testid={"model-settings-model-id__alert-model-id-invalid"}
                                        />
                                    </StackItem>
                                )}
                                <StackItem>
                                    <TextContent>
                                        <Text component={"h3"}>
                                            {t("ModelId")}
                                            <Tooltip aria="none" aria-live="polite" content={t("ModelIdTooltip")}>
                                                <Icon>
                                                    <OutlinedQuestionCircleIcon className={"Info-icon"}/>
                                                </Icon>
                                            </Tooltip>
                                        </Text>
                                    </TextContent>
                                </StackItem>
                                <StackItem>
                                    <TextInput
                                        value={value}
                                        type="text"
                                        onChange={(value) => setValue(value)}
                                        aria-label={t("AddKey")}
                                        placeholder={t("PlaceholderModelId")}
                                        isDisabled={isSaving}
                                        data-testid={"model-settings-model-id__model-id_textbox"}
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
                                                data-testid={"model-settings-model-id__save-button"}
                                            >
                                                {t("Save")}
                                            </BusyButton>
                                        </SplitItem>
                                        <SplitItem>
                                            <Button
                                                variant={"secondary"}
                                                onClick={cancel}
                                                isDisabled={isSaving}
                                                data-testid={"model-settings-model-id__cancel-button"}
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
