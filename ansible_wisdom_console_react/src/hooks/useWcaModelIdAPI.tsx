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
                        setWcaModelId({status: "SUCCESS", data: {model_id: modelId, lastUpdate: new Date(lastUpdate)}});
                    }
                })
                .catch((error) => {
                    if (error.response.status === 404) {
                        setWcaModelId({status: "SUCCESS_NOT_FOUND"});
                    } else {
                        setWcaModelId({status: "FAILURE", error: error});
                    }
                });
        }
        return () => {
            isMounted = false;
        };
    }, [reload]);

    return wcaModelId;
};
