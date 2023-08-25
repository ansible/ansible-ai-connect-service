import React, {useCallback, useMemo, useRef, useState} from 'react';
import {Alert, Button, Icon, PageSection, PageSectionVariants, Panel, PanelMain, PanelMainBody, Skeleton, Split, SplitItem, Stack, StackItem, Text, TextContent, Tooltip} from "@patternfly/react-core";
import {useTranslation} from "react-i18next";
import {CheckCircleIcon, OutlinedQuestionCircleIcon, PlusCircleIcon} from "@patternfly/react-icons";
import './ModelSettings.css';
import {Success, WcaKey, WcaKeyResponse, WcaModelId, WcaModelIdResponse} from "./api/types";
import {testWcaKey, testWcaModelId} from "./api/api";
import {ErrorModal, HasError, NO_ERROR} from "./ErrorModal";
import {Alerts, AlertsHandle} from "./Alerts";

interface ModelSettingsOverviewProps {
    wcaKey: WcaKey;
    wcaModelId: WcaModelId;
    setModeToKey: () => void
    setModeToModelId: () => void
}

export const ModelSettingsOverview = (props: ModelSettingsOverviewProps) => {
    const {t} = useTranslation();
    const {wcaKey, wcaModelId, setModeToKey, setModeToModelId} = props;

    const isWcaKeyLoading: boolean = useMemo(() => wcaKey.status === "NOT_ASKED" || wcaKey.status === "LOADING", [wcaKey]);
    const isWcaKeyNotFound: boolean = useMemo(() => wcaKey.status === "SUCCESS_NOT_FOUND", [wcaKey]);
    const isWcaKeyFound: boolean = useMemo(() => wcaKey.status === "SUCCESS", [wcaKey]);

    const isWcaModelIdLoading: boolean = useMemo(() => wcaModelId.status === "NOT_ASKED" || wcaModelId.status === "LOADING", [wcaModelId]);
    const isWcaModelIdNotFound: boolean = useMemo(() => wcaModelId.status === "SUCCESS_NOT_FOUND", [wcaModelId]);
    const isWcaModelIdFound: boolean = useMemo(() => wcaModelId.status === "SUCCESS", [wcaModelId]);

    const [isValidatingKey, setIsValidatingKey] = useState<boolean>(false);
    const [isKeyInvalid, setIsKeyInvalid] = useState<boolean>(false);
    const [keyError, setKeyError] = useState<HasError>(NO_ERROR);

    const [isValidatingModelId, setIsValidatingModelId] = useState<boolean>(false);
    const [isModelIdInvalid, setIsModelIdInvalid] = useState<boolean>(false);
    const [modelIdError, setModelIdError] = useState<HasError>(NO_ERROR);

    const alertsRef = useRef<AlertsHandle>(null);

    const testKey = useCallback(() => {
        setIsValidatingKey(true);
        testWcaKey()
            .then((_) => {
                alertsRef.current?.addAlert(t("KeyValidationSuccess"));
            })
            .catch((error) => {
                if (error.response.status === 400) {
                    setIsKeyInvalid(true);
                }
                if (error.response.status === 500) {
                    setKeyError({inError: true, message: error.response.data});
                }
            })
            .finally(() => {
                setIsValidatingKey(false);
            });
    }, []);

    const testModelId = () => {
        setIsValidatingModelId(true);
        testWcaModelId()
            .then((_) => {
                alertsRef.current?.addAlert(t("ModelIdValidationSuccess"));
            })
            .catch((error) => {
                if (error.response.status === 400) {
                    setIsModelIdInvalid(true);
                }
                if (error.response.status === 500) {
                    setModelIdError({inError: true, message: error.response.data});
                }
            })
            .finally(() => {
                setIsValidatingModelId(false);
            });
    };

    return (
        <>
            <ErrorModal
                message={t("KeyValidationError")}
                hasError={keyError}
                close={() => setKeyError(NO_ERROR)}
            />
            <ErrorModal
                message={t("ModelIdValidationError")}
                hasError={modelIdError}
                close={() => setModelIdError(NO_ERROR)}
            />
            <PageSection variant={PageSectionVariants.light} isWidthLimited>
                <Alerts ref={alertsRef}/>
                <TextContent>
                    <Text component="h1">{t("ModelSettings")}</Text>
                </TextContent>
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
                                        <Text component={"p"}>{t("APIKeyDescription")}</Text>
                                    </TextContent>
                                </StackItem>
                                <StackItem>
                                    {isWcaKeyLoading && (
                                        <div className={"Loading"}>
                                            <Skeleton height="100%" screenreaderText={t("Loading")}/>
                                        </div>
                                    )}
                                    {isWcaKeyNotFound && (
                                        <TextContent>
                                            <Text component={"p"}>{t("NoAPIKey")}</Text>
                                        </TextContent>
                                    )}
                                    {isWcaKeyFound && (
                                        <>
                                            <TextContent>
                                                <Text component={"h3"}>{t("APIKey")}</Text>
                                            </TextContent>
                                            <Split>
                                                <SplitItem isFilled={true}>
                                                    <TextContent>
                                                        <Text component={"p"} className={"Secret-value"}>{t("SecretValue")}</Text>
                                                    </TextContent>
                                                </SplitItem>
                                                <SplitItem>
                                                    <Button
                                                        variant={"tertiary"}
                                                        isSmall={true}
                                                        isDisabled={isValidatingKey}
                                                        onClick={testKey}>
                                                        {t("Test")}
                                                    </Button>
                                                </SplitItem>
                                            </Split>
                                        </>
                                    )}
                                </StackItem>
                                <StackItem>
                                    {isWcaKeyNotFound && (
                                        <Button variant={"primary"} icon={<PlusCircleIcon/>} onClick={setModeToKey}>{t("AddAPIKey")}</Button>
                                    )}
                                    {isWcaKeyFound && (
                                        <Button
                                            variant={"primary"}
                                            icon={<CheckCircleIcon/>}
                                            isDisabled={isValidatingKey}
                                            onClick={setModeToKey}>
                                            {t("UpdateAPIKey")}
                                        </Button>
                                    )}
                                </StackItem>
                                {isWcaKeyFound && (
                                    <>
                                        <StackItem>
                                            <TextContent>
                                                <Text component={"h3"}>{t("LastUpdated")}</Text>
                                            </TextContent>
                                        </StackItem>
                                        <StackItem>
                                            <TextContent>
                                                {/*This is a safe cast as 'isWcaKeyFound' is true*/}
                                                <Text component={"p"}>{(wcaKey as Success<WcaKeyResponse>).data.lastUpdate.toLocaleString()}</Text>
                                            </TextContent>
                                        </StackItem>
                                    </>
                                )}
                            </Stack>
                        </PanelMainBody>
                    </PanelMain>
                </Panel>
            </PageSection>
            <PageSection>
                <Panel variant={"bordered"}>
                    <PanelMain>
                        <PanelMainBody>
                            <Stack hasGutter={true}>
                                {isModelIdInvalid && (
                                    <StackItem>
                                        <Alert variant="warning" title={t("ModelIdInvalidAlert")}/>
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
                                        <Text component={"p"}>{t("ModelIdDescription")}</Text>
                                    </TextContent>
                                </StackItem>
                                <StackItem>
                                    <StackItem>
                                        {isWcaModelIdNotFound && (
                                            <TextContent>
                                                <Text component={"p"}>{t("NoModelId")}</Text>
                                            </TextContent>
                                        )}
                                        {isWcaModelIdFound && (
                                            <>
                                                <TextContent>
                                                    <Text component={"h3"}>{t("ModelId")}</Text>
                                                </TextContent>
                                                <Split>
                                                    <SplitItem isFilled={true}>
                                                        <TextContent>
                                                            {/*This is a safe cast as 'isWcaModelIdFound' is true*/}
                                                            <Text
                                                                component={"p"}
                                                                className={"Secret-value"}>
                                                                {(wcaModelId as Success<WcaModelIdResponse>).data.model_id}
                                                            </Text>
                                                        </TextContent>
                                                    </SplitItem>
                                                    <SplitItem>
                                                        <Button
                                                            variant={"tertiary"}
                                                            isSmall={true}
                                                            isDisabled={isValidatingModelId}
                                                            onClick={testModelId}>
                                                            {t("Test")}
                                                        </Button>
                                                    </SplitItem>
                                                </Split>
                                            </>
                                        )}
                                    </StackItem>
                                </StackItem>
                                <StackItem>
                                    {isWcaModelIdLoading && (
                                        <div className={"Loading"}>
                                            <Skeleton height="100%" screenreaderText={t("Loading")}/>
                                        </div>
                                    )}
                                    {isWcaModelIdNotFound && (
                                        <Button variant={"primary"} icon={<PlusCircleIcon/>} onClick={setModeToModelId}>{t("AddModelId")}</Button>
                                    )}
                                    {isWcaModelIdFound && (
                                        <Button
                                            variant={"primary"}
                                            icon={<CheckCircleIcon/>}
                                            isDisabled={isValidatingModelId}
                                            onClick={setModeToModelId}>
                                            {t("UpdateModelId")}
                                        </Button>
                                    )}
                                </StackItem>
                                {isWcaModelIdFound && (
                                    <>
                                        <StackItem>
                                            <TextContent>
                                                <Text component={"h3"}>{t("LastUpdated")}</Text>
                                            </TextContent>
                                        </StackItem>
                                        <StackItem>
                                            <TextContent>
                                                {/*This is a safe cast as 'isWcaModelIdFound' is true*/}
                                                <Text component={"p"}>{(wcaModelId as Success<WcaModelIdResponse>).data.lastUpdate.toLocaleString()}</Text>
                                            </TextContent>
                                        </StackItem>
                                    </>
                                )}
                            </Stack>
                        </PanelMainBody>
                    </PanelMain>
                </Panel>
            </PageSection>
        </>
    )
}
