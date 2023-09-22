import {PageFramework, PageLayout, PageNavigation, PageNavigationItem} from '@ansible/ansible-ui-framework'
import {Page} from '@patternfly/react-core'
import {ReactNode, useMemo} from 'react'
import {createBrowserRouter, Navigate, Outlet, RouterProvider,} from 'react-router-dom'

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

function PageRouterLayout(props: { header?: ReactNode; navigationItems: PageNavigationItem[] }) {
    const {header, navigationItems} = props
    return (
        <PageFramework>
            <Page header={header} sidebar={<PageNavigation navigation={navigationItems}/>}>
                <PageLayout>
                    <Outlet/>
                </PageLayout>
            </Page>
        </PageFramework>
    )
}
