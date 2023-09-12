import React from 'react';
import {Page, PageSection, PageSectionVariants, Panel, PanelMain, PanelMainBody, Stack, StackItem, Text, TextContent} from "@patternfly/react-core";
import {useTranslation} from "react-i18next";

export function Overview() {
    const {t} = useTranslation()

    return (
        <Page>
            <PageSection variant={PageSectionVariants.light} isWidthLimited>
                <TextContent>
                    <Text component="h1">{t("Overview")}</Text>
                </TextContent>
            </PageSection>
            <PageSection>
                <Panel variant={"bordered"}>
                    <PanelMain>
                        <PanelMainBody>
                            <Stack hasGutter={true}>
                                <StackItem>
                                    <TextContent>
                                        <Text component={"h6"}>{t("OverviewDescription")}</Text>
                                    </TextContent>
                                </StackItem>
                            </Stack>
                        </PanelMainBody>
                    </PanelMain>
                </Panel>
            </PageSection>
        </Page>
    )
}
