import {usePageNavBarClick, usePageNavSideBar} from '@ansible/ansible-ui-framework'
import {Nav, NavExpandable, NavItem, NavList, PageSidebar} from '@patternfly/react-core'

export function PageNavigation(props: { navigationItems: PageNavigationElements }) {
    const {navigationItems} = props
    const navBar = usePageNavSideBar()
    return (
        <PageSidebar
            isNavOpen={navBar.isOpen}
            nav={
                <Nav>
                    <NavList>
                        <PageNavigationItems baseRoute={''} items={navigationItems}/>
                    </NavList>
                </Nav>
            }
        />
    )
}

interface PageNavigationGroup {
    label?: string
    path: string
    children: PageNavigationElement[]
}

interface PageNavigationComponent {
    label?: string
    path: string
    element: JSX.Element
}

type PageNavigationElement = PageNavigationGroup | PageNavigationComponent

export type PageNavigationElements = PageNavigationElement[]

export function PageNavigationItems(props: { items: PageNavigationElements; baseRoute: string }) {
    return (
        <>
            {props.items.map((item: PageNavigationElement) => (
                <PageNavigationItem key={item.path} item={item} baseRoute={props.baseRoute}/>
            ))}
        </>
    )
}

function PageNavigationItem(props: { item: PageNavigationElement; baseRoute: string }) {
    const onClickNavItem = usePageNavBarClick()
    const {item} = props
    const route = props.baseRoute + '/' + item.path
    if (item.path === '/' && 'children' in item) {
        return <PageNavigationItems items={item.children} baseRoute={''}/>
    } else if (
        'children' in item &&
        item.children.find((child: PageNavigationElement) => child.label !== undefined) !== undefined
    ) {
        if (!item.label) {
            return <></>
        }
        return (
            <NavExpandable title={item.label} isActive={window.location.pathname.startsWith(route)} isExpanded>
                <PageNavigationItems items={item.children} baseRoute={route}/>
            </NavExpandable>
        )
    } else if ('label' in item) {
        return (
            <NavItem isActive={window.location.pathname.startsWith(route)} onClick={() => onClickNavItem(route)}>
                {item.label}
            </NavItem>
        )
    }
    return <></>
}
