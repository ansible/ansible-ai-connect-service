import React, { useEffect, useState } from "react";
import { Page } from "@patternfly/react-core";
import "./ModelSettings.css";
import { ModelSettingsKey } from "./ModelSettingsKey";
import { ModelSettingsModelId } from "./ModelSettingsModelId";
import { ModelSettingsOverview } from "./ModelSettingsOverview";
import { useWcaKey } from "./hooks/useWcaKeyAPI";
import { WcaKey, WcaModelId } from "./api/types";
import { useWcaModelId } from "./hooks/useWcaModelIdAPI";

export type Mode = "OVERVIEW" | "SET_WCA_KEY" | "SET_MODEL_ID";

export function ModelSettings() {
  const [mode, setMode] = useState<Mode>("OVERVIEW");
  const [reloadWcaKey, setReloadWcaKey] = useState<boolean>(true);
  const [reloadWcaModelId, setReloadWcaModelId] = useState<boolean>(true);
  const [wcaKey, setWcaKey] = useState<WcaKey>({ status: "NOT_ASKED" });
  const [wcaModelId, setWcaModelId] = useState<WcaModelId>({
    status: "NOT_ASKED",
  });
  const _wcaKey = useWcaKey(reloadWcaKey);
  const _wcaModelId = useWcaModelId(reloadWcaModelId);

  useEffect(() => {
    setWcaKey(_wcaKey);
  }, [_wcaKey]);

  useEffect(() => {
    setWcaModelId(_wcaModelId);
  }, [_wcaModelId]);

  return (
    <Page>
      {mode === "OVERVIEW" && (
        <ModelSettingsOverview
          wcaKey={wcaKey}
          wcaModelId={wcaModelId}
          setModeToKey={() => {
            setReloadWcaKey(false);
            setMode("SET_WCA_KEY");
          }}
          setModeToModelId={() => {
            setReloadWcaModelId(false);
            setMode("SET_MODEL_ID");
          }}
          reload={() => {
            setWcaKey({ status: "SUCCESS_NOT_FOUND" });
            setReloadWcaKey(false);
            setMode("OVERVIEW");
          }}
        />
      )}
      {mode === "SET_WCA_KEY" && (
        <ModelSettingsKey
          wcaKey={wcaKey}
          cancel={() => setMode("OVERVIEW")}
          reload={() => {
            setWcaKey({ status: "NOT_ASKED" });
            setReloadWcaKey(true);
            setMode("OVERVIEW");
          }}
        />
      )}
      {mode === "SET_MODEL_ID" && (
        <ModelSettingsModelId
          wcaModelId={wcaModelId}
          cancel={() => setMode("OVERVIEW")}
          reload={() => {
            setWcaModelId({ status: "NOT_ASKED" });
            setReloadWcaModelId(true);
            setMode("OVERVIEW");
          }}
        />
      )}
    </Page>
  );
}
