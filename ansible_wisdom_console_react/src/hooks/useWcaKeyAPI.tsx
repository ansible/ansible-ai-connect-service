import {useEffect, useState} from "react";
import {WcaKey} from "../api/types";
import {getWcaKey} from "../api/api";

export const useWcaKey = (reload: boolean) => {
    const [wcaKey, setWcaKey] = useState<WcaKey>({
        status: "NOT_ASKED",
    });

    useEffect(() => {
        let isMounted = true;
        if (reload) {
            setWcaKey({status: "LOADING"});
            getWcaKey()
                .then((response) => {
                    if (isMounted) {
                        const lastUpdate = response.data['last_update'];
                        setWcaKey({status: "SUCCESS", data: {lastUpdate: new Date(lastUpdate)}});
                    }
                })
                .catch((error) => {
                    if (error.response.status === 404) {
                        setWcaKey({status: "SUCCESS_NOT_FOUND"});
                    } else {
                        setWcaKey({status: "FAILURE", error: error});
                    }
                });
        }
        return () => {
            isMounted = false;
        };
    }, [reload]);

    return wcaKey;
};
