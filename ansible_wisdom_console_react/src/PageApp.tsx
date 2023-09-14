import {PageFramework, PageLayout} from '@ansible/ansible-ui-framework'
import {Page} from '@patternfly/react-core'
import {ReactNode, useMemo} from 'react'
import {createBrowserRouter, Navigate, Outlet, RouterProvider, useNavigate,} from 'react-router-dom'
import {PageNavigationElements} from './PageNavigation'

export function PageApp(props: {
    basename: string
    navigationItems: PageNavigationElements
    header?: ReactNode
    sidebar?: ReactNode
}) {
    const {navigationItems, basename, header, sidebar} = props
    const navigationItemsWithRoot = useMemo<PageNavigationElements>(
        () => [
            {
                path: '*',
                element: <PageRouterLayout header={header} sidebar={sidebar}/>,
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
        [header, navigationItems, sidebar]
    )

    const router = useMemo(
        () => createBrowserRouter(navigationItemsWithRoot, {basename}),
        [basename, navigationItemsWithRoot]
    )

    return <RouterProvider router={router}/>
}

function PageRouterLayout(props: { header?: ReactNode; sidebar?: ReactNode }) {
    const {header, sidebar} = props
    const navigate = useNavigate()
    return (
        <PageFramework navigate={navigate}>
            <Page header={header} sidebar={sidebar}>
                <PageLayout>
                    <Outlet/>
                </PageLayout>
            </Page>
        </PageFramework>
    )
}
