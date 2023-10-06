import React from 'react';
import {
    Icon,
    PageSection,
    PageSectionVariants,
    Panel,
    PanelMain,
    PanelMainBody,
    Stack,
    StackItem,
    Text,
    TextContent,
    TextVariants
} from "@patternfly/react-core";
import {useTranslation} from "react-i18next";
import './ModelSettings.css';
import {ExclamationCircleIcon} from "@patternfly/react-icons";

export const UserNotAllowed = () => {
    const {t} = useTranslation();

    return (
        <>
            <PageSection variant={PageSectionVariants.light} isWidthLimited>
                <TextContent>
                    <Text component={TextVariants.h1}>{t("ModelSettings")}</Text>
                </TextContent>
            </PageSection>
            <PageSection>
                <Panel variant={"bordered"}>
                    <PanelMain>
                        <PanelMainBody>
                            <Stack hasGutter={true}>
                                <StackItem>
                                    <Icon size="xl" status="danger">
                                        <ExclamationCircleIcon/>
                                    </Icon>
                                </StackItem>
                                <StackItem>
                                    <Text component={TextVariants.h1}>{t('noPagePermissions')}</Text>
                                </StackItem>
                                <StackItem>
                                    <Text component={TextVariants.h3}>{t('contactOrgText')}</Text>
                                </StackItem>
                            </Stack>
                        </PanelMainBody>
                    </PanelMain>
                </Panel>
            </PageSection>
        </>
    )
}
