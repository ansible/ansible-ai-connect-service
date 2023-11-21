import {useMemo} from 'react'
import {useTranslation} from 'react-i18next'
import {PageNavigationItem} from "@ansible/ansible-ui-framework";
import {PageAppDenied} from "./PageAppDenied";
import {AppHeader} from "../AppHeader";

interface AppDeniedProps {
    readonly userName?: string
    readonly hasSubscription: boolean
}

export function AppDenied(props: AppDeniedProps) {
    const {t} = useTranslation();
    const {userName, hasSubscription} = props;

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
                        element: <></>
                    },
                ],
            },
        ],
        [t]
    );

    return (
        <PageAppDenied
            header={<AppHeader userName={userName ?? t("UnknownUser")}/>}
            navigationItems={navigationItems}
            hasSubscription={hasSubscription}
        />
    );
}
