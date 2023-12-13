import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Button, Icon, Page, PageSection, PageSectionVariants, Panel, PanelMain, PanelMainBody, Radio, Skeleton, Split, SplitItem, Stack, StackItem, Text, TextContent} from "@patternfly/react-core";
import './ModelSettings.css';
import {Success, Telemetry, TelemetryRequest, TelemetryResponse} from "./api/types";
import {CheckCircleIcon, ExternalLinkAltIcon} from "@patternfly/react-icons";
import {useTranslation} from "react-i18next";
import {DELAY} from "./api/globals";
import {saveTelemetrySettings} from "./api/api";
import {ErrorModal, HasError, NO_ERROR} from "./ErrorModal";
import {useTelemetry} from "./hooks/useTelemetryAPI";
import {BusyButton} from "./BusyButton";
import {Alerts, AlertsHandle} from "./Alerts";

export function TelemetrySettings() {
    const {t} = useTranslation();

    const [telemetry, setTelemetry] = useState<Telemetry>({status: "NOT_ASKED"});
    const [telemetryOptOut, setTelemetryOptOut] = useState<boolean>(false);
    const _telemetry = useTelemetry();

    const [saving, setSaving] = useState<boolean>(false);
    const [telemetrySettingsError, setTelemetrySettingsError] = useState<HasError>(NO_ERROR);
    const isTelemetryLoading: boolean = useMemo(() => _telemetry.status === "NOT_ASKED" || _telemetry.status === "LOADING", [_telemetry]);
    const isTelemetryFound: boolean = useMemo(() => _telemetry.status === "SUCCESS", [_telemetry]);

    const alertsRef = useRef<AlertsHandle>(null);

    useEffect(() => {
        setTelemetry(_telemetry);
        if (_telemetry.status === "SUCCESS") {
            const optOut: boolean = (_telemetry as Success<TelemetryResponse>).data.optOut;
            setTelemetryOptOut(optOut);
        }
    }, [_telemetry]);

    const optInOutChanged = useMemo(() => {
        if (telemetry.status === "SUCCESS") {
            return ((telemetry as Success<TelemetryResponse>).data.optOut) !== telemetryOptOut;
        }
        return false;
    }, [telemetry, telemetryOptOut])

    const save = useCallback(() => {
        const timeoutId = setTimeout(() => setSaving(true), DELAY);
        const telemetryRequest: TelemetryRequest = {optOut: telemetryOptOut};
        saveTelemetrySettings(telemetryRequest)
            .then((_) => {
                setSaving(false);
                setTelemetry({status: "SUCCESS", data: telemetryRequest});
                if (telemetryOptOut) {
                    alertsRef.current?.addAlert(t("TelemetryOptOutSaveSuccessAlert"));
                } else {
                    alertsRef.current?.addAlert(t("TelemetryOptInSaveSuccessAlert"));
                }
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
    }, [t, telemetryOptOut]);

    const cancel = useCallback(() => {
        setSaving(false);
        if (telemetry.status === "SUCCESS") {
            const optOut: boolean = (_telemetry as Success<TelemetryResponse>).data.optOut;
            setTelemetryOptOut(optOut);
        }
    }, [_telemetry, telemetry])

    return (
        <Page>
            <ErrorModal
                caption={t("TelemetryError")}
                hasError={telemetrySettingsError}
                close={() => setTelemetrySettingsError(NO_ERROR)}
            />
            <PageSection variant={PageSectionVariants.light} isWidthLimited>
                <TextContent>
                    <Alerts ref={alertsRef}/>
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
                                            {t("TelemetryManageUsage")}
                                        </Text>
                                        <Text component={"p"}>
                                            {t("TelemetryManageUsageDescription")}
                                            <a href={t("TelemetryManageUsageAdminDashboardURL")}>
                                                {t("TelemetryManageUsageAdminDashboardURLText")}
                                            </a>
                                        </Text>
                                        <Text component={"p"}>
                                            <a href={t("TelemetryManageUsageLearnMoreURL")}>
                                                {t("TelemetryManageUsageLearnMoreURLText")}
                                                <Icon size="md">
                                                    <ExternalLinkAltIcon style={{color: "var(--pf-c-content--a--Color)"}}/>
                                                </Icon>
                                            </a>
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
                                        <Stack hasGutter={true}>
                                            <StackItem>
                                                {/*This is a safe cast as 'isTelemetryFound' is true*/}
                                                <Radio
                                                    id="optInRadio"
                                                    name="optInOutRadio"
                                                    label={t("TelemetryOptInLabel")}
                                                    description={t("TelemetryOptInDescription")}
                                                    isChecked={!telemetryOptOut}
                                                    onChange={() => setTelemetryOptOut(false)}
                                                    isDisabled={saving}
                                                    data-testid={"telemetry-settings__opt_in_radiobutton"}
                                                />
                                            </StackItem>
                                            <StackItem>
                                                <Radio
                                                    id="optOutRadio"
                                                    name="optInOutRadio"
                                                    label={t("TelemetryOptOutLabel")}
                                                    description={t("TelemetryOptOutDescription")}
                                                    isChecked={telemetryOptOut}
                                                    onChange={() => setTelemetryOptOut(true)}
                                                    isDisabled={saving}
                                                    data-testid={"telemetry-settings__opt_out_radiobutton"}
                                                />
                                            </StackItem>
                                            <StackItem>
                                                <Split hasGutter={true}>
                                                    <SplitItem>
                                                        <BusyButton
                                                            variant={"primary"}
                                                            icon={<CheckCircleIcon/>}
                                                            onClick={save}
                                                            isBusy={saving}
                                                            isDisabled={saving}
                                                            data-testid={"telemetry-settings__save-button"}
                                                        >
                                                            {t("Save")}
                                                        </BusyButton>
                                                    </SplitItem>
                                                    <SplitItem>
                                                        <Button
                                                            variant={"secondary"}
                                                            onClick={cancel}
                                                            isDisabled={saving || !optInOutChanged}
                                                            data-testid={"telemetry-settings__cancel-button"}
                                                        >
                                                            {t("Cancel")}
                                                        </Button>
                                                    </SplitItem>
                                                </Split>
                                            </StackItem>
                                        </Stack>
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
