import {PageMasthead} from '@ansible/ansible-ui-framework'
import {useTranslation} from 'react-i18next'

export function AppHeader() {
    const {t} = useTranslation()
    return (
        <PageMasthead title={t("AnsibleLightspeedConsole")}/>
    )
}
