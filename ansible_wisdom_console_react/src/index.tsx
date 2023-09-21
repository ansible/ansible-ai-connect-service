import '@patternfly/patternfly/patternfly-base.css'
import '@patternfly/patternfly/patternfly-charts-theme-dark.css'

import '@ansible/ansible-ui-framework/style.css'

import {StrictMode} from 'react'
import {createRoot} from 'react-dom/client'
import {App} from './App'
import './i18n'
import './index.css'

const debugElement = document.getElementById('debug');
const userName = document.getElementById('userName')?.innerText ?? undefined;

createRoot(document.getElementById('root') as HTMLElement).render(
    <StrictMode>
        <App debug={debugElement !== null} userName={userName}/>
    </StrictMode>
)
