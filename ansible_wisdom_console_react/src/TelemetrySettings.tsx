import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {Checkbox, Icon, Page, PageSection, PageSectionVariants, Panel, PanelMain, PanelMainBody, Skeleton, Stack, StackItem, Text, TextContent, Tooltip} from "@patternfly/react-core";
import './ModelSettings.css';
import {Success, Telemetry, TelemetryRequest, TelemetryResponse} from "./api/types";
import {OutlinedQuestionCircleIcon} from "@patternfly/react-icons";
import {useTranslation} from "react-i18next";
import {DELAY} from "./api/globals";
import {saveTelemetrySettings} from "./api/api";
import {ErrorModal, HasError, NO_ERROR} from "./ErrorModal";
import {useTelemetry} from "./hooks/useTelemetryAPI";

export function TelemetrySettings() {
    const {t} = useTranslation();

    const [telemetry, setTelemetry] = useState<Telemetry>({status: "NOT_ASKED"});
    const _telemetry = useTelemetry();

    const [saving, setSaving] = useState<boolean>(false);
    const [telemetrySettingsError, setTelemetrySettingsError] = useState<HasError>(NO_ERROR);
    const isTelemetryLoading: boolean = useMemo(() => telemetry.status === "NOT_ASKED" || telemetry.status === "LOADING", [telemetry]);
    const isTelemetryFound: boolean = useMemo(() => telemetry.status === "SUCCESS", [telemetry]);

    useEffect(() => {
        setTelemetry(_telemetry);
    }, [_telemetry]);

    const save = useCallback((optOut: boolean) => {
        const timeoutId = setTimeout(() => setSaving(true), DELAY);
        const telemetryRequest: TelemetryRequest = {optOut: optOut};
        saveTelemetrySettings(telemetryRequest)
            .then((_) => {
                setSaving(false)
                setTelemetry({status: "SUCCESS", data: telemetryRequest});
            })
            .catch((error) => {
                setTelemetrySettingsError({
                    inError: true,
                    message: error.message,
                    detail: error.response?.data?.detail
                })
            })
            .finally(() => {
                setSaving(false);
                clearTimeout(timeoutId);
            });
    }, []);

    return (
        <Page>
            <ErrorModal
                caption={t("TelemetryError")}
                hasError={telemetrySettingsError}
                close={() => setTelemetrySettingsError(NO_ERROR)}
            />
            <PageSection variant={PageSectionVariants.light} isWidthLimited>
                <TextContent>
                    <Text component="h1">{t("TelemetrySettings")}</Text>
                </TextContent>
            </PageSection>
            <PageSection data-testid={"telemetry-settings"}>
                <Panel variant={"bordered"}>
                    <PanelMain>
                        <PanelMainBody>
                            <Stack hasGutter={true}>
                                <StackItem>
                                    <TextContent>
                                        <Text component={"h3"}>
                                            {t("TelemetryOptOut")}
                                            <Tooltip aria="none" aria-live="polite" content={t("TelemetryOptOutTooltip")}>
                                                <Icon>
                                                    <OutlinedQuestionCircleIcon className={"Info-icon"}/>
                                                </Icon>
                                            </Tooltip>
                                        </Text>
                                    </TextContent>
                                </StackItem>
                                <StackItem>
                                    {isTelemetryLoading && (
                                        <div className={"Loading"} data-testid={"telemetry-settings__telemetry-loading"}>
                                            <Skeleton height="100%" screenreaderText={t("Loading")}/>
                                        </div>
                                    )}
                                    {isTelemetryFound && (
                                        <>
                                            {/*This is a safe cast as 'isTelemetryFound' is true*/}
                                            <Checkbox
                                                label={t("TelemetryOptOutDescription")}
                                                isChecked={(telemetry as Success<TelemetryResponse>).data.optOut}
                                                onChange={save}
                                                isDisabled={saving}
                                                id="optOut"
                                                name="outOut"
                                                data-testid={"telemetry-settings__opt_out_checkbox"}
                                            />
                                        </>
                                    )}
                                </StackItem>
                            </Stack>
                        </PanelMainBody>
                    </PanelMain>
                </Panel>
            </PageSection>
        </Page>
    )
}
