import '@patternfly/patternfly/patternfly-base.css'
import '@patternfly/patternfly/patternfly-charts-theme-dark.css'

import '@ansible/ansible-ui-framework/style.css'

import {StrictMode} from 'react'
import {createRoot} from 'react-dom/client'
import {App} from './App'
import './i18n'
import './index.css'

// TODO:
//  - Consider just creating a new field in the window object instead, eg: window.__varname
//  - No need for DOM overhead
//  - Use of (shared) objects. No need for serialization, are on same DOM heap.
//  - Security?
// TODO: Missing the hasUserSubscription parameter
const userName = document.getElementById('userName')?.innerText ?? undefined;
const isUserAllowed = document.getElementById('isUserAllowed')?.innerText ?? undefined;

createRoot(document.getElementById('root') as HTMLElement).render(
    <StrictMode>
        <App userName={userName} isUserAllowed={isUserAllowed ? isUserAllowed === 'true' : false}/>
    </StrictMode>
)
