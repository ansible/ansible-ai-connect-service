import '@patternfly/patternfly/patternfly-base.css'
import '@patternfly/patternfly/patternfly-charts-theme-dark.css'

import '@ansible/ansible-ui-framework/style.css'

import {StrictMode} from 'react'
import {createRoot} from 'react-dom/client'
import {App} from './App'
import './i18n'
import './index.css'

const userName = document.getElementById('user_name')?.innerText ?? "undefined";
const telemetryOptEnabled = Boolean(document.getElementById('telemetry_opt_enabled')?.innerText);

createRoot(document.getElementById('root') as HTMLElement).render(
    <StrictMode>
        <App userName={userName} telemetryOptEnabled={telemetryOptEnabled}/>
    </StrictMode>
)
