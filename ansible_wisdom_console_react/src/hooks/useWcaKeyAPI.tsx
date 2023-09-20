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
                        if (lastUpdate) {
                            setWcaKey({status: "SUCCESS", data: {lastUpdate: new Date(lastUpdate)}});
                        } else {
                            setWcaKey({status: "SUCCESS_NOT_FOUND"});
                        }
                    }
                })
                .catch((error) => {
                    setWcaKey({status: "FAILURE", error: error});
                });
        }
        return () => {
            isMounted = false;
        };
    }, [reload]);

    return wcaKey;
};
