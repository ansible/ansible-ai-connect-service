import React from "react";
import {
  Bullseye,
  EmptyState,
  EmptyStateBody,
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
  TextVariants,
} from "@patternfly/react-core";
import { ExclamationCircleIcon } from "@patternfly/react-icons";
import { useTranslation } from "react-i18next";

interface PageDeniedProps {
  readonly titleKey: string;
  readonly captionKey: string;
}

export function PageDenied(props: PageDeniedProps) {
  const { t } = useTranslation();
  const { titleKey, captionKey } = props;

  return (
    <>
      <PageSection variant={PageSectionVariants.light} isWidthLimited>
        <TextContent>
          <Text component="h1">{t("ModelSettings")}</Text>
        </TextContent>
      </PageSection>
      <PageSection>
        <Panel variant={"bordered"} style={{ height: "100%" }}>
          <PanelMain style={{ height: "100%" }}>
            <PanelMainBody style={{ height: "100%" }}>
              <Bullseye>
                <EmptyState>
                  <EmptyStateBody>
                    <Stack hasGutter={true} style={{ alignItems: "center" }}>
                      <StackItem>
                        <Icon size="xl" status="danger">
                          <ExclamationCircleIcon />
                        </Icon>
                      </StackItem>
                      <StackItem>
                        <TextContent data-testid={"page-denied__title"}>
                          <Text component={TextVariants.h1}>{t(titleKey)}</Text>
                        </TextContent>
                      </StackItem>
                      <StackItem>
                        <TextContent data-testid={"page-denied__caption"}>
                          <Text component={TextVariants.p}>
                            {t(captionKey)}
                          </Text>
                        </TextContent>
                      </StackItem>
                    </Stack>
                  </EmptyStateBody>
                </EmptyState>
              </Bullseye>
            </PanelMainBody>
          </PanelMain>
        </Panel>
      </PageSection>
    </>
  );
}
