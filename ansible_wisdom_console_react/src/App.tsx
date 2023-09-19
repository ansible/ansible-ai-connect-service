import {useMemo} from 'react'
import {useTranslation} from 'react-i18next'
import {AppHeader} from './AppHeader'
import {PageApp} from './PageApp'
import {PageNavigation, PageNavigationElements} from './PageNavigation'
import {ModelSettings} from "./ModelSettings";

export interface AppProps {
    debug: boolean
}

export function App(props: AppProps) {
    const {t} = useTranslation();
    const {debug} = props;

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
                        element: <ModelSettings debug={debug}/>
                    },
                ],
            },
        ],
        [t]
    );

    return (
        <PageApp
            header={<AppHeader/>}
            sidebar={<PageNavigation navigationItems={navigationItems}/>}
            navigationItems={navigationItems}
            basename="/console"
        />
    );
}

export default App;
