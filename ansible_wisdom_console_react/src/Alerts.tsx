import React, {forwardRef, useImperativeHandle} from 'react';
import {Alert, AlertActionCloseButton, AlertGroup, AlertProps} from "@patternfly/react-core";
import {useTranslation} from "react-i18next";
import './ModelSettings.css';

export type AlertsHandle = {
    addAlert: (title: string) => void;
};

type AlertsProps = {}

export const Alerts = forwardRef<AlertsHandle, AlertsProps>((props, ref) => {
    const {t} = useTranslation();
    const [alerts, setAlerts] = React.useState<React.ReactElement<AlertProps>[]>([]);

    useImperativeHandle(ref, () => ({
        addAlert(title: string) {
            _addAlert(title);
        }
    }), []);

    const _addAlert = (title: string) => {
        const key = new Date().getTime();
        setAlerts(prevAlerts => [
            <Alert
                variant={"success"}
                title={title}
                timeout={5000}
                onTimeout={() => _removeAlert(key)}
                isLiveRegion
                actionClose={
                    <AlertActionCloseButton
                        title={t("Close")}
                        variantLabel={"success alert"}
                        onClose={() => _removeAlert(key)}
                    />
                }
                key={key}
                id={key.toString()}
            >
            </Alert>,
            ...prevAlerts
        ]);
    };

    const _removeAlert = (key: React.Key) => {
        setAlerts(prevAlerts => prevAlerts.filter(alert => alert.props.id !== key.toString()));
    };
    return (
        <AlertGroup isToast={true} isLiveRegion={true}>
            {alerts}
        </AlertGroup>
    )
});
