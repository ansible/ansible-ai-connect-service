import {useMemo} from 'react'
import {useTranslation} from 'react-i18next'
import {AppHeader} from './AppHeader'
import {PageApp} from './PageApp'
import {PageNavigation, PageNavigationElements} from './PageNavigation'
import {ModelSettings} from "./ModelSettings";

export function App() {
    const {t} = useTranslation()

    const navigationItems = useMemo<PageNavigationElements>(
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
