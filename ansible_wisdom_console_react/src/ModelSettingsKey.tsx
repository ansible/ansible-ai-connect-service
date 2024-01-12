import React, { useCallback, useMemo, useState } from "react";
import "./ModelSettings.css";
import { WcaKey, WcaKeyRequest } from "./api/types";
import { saveWcaKey } from "./api/api";
import { HasError, NO_ERROR } from "./ErrorModal";
import { DELAY } from "./api/globals";
import { ModelSettingsEditor } from "./ModelSettingsEditor";

interface ModelSettingsKeyProps {
  readonly wcaKey: WcaKey | undefined;
  readonly cancel: () => void;
  readonly reload: () => void;
}

export const ModelSettingsKey = (props: ModelSettingsKeyProps) => {
  const { wcaKey, cancel, reload } = props;

  const [saving, setSaving] = useState<boolean>(false);
  const hasWcaKey = useMemo(() => wcaKey?.status === "SUCCESS", [wcaKey]);

  const [isKeyInvalid, setIsKeyInvalid] = useState<boolean>(false);
  const [keyError, setKeyError] = useState<HasError>(NO_ERROR);

  const save = useCallback(
    (value: string) => {
      const timeoutId = setTimeout(() => setSaving(true), DELAY);
      const wcaKey: WcaKeyRequest = { key: value };
      saveWcaKey(wcaKey)
        .then((_) => {
          reload();
        })
        .catch((error) => {
          if (error.response?.status === 400) {
            setIsKeyInvalid(true);
          } else {
            setKeyError({
              inError: true,
              message: error.message,
              detail: error.response?.data?.detail,
            });
          }
        })
        .finally(() => {
          setSaving(false);
          clearTimeout(timeoutId);
        });
    },
    [reload],
  );

  return (
    <ModelSettingsEditor
      hasValue={hasWcaKey}
      isSaving={saving}
      isValueInvalid={isKeyInvalid}
      isPassword={true}
      clearInvalidState={() => setIsKeyInvalid(false)}
      errorState={keyError}
      setErrorState={setKeyError}
      save={save}
      cancel={cancel}
      captions={{
        errorModalCaption: "KeyError",
        invalidAlertCaption: "KeyInvalidAlert",
        setValueTitle: "AddKeyTitle",
        updateValueTitle: "UpdateKeyTitle",
        fieldCaption: "APIKey",
        fieldCaptionTooltip: "APIKeyTooltip",
        fieldInputCaption: "AddKey",
        fieldInputPlaceholder: "PlaceholderKey",
      }}
    />
  );
};
