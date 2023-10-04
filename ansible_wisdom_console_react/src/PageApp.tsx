import {PageFramework, PageLayout, PageNavigation, PageNavigationItem, usePageNavSideBar} from '@ansible/ansible-ui-framework'
import {Brand, Page, Text, TextContent, TextVariants} from '@patternfly/react-core'
import {ReactNode, useMemo} from 'react'
import {useTranslation} from 'react-i18next'
import {createBrowserRouter, Navigate, Outlet, RouterProvider,} from 'react-router-dom'
import LSLogo from "./lightspeed-logo.png"
import './PageApp.css'

// This is copied from ansible/ansible-ui/framework and modified to support redirection
// to 'admin/settings' by default. When the Admin Portal moves to console.redhat.com *OR*
// ansible/ansible-ui/framework supports redirection to a default root this can be removed.
// See https://issues.redhat.com/browse/AAP-16027
export function PageApp(props: {
    basename: string
    navigationItems: PageNavigationItem[]
    header?: ReactNode
}) {
    const {navigationItems, basename, header} = props
    const navigationItemsWithRoot = useMemo<PageNavigationItem[]>(
        () => [
            {
                path: '*',
                element: <PageRouterLayout header={header} navigationItems={navigationItems}/>,
                children: navigationItems,
            },
            {
                path: '/',
                element: <Navigate to="/admin/settings" replace={true}/>,
            },
            {
                path: '/admin',
                element: <Navigate to="/admin/settings" replace={true}/>,
            },
        ],
        [header, navigationItems]
    );

    const router = useMemo(
        () => createBrowserRouter(navigationItemsWithRoot, {basename}),
        [basename, navigationItemsWithRoot]
    )

    return <RouterProvider router={router}/>
}

function LSBrand(props: { cName?: string }) {
    const {t} = useTranslation();
    return (
        <div className={props.cName}>
            <Brand alt="" widths={{default: '40px', md: '40px'}} className={'ansible-lightspeed-logo'}>
                <source media="(min-width: 40px)" srcSet={LSLogo}/>
            </Brand>
            <TextContent className={'ansible-lightspeed-w'}>
                <Text component={TextVariants.p} className={'ansible-lightspeed-t'}>
                    {t('AnsibleLightspeed') + ' ' + t('with')}
                </Text>
                <Text component={TextVariants.p} className={'ansible-lightspeed-t'}>
                    {t('IBMwatsonxCodeAssistant')}
                </Text>
            </TextContent>
        </div>
    )
}

function PageSidebar(props: { navigation: PageNavigationItem[] }) {
    const navBar = usePageNavSideBar();
    const barStateClassName = navBar.isOpen ? "pf-m-expanded" : "pf-m-collapsed";
    const groupClassName = ' pf-c-page__sidebar ' + barStateClassName;
    return (<div className={groupClassName}>
        <LSBrand cName={groupClassName} aria-hidden={!navBar.isOpen}/>
        <PageNavigation navigation={props.navigation}/>
    </div>)
}

function PageRouterLayout(props: { header?: ReactNode; navigationItems: PageNavigationItem[] }) {
    const {header, navigationItems} = props
    return (
        <PageFramework>
            <Page header={header} sidebar={<PageSidebar navigation={navigationItems}/>}>
                <PageLayout>
                    <Outlet/>
                </PageLayout>
            </Page>
        </PageFramework>
    )
}
