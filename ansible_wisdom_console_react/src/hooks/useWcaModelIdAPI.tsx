import {useEffect, useState} from "react";
import {WcaModelId} from "../api/types";
import {getWcaModelId} from "../api/api";

export const useWcaModelId = (reload: boolean) => {
    const [wcaModelId, setWcaModelId] = useState<WcaModelId>({
        status: "NOT_ASKED",
    });

    useEffect(() => {
        let isMounted = true;
        if (reload) {
            setWcaModelId({status: "LOADING"});
            getWcaModelId()
                .then((response) => {
                    if (isMounted) {
                        const modelId = response.data['model_id'];
                        const lastUpdate = response.data['last_update'];
                        if (lastUpdate) {
                            setWcaModelId({status: "SUCCESS", data: {model_id: modelId, lastUpdate: new Date(lastUpdate)}});
                        } else {
                            setWcaModelId({status: "SUCCESS_NOT_FOUND"});
                        }
                    }
                })
                .catch((error) => {
                    setWcaModelId({status: "FAILURE", error: error});
                });
        }
        return () => {
            isMounted = false;
        };
    }, [reload]);

    return wcaModelId;
};
