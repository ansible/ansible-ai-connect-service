import React, {useCallback, useMemo, useState} from 'react';
import './ModelSettings.css';
import {WcaModelId, WcaModelIdRequest} from "./api/types";
import {saveWcaModelId} from "./api/api";
import {HasError, NO_ERROR} from "./ErrorModal";
import {DELAY} from "./api/globals";
import {ModelSettingsEditor} from "./ModelSettingsEditor";

interface ModelSettingsModelIdProps {
    readonly wcaModelId: WcaModelId;
    readonly cancel: () => void;
    readonly reload: () => void;
}

export const ModelSettingsModelId = (props: ModelSettingsModelIdProps) => {
    const {wcaModelId, cancel, reload} = props;

    const [saving, setSaving] = useState(false);
    const hasWcaModelId = useMemo(() => wcaModelId?.status === "SUCCESS", [wcaModelId]);

    const [isModelIdInvalid, setIsModelIdInvalid] = useState<boolean>(false);
    const [modelIdError, setModelIdError] = useState<HasError>(NO_ERROR);

    const save = useCallback((value: string) => {
        const timeoutId = setTimeout(() => setSaving(true), DELAY);
        const wcaModelId: WcaModelIdRequest = {model_id: value};
        saveWcaModelId(wcaModelId)
            .then((_) => {
                reload();
            })
            .catch((error) => {
                if (error.response?.status === 400) {
                    setIsModelIdInvalid(true);
                } else {
                    setModelIdError({
                        inError: true,
                        message: error.message,
                        detail: error.response?.data?.detail
                    });
                }
            })
            .finally(() => {
                setSaving(false);
                clearTimeout(timeoutId);
            });
    }, [reload]);

    return (
        <ModelSettingsEditor
            hasValue={hasWcaModelId}
            isSaving={saving}
            isValueInvalid={isModelIdInvalid}
            clearInvalidState={() => setIsModelIdInvalid(false)}
            errorState={modelIdError}
            setErrorState={setModelIdError}
            save={save}
            cancel={cancel}
            captions={
                {
                    errorModalCaption: "ModelIdError",
                    invalidAlertCaption: "ModelIdInvalidAlert",
                    setValueTitle: "AddModelIdTitle",
                    updateValueTitle: "UpdateModelIdTitle",
                    fieldCaption: "ModelId",
                    fieldCaptionTooltip: "ModelIdTooltip",
                    fieldInputCaption: "AddModelId",
                    fieldInputPlaceholder: "PlaceholderModelId"
                }
            }
        />
    );
}
