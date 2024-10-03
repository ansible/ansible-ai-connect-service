import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  Alert,
  Button,
  Icon,
  PageSection,
  PageSectionVariants,
  Panel,
  PanelMain,
  PanelMainBody,
  Skeleton,
  Split,
  SplitItem,
  Stack,
  StackItem,
  Text,
  TextContent,
  Tooltip,
} from "@patternfly/react-core";
import { useTranslation } from "react-i18next";
import {
  CheckCircleIcon,
  OutlinedQuestionCircleIcon,
  PlusCircleIcon,
  TrashIcon,
} from "@patternfly/react-icons";
import "./ModelSettings.css";
import {
  APIException,
  Success,
  WcaKey,
  WcaKeyResponse,
  WcaModelId,
  WcaModelIdResponse,
} from "./api/types";
import { DELAY } from "./api/globals";
import { testWcaKey, testWcaModelId } from "./api/api";
import { ErrorModal, HasError, NO_ERROR } from "./ErrorModal";
import { Alerts, AlertsHandle } from "./Alerts";
import { BusyButton } from "./BusyButton";
import { AxiosError } from "axios";
import { ModelSettingsKeyDeletionModal } from "./ModelSettingsKeyDeletionModal";

interface ModelSettingsOverviewProps {
  readonly wcaKey: WcaKey;
  readonly wcaModelId: WcaModelId;
  readonly setModeToKey: () => void;
  readonly setModeToModelId: () => void;
  readonly reload: () => void;
}

