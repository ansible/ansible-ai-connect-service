import {useMemo} from 'react'
import {useTranslation} from 'react-i18next'
import {AppHeader} from './AppHeader'
import {PageApp} from './PageApp'
import {PageNavigation, PageNavigationElements} from './PageNavigation'
import {Overview} from "./Overview";
import {ModelSettings} from "./ModelSettings";

export function App() {
    const {t} = useTranslation()

    const navigationItems = useMemo<PageNavigationElements>(
        () => [
            {
                // Overview
                label: t('Overview'),
                path: 'overview',
                element: <Overview/>,
            },
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
    )

    return (
        <PageApp
            header={<AppHeader/>}
            sidebar={<PageNavigation navigationItems={navigationItems}/>}
            navigationItems={navigationItems}
            basename="/console"
        />
    )
}

export default App;
