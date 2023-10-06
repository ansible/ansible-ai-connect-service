import {useMemo} from 'react'
import {useTranslation} from 'react-i18next'
import {AppHeader} from './AppHeader'
import {ModelSettings} from "./ModelSettings";
import {PageNavigationItem} from "@ansible/ansible-ui-framework";
import {PageApp} from "./PageApp";

export interface AppProps {
    readonly userName?: string
}

export function App(props: AppProps) {
    const {t} = useTranslation();
    const {userName} = props;

    const navigationItems = useMemo<PageNavigationItem[]>(
        () => [
            {
                // Admin portal
                label: t('AdminPortal'),
                path: 'admin',
                children: [
                    {
                        // Model settings
                        label: t('ModelSettings'),
                        path: 'settings',
                        element: <ModelSettings/>
                    },
                ],
            },
        ],
        [t]
    );

    return (
        <PageApp
            header={<AppHeader userName={userName ?? t("UnknownUser")}/>}
            navigationItems={navigationItems}
            basename="/console"
        />
    );
}

export default App;