export const ModelSettingsOverview = (props: ModelSettingsOverviewProps) => {
  const { t } = useTranslation();
  const { wcaKey, wcaModelId, setModeToKey, setModeToModelId, reload } = props;

  const isWcaKeyLoading: boolean = useMemo(
    () => wcaKey.status === "NOT_ASKED" || wcaKey.status === "LOADING",
    [wcaKey],
  );
  const isWcaKeyNotFound: boolean = useMemo(
    () => wcaKey.status === "SUCCESS_NOT_FOUND",
    [wcaKey],
  );
  const isWcaKeyFound: boolean = useMemo(
    () => wcaKey.status === "SUCCESS",
    [wcaKey],
  );

  const isWcaModelIdLoading: boolean = useMemo(
    () => wcaModelId.status === "NOT_ASKED" || wcaModelId.status === "LOADING",
    [wcaModelId],
  );
  const isWcaModelIdNotFound: boolean = useMemo(
    () => wcaModelId.status === "SUCCESS_NOT_FOUND",
    [wcaModelId],
  );
  const isWcaModelIdFound: boolean = useMemo(
    () => wcaModelId.status === "SUCCESS",
    [wcaModelId],
  );

  const [isValidatingKey, setIsValidatingKey] = useState<boolean>(false);
  const [isKeyInvalid, setIsKeyInvalid] = useState<boolean>(false);
  const [keyError, setKeyError] = useState<HasError>(NO_ERROR);
  const [isDeletionModalOpen, setIsDeletionModalOpen] = useState(false);

  const [isValidatingModelId, setIsValidatingModelId] =
    useState<boolean>(false);
  const [isModelIdInvalid, setIsModelIdInvalid] = useState<boolean>(false);
  const [modelIdError, setModelIdError] = useState<HasError>(NO_ERROR);

  const alertsRef = useRef<AlertsHandle>(null);

  const testKey = useCallback(() => {
    const timeoutId = setTimeout(() => setIsValidatingKey(true), DELAY);
    testWcaKey()
      .then((_) => {
        alertsRef.current?.addAlert(t("KeyValidationSuccess"));
      })
      .catch((error: AxiosError<APIException, any>) => {
        if (error.response?.status === 400) {
          setIsKeyInvalid(true);
        } else {
          setKeyError({
            inError: true,
            message: error.message,
            detail: error.response?.data?.detail ?? "",
          });
        }
      })
      .finally(() => {
        setIsValidatingKey(false);
        clearTimeout(timeoutId);
      });
  }, [t]);

  const testModelId = useCallback(() => {
    const timeoutId = setTimeout(() => setIsValidatingModelId(true), DELAY);
    testWcaModelId()
      .then((_) => {
        alertsRef.current?.addAlert(t("ModelIdValidationSuccess"));
      })
      .catch((error: AxiosError<APIException, any>) => {
        if (error.response?.status === 400) {
          setIsModelIdInvalid(true);
        } else if (
          error.response?.status === 403 &&
          error.response?.data?.code === "permission_denied__user_trial_expired"
        ) {
          setModelIdError({
            inError: true,
            message: t("ModelIdValidationTrialExpired"),
            detail: error.response?.data?.detail ?? "",
          });
        } else {
          setModelIdError({
            inError: true,
            message: error.message,
            detail: error.response?.data?.detail ?? "",
          });
        }
      })
      .finally(() => {
        setIsValidatingModelId(false);
        clearTimeout(timeoutId);
      });
  }, [t]);

  const handleDeletionModalToggle = () => {
    setIsDeletionModalOpen(!isDeletionModalOpen);
  };

  return (
    <>
      <ModelSettingsKeyDeletionModal
        isModalOpen={isDeletionModalOpen}
        setIsModalOpen={setIsDeletionModalOpen}
        handleModalToggle={handleDeletionModalToggle}
        reloadParent={reload}
      />
      <ErrorModal
        caption={t("KeyValidationError")}
        hasError={keyError}
        close={() => setKeyError(NO_ERROR)}
      />
      <ErrorModal
        caption={t("ModelIdValidationError")}
        hasError={modelIdError}
        close={() => setModelIdError(NO_ERROR)}
      />
      <PageSection variant={PageSectionVariants.light} isWidthLimited>
        <Alerts ref={alertsRef} />
        <TextContent>
          <Text component="h1">{t("ModelSettings")}</Text>
        </TextContent>
      </PageSection>
      <PageSection data-testid={"model-settings-overview"}>
        <Panel variant={"bordered"}>
          <PanelMain>
            <PanelMainBody>
              <Stack hasGutter={true}>
                {isKeyInvalid && (
                  <StackItem>
                    <Alert
                      variant="warning"
                      title={t("KeyInvalidAlert")}
                      data-testid={"model-settings-overview__alert-key-invalid"}
                    />
                  </StackItem>
                )}
                <StackItem>
                  <TextContent>
                    <Text component={"h3"}>
                      {t("APIKey")}
                      <Tooltip
                        aria="none"
                        aria-live="polite"
                        content={t("APIKeyTooltip")}
                      >
                        <Icon>
                          <OutlinedQuestionCircleIcon className={"Info-icon"} />
                        </Icon>
                      </Tooltip>
                    </Text>
                    <Text component={"p"}>{t("APIKeyDescription")}</Text>
                  </TextContent>
                </StackItem>
                <StackItem>
                  {isWcaKeyLoading && (
                    <div
                      className={"Loading"}
                      data-testid={"model-settings-overview__key-loading"}
                    >
                      <Skeleton height="100%" screenreaderText={t("Loading")} />
                    </div>
                  )}
                  {isWcaKeyNotFound && (
                    <TextContent
                      data-testid={"model-settings-overview__key-not-found"}
                    >
                      <Text component={"p"}>{t("NoAPIKey")}</Text>
                    </TextContent>
                  )}
                  {isWcaKeyFound && (
                    <>
                      <TextContent data-testid={"model-settings-overview__key"}>
                        <Text component={"h3"}>{t("APIKey")}</Text>
                      </TextContent>
                      <Split>
                        <SplitItem isFilled={true}>
                          <TextContent>
                            <Text component={"p"} className={"Secret-value"}>
                              {t("SecretValue")}
                            </Text>
                          </TextContent>
                        </SplitItem>
                        <SplitItem>
                          <BusyButton
                            variant={"tertiary"}
                            isSmall={true}
                            isBusy={isValidatingKey}
                            isDisabled={isValidatingKey}
                            onClick={testKey}
                            data-testid={
                              "model-settings-overview__key-test-button"
                            }
                          >
                            {t("Test")}
                          </BusyButton>
                        </SplitItem>
                      </Split>
                    </>
                  )}
                </StackItem>
                <StackItem>
                  {isWcaKeyNotFound && (
                    <Button
                      variant={"primary"}
                      icon={<PlusCircleIcon />}
                      onClick={setModeToKey}
                      data-testid={"model-settings-overview__add-key-button"}
                    >
                      {t("AddAPIKey")}
                    </Button>
                  )}
                  {isWcaKeyFound && (
                    <Split hasGutter={true}>
                      <SplitItem>
                        <Button
                          variant={"primary"}
                          icon={<CheckCircleIcon />}
                          isDisabled={isValidatingKey}
                          onClick={setModeToKey}
                          data-testid={
                            "model-settings-overview__update-key-button"
                          }
                        >
                          {t("UpdateAPIKey")}
                        </Button>
                      </SplitItem>
                      {/* The following part will be opened when AAP-32688 is done.*/}
                      {/*<SplitItem>
                        <Button
                          variant={"danger"}
                          icon={<TrashIcon />}
                          isDisabled={isValidatingKey}
                          onClick={handleDeletionModalToggle}
                          data-testid={
                            "model-settings-overview__delete-key-button"
                          }
                        >
                          {t("DeleteAPIKey")}
                        </Button>
                      </SplitItem>*/}
                    </Split>
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
                        <Text component={"p"}>
                          {(
                            wcaKey as Success<WcaKeyResponse>
                          ).data.lastUpdate.toLocaleString()}
                        </Text>
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
                    <Alert
                      variant="warning"
                      title={t("ModelIdInvalidAlert")}
                      data-testid={
                        "model-settings-overview__alert-model-id-invalid"
                      }
                    />
                  </StackItem>
                )}
                {isWcaModelIdNotFound &&
                  !isWcaKeyFound &&
                  !isWcaKeyLoading &&
                  !isWcaModelIdLoading && (
                    <Alert
                      variant="info"
                      title={t("NoModelIdNoAPIKey")}
                      data-testid={
                        "model-settings-overview__model-id-set-api-key-first"
                      }
                    />
                  )}
                <StackItem>
                  <TextContent>
                    <Text component={"h3"}>
                      {t("ModelId")}
                      <Tooltip
                        aria="none"
                        aria-live="polite"
                        content={t("ModelIdTooltip")}
                      >
                        <Icon>
                          <OutlinedQuestionCircleIcon className={"Info-icon"} />
                        </Icon>
                      </Tooltip>
                    </Text>
                    <Text component={"p"}>{t("ModelIdDescription")}</Text>
                  </TextContent>
                </StackItem>
                <StackItem>
                  <StackItem>
                    {(isWcaKeyLoading || isWcaModelIdLoading) && (
                      <div
                        className={"Loading"}
                        data-testid={
                          "model-settings-overview__model-id-loading"
                        }
                      >
                        <Skeleton
                          height="100%"
                          screenreaderText={t("Loading")}
                        />
                      </div>
                    )}
                    {isWcaModelIdNotFound && !isWcaKeyLoading && (
                      <TextContent
                        data-testid={
                          "model-settings-overview__model-id-not-found"
                        }
                      >
                        <Text component={"p"}>{t("NoModelId")}</Text>
                      </TextContent>
                    )}
                    {isWcaModelIdFound && !isWcaKeyLoading && (
                      <>
                        <TextContent
                          data-testid={"model-settings-overview__model-id"}
                        >
                          <Text component={"h3"}>{t("ModelId")}</Text>
                        </TextContent>
                        <Split>
                          <SplitItem isFilled={true}>
                            <TextContent>
                              {/*This is a safe cast as 'isWcaModelIdFound' is true*/}
                              <Text component={"p"} className={"Secret-value"}>
                                {
                                  (wcaModelId as Success<WcaModelIdResponse>)
                                    .data.model_id
                                }
                              </Text>
                            </TextContent>
                          </SplitItem>
                          <SplitItem>
                            <BusyButton
                              variant={"tertiary"}
                              isSmall={true}
                              isBusy={isValidatingModelId}
                              isDisabled={isValidatingModelId}
                              onClick={testModelId}
                              data-testid={
                                "model-settings-overview__model-id-test-button"
                              }
                            >
                              {t("Test")}
                            </BusyButton>
                          </SplitItem>
                        </Split>
                      </>
                    )}
                  </StackItem>
                </StackItem>
                <StackItem>
                  {isWcaModelIdNotFound && !isWcaKeyLoading && (
                    <Button
                      variant={"primary"}
                      icon={<PlusCircleIcon />}
                      onClick={setModeToModelId}
                      isDisabled={!isWcaKeyFound}
                      data-testid={
                        "model-settings-overview__add-model-id-button"
                      }
                    >
                      {t("AddModelId")}
                    </Button>
                  )}
                  {isWcaModelIdFound && !isWcaKeyLoading && (
                    <Button
                      variant={"primary"}
                      icon={<CheckCircleIcon />}
                      isDisabled={isValidatingModelId}
                      onClick={setModeToModelId}
                      data-testid={
                        "model-settings-overview__update-model-id-button"
                      }
                    >
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
                        <Text component={"p"}>
                          {(
                            wcaModelId as Success<WcaModelIdResponse>
                          ).data.lastUpdate.toLocaleString()}
                        </Text>
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
  );
};
