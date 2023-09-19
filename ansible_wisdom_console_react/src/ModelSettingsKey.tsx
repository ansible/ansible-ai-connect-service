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
                }
                if (error.response?.status === 500) {
                    setKeyError({inError: true, message: error.response.data});
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
            <PageSection variant={PageSectionVariants.light} isWidthLimited>
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
            <PageSection>
                <Panel variant={"bordered"}>
                    <PanelMain>
                        <PanelMainBody>
                            <Stack hasGutter={true}>
                                {isKeyInvalid && (
                                    <StackItem>
                                        <Alert variant="warning" title={t("KeyInvalidAlert")}/>
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
                                    />
                                </StackItem>
                                <StackItem>
                                    <Split hasGutter={true}>
                                        <SplitItem>
                                            <Button
                                                variant={"primary"}
                                                icon={<CheckCircleIcon/>}
                                                onClick={() => save(value)}
                                                isDisabled={isSaveDisabled}>
                                                {t("Save")}
                                            </Button>
                                        </SplitItem>
                                        <SplitItem>
                                            <Button variant={"secondary"} onClick={cancel} isDisabled={isSaving}>{t("Cancel")}</Button>
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
