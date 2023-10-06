import {PageNavigation, PageNavigationItem, usePageNavSideBar} from '@ansible/ansible-ui-framework'
import {Brand, Text, TextContent, TextVariants} from '@patternfly/react-core'
import {useTranslation} from 'react-i18next'
import LSLogo from "./lightspeed-logo.png"
import './PageApp.css'

interface LSBrandProps {
    readonly   cName?: string
}

function LSBrand(props: LSBrandProps) {
    const {t} = useTranslation();
    const {cName} = props;
    return (
        <div
            data-testid={"page-sidebar__brand"}
            className={cName}
        >
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
    );
}

interface PageSidebarProps {
    readonly   navigation: PageNavigationItem[];
}

export function PageSidebar(props: PageSidebarProps) {
    const navBar = usePageNavSideBar();
    const {navigation} = props;
    const barStateClassName = navBar.isOpen ? "pf-m-expanded" : "pf-m-collapsed";
    const groupClassName = ' pf-c-page__sidebar ' + barStateClassName;
    return (
        <div className={groupClassName}>
            <LSBrand cName={groupClassName} aria-hidden={!navBar.isOpen}/>
            <div data-testid={"page-sidebar__navigation"}>
                <PageNavigation navigation={navigation}/>
            </div>
        </div>
    );
}
