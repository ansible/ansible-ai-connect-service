import {useMemo} from 'react'
import {useTranslation} from 'react-i18next'
import {AppHeader} from './AppHeader'
import {ModelSettings} from "./ModelSettings";
import {TelemetrySettings} from "./TelemetrySettings";
import {PageNavigationItem} from "@ansible/ansible-ui-framework";
import {PageApp} from "./PageApp";

export interface AppProps {
    readonly userName: string
    readonly telemetryOptEnabled: boolean
}

export function App(props: AppProps) {
    const {t} = useTranslation();
    const {userName, telemetryOptEnabled} = props;

    const navigationItems = useMemo<PageNavigationItem[]>(
        () => {
            const items = [{
                // Model settings
                label: t('ModelSettings'),
                path: 'settings',
                element: <ModelSettings/>
            }]
            if (telemetryOptEnabled) {
                items.push({
                    // Telemetry
                    label: t('Telemetry'),
                    path: 'telemetry',
                    element: <TelemetrySettings/>
                })
            }
            return [
                {
                    // Admin portal
                    label: t('AdminPortal'),
                    path: 'admin',
                    children: items,
                },
            ]
        },
        [t, telemetryOptEnabled]
    );

    return (
        <PageApp
            header={<AppHeader userName={userName}/>}
            navigationItems={navigationItems}
            basename="/console"
        />
    );
}

export default App;
