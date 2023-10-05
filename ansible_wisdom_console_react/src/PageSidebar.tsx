import {PageNavigation, PageNavigationItem, usePageNavSideBar} from '@ansible/ansible-ui-framework'
import {Brand, Text, TextContent, TextVariants} from '@patternfly/react-core'
import {useTranslation} from 'react-i18next'
import LSLogo from "./lightspeed-logo.png"
import './PageApp.css'

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

export function PageSidebar(props: { navigation: PageNavigationItem[] }) {
    const navBar = usePageNavSideBar();
    const barStateClassName = navBar.isOpen ? "pf-m-expanded" : "pf-m-collapsed";
    const groupClassName = ' pf-c-page__sidebar ' + barStateClassName;
    return (<div className={groupClassName}>
        <LSBrand cName={groupClassName} aria-hidden={!navBar.isOpen}/>
        <PageNavigation navigation={props.navigation}/>
    </div>)
}
