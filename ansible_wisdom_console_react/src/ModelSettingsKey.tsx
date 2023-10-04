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
import {WcaKey, WcaKeyRequest} from "./api/types";
import {saveWcaKey} from "./api/api";
import {ErrorModal, HasError, NO_ERROR} from "./ErrorModal";
import {DELAY} from "./api/globals";
import {BusyButton} from "./BusyButton";

interface ModelSettingsKeyProps {
    wcaKey: WcaKey | undefined;
    cancel: () => void;
    reload: () => void;
}

export const ModelSettingsKey = (props: ModelSettingsKeyProps) => {
    const {t} = useTranslation();
    const {wcaKey, cancel, reload} = props;

    const [value, setValue] = useState<string>("");
    const [isSaving, setSaving] = useState<boolean>(false);
    const isSaveDisabled: boolean = useMemo(() => value?.trim().length === 0 || isSaving, [value, isSaving]);
    const hasWcaKey = useMemo(() => wcaKey !== undefined, [wcaKey]);

    const [isKeyInvalid, setIsKeyInvalid] = useState<boolean>(false);
    const [keyError, setKeyError] = useState<HasError>(NO_ERROR);

    const save = useCallback((value: string) => {
        const timeoutId = setTimeout(() => setSaving(true), DELAY);
        const wcaKey: WcaKeyRequest = {key: value};
        saveWcaKey(wcaKey)
            .then((_) => {
                reload();
            })
            .catch((error) => {
                if (error.response?.status === 400) {
                    setIsKeyInvalid(true);
                } else if (error.response?.status === 500) {
                    setKeyError({inError: true, message: error.response.data});
                } else {
                    setKeyError({inError: true, message: error.message});
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
                message={t("KeyError")}
                hasError={keyError}
                close={() => setKeyError(NO_ERROR)}
            />
            <PageSection
                variant={PageSectionVariants.light}
                isWidthLimited
                data-testid={"model-settings-key__bread-crumbs"}
            >
                <Stack hasGutter={true}>
                    <StackItem>
                        <Breadcrumb>
                            <BreadcrumbItem to="/console/admin/settings">{t("ModelSettings")}</BreadcrumbItem>
                            <BreadcrumbItem isActive>{t("AddKeyTitle")}</BreadcrumbItem>
                        </Breadcrumb>
                    </StackItem>
                    <StackItem>
                        <TextContent>
                            {!hasWcaKey && (
                                <Text component="h1">{t("AddKeyTitle")}</Text>
                            )}
                            {hasWcaKey && (
                                <Text component="h1">{t("UpdateKeyTitle")}</Text>
                            )}
                        </TextContent>
                    </StackItem>
                </Stack>
            </PageSection>
            <PageSection data-testid={"model-settings-key__editor"}>
                <Panel variant={"bordered"}>
                    <PanelMain>
                        <PanelMainBody>
                            <Stack hasGutter={true}>
                                {isKeyInvalid && (
                                    <StackItem>
                                        <Alert
                                            variant="warning"
                                            title={t("KeyInvalidAlert")}
                                            data-testid={"model-settings-key__alert-key-invalid"}
                                        />
                                    </StackItem>
                                )}
                                <StackItem>
                                    <TextContent>
                                        <Text component={"h3"}>
                                            {t("APIKey")}
                                            <Tooltip aria="none" aria-live="polite" content={t("APIKeyTooltip")}>
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
                                        onChange={(value) => {
                                            setValue(value);
                                            setIsKeyInvalid(false);
                                        }}
                                        aria-label={t("AddKey")}
                                        placeholder={t("PlaceholderKey")}
                                        isDisabled={isSaving}
                                        data-testid={"model-settings-key__key_textbox"}
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
                                                data-testid={"model-settings-key__save-button"}
                                            >
                                                {t("Save")}
                                            </BusyButton>
                                        </SplitItem>
                                        <SplitItem>
                                            <Button
                                                variant={"secondary"}
                                                onClick={cancel}
                                                isDisabled={isSaving}
                                                data-testid={"model-settings-key__cancel-button"}
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
