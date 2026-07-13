# MCP OAuth2 Redirect Flow

## Problem

When users access the Lightspeed chatbot from AAP-UI, the Gateway proxies
requests with an `X-DAB-JW-TOKEN` JWT. Lightspeed authenticates the user via
`LightspeedJWTAuthentication`, but this does not create a `UserSocialAuth`
record with a refresh token. MCP servers (e.g.,
[aap-mcp-server](https://github.com/ansible/aap-mcp-server)) need to call
Gateway API endpoints, which require an OAuth2 access token — they do not
accept the DAB JWT.

Without a stored refresh token, Lightspeed cannot obtain an OAuth2 access
token on behalf of the user, and MCP tool calls fail.

## Solution

A one-time OAuth2 redirect flow that transparently creates the
`UserSocialAuth` record when a JWT-authenticated user first triggers an MCP
tool call.

### Flow

```
AAP-UI (Gateway origin)
  → Lightspeed /login/aap/?next=<aap-ui-chatbot-url>
    → Gateway /o/authorize/ (auto-approves, user has active session)
      → Lightspeed /complete/aap/ (creates UserSocialAuth with refresh_token)
        → redirect to <aap-ui-chatbot-url> (back to AAP-UI)
```

1. User sends a chat message that requires MCP tools.
2. `get_mcp_headers()` calls `_get_gateway_access_token()`, which looks up
   `UserSocialAuth(provider="aap")` for the user.
3. No record exists → raises `ChatbotOAuth2RequiredException` (HTTP 403).
4. The API returns:
   ```json
   {
     "code": "error__chatbot_oauth2_required",
     "message": "OAuth2 authentication required for MCP tool access",
     "login_url": "https://<lightspeed-url>/login/aap/"
   }
   ```
5. The chatbot frontend detects this error, appends `?next=<current-page>`
   to the `login_url`, and redirects the browser.
6. Since the user already has a valid Gateway session, the OAuth2 consent
   screen auto-approves (or requires one click).
7. `social_django` completes the flow, creating a `UserSocialAuth` record
   with the refresh token.
8. The user is redirected back to the chatbot page. Subsequent chat messages
   work without further redirects.

### Token exchange (after redirect)

Once the `UserSocialAuth` record exists, `_get_gateway_access_token()`
exchanges the stored refresh token for a short-lived Gateway access token:

```
Lightspeed → POST {AAP_API_URL}/o/token/
               grant_type=refresh_token
               refresh_token=<stored>
               client_id=<SOCIAL_AUTH_AAP_KEY>
               client_secret=<SOCIAL_AUTH_AAP_SECRET>
           ← 200 {access_token, expires_in, refresh_token}
```

The access token is cached in Django's cache framework with a TTL of
`expires_in - 10 minutes` (minimum 60 seconds). If the Gateway rotates the
refresh token, the new value is persisted to `UserSocialAuth.extra_data`.

## Changes

### Backend

| File | Change |
|------|--------|
| `ansible_ai_connect/ai/api/exceptions.py` | New `ChatbotOAuth2RequiredException` (403) with `login_url` property |
| `ansible_ai_connect/ai/api/views.py` | New `_get_gateway_access_token()` static method on `AACSAPIView`; extended `get_mcp_headers()` with `mcp-server` type handling |
| `ansible_ai_connect/main/exception_handler.py` | Include `login_url` in error response when present on the exception |
| `ansible_ai_connect/main/settings/base.py` | New `LIGHTSPEED_URL` env var for Lightspeed's externally-reachable URL |
| `ansible_ai_connect/users/pipeline.py` | Modified `block_auth_users()` to allow JWT-authenticated AAP users without a `UserSocialAuth` record to complete the OAuth2 flow |

### Frontend

| File | Change |
|------|--------|
| `aap_chatbot/src/useChatbot/useChatbot.ts` | `getOAuth2LoginUrl()` helper; redirect on 403 in streaming and non-streaming paths; uses `window.location.pathname` for `next` so user returns to their AAP-UI page |

### MCP header types

`get_mcp_headers()` now handles two MCP server types:

| Server type | Auth header | Token source |
|-------------|-------------|--------------|
| `controller`, `eda`, `hub`, `lightspeed` | `X-DAB-JW-TOKEN` | Forwarded from Gateway proxy |
| `mcp-server` | `X-Authorization: Bearer <token>` | OAuth2 access token via refresh token exchange |

## Configuration

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LIGHTSPEED_URL` | Yes | Lightspeed's externally-reachable base URL (e.g., `https://lightspeed.example.com`). Used to build the `login_url` in the OAuth2 redirect response. |
| `AAP_UI_URL` | Yes | AAP-UI's externally-reachable base URL (e.g., `https://gateway.example.com`). Allows the OAuth2 redirect to return the user to AAP-UI after completing the flow. |
| `AAP_API_URL` | Yes | Gateway base URL (e.g., `https://gateway.example.com`). Already required for AAP OAuth2 login. |
| `SOCIAL_AUTH_AAP_KEY` | Yes | OAuth2 application client ID on the Gateway. |
| `SOCIAL_AUTH_AAP_SECRET` | Yes | OAuth2 application client secret on the Gateway. |

### AAP Gateway OAuth2 application

An OAuth2 application must be registered on the AAP Gateway for Lightspeed.
This may be the same application used for the existing AAP login flow, or a
separate one depending on deployment requirements.

#### Required settings

| Field | Value | Notes |
|-------|-------|-------|
| **Client Type** | `Confidential` | Lightspeed stores the client secret server-side |
| **Grant Type** | `Authorization code` | Standard OAuth2 flow with browser redirect |
| **Redirect URIs** | `https://<lightspeed-url>/complete/aap/` | Must match `LIGHTSPEED_URL` + `/complete/aap/`. Multiple URIs can be listed (one per line) if Lightspeed is reachable at multiple URLs. |
| **Scope** | `write` | The MCP server needs write access to call Gateway API endpoints (e.g., launch jobs, create resources). The current `SOCIAL_AUTH_AAP_SCOPE` is `["read"]` — this may need to be expanded to `["read", "write"]` depending on what operations the MCP server performs. |

#### Creating the application on the Gateway

Via the Gateway UI:

1. Navigate to **Administration → Applications**
2. Click **Add**
3. Set the fields per the table above
4. Set **Organization** to the appropriate org
5. Save and copy the **Client ID** and **Client Secret**
6. Set `SOCIAL_AUTH_AAP_KEY` and `SOCIAL_AUTH_AAP_SECRET` in Lightspeed's env

Via the Gateway API:

```bash
curl -X POST https://<gateway>/api/gateway/v1/applications/ \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ansible Lightspeed",
    "client_type": "confidential",
    "authorization_grant_type": "authorization-code",
    "redirect_uris": "https://<lightspeed-url>/complete/aap/"
  }'
```

#### Reusing the existing application

If Lightspeed already has an OAuth2 application for the AAP login flow
(`SOCIAL_AUTH_AAP_KEY` / `SOCIAL_AUTH_AAP_SECRET`), the same application can
be reused for the MCP token exchange, provided:

1. The **Redirect URI** includes the Lightspeed callback URL
2. The **Scope** is sufficient for MCP server operations
3. The **Grant Type** is `Authorization code` (which it already is for login)

No separate application is needed unless the deployment requires different
scope or audit separation between login and MCP access.

#### Scope considerations

The current login flow requests `read` scope
(`SOCIAL_AUTH_AAP_SCOPE = ["read"]`). If the MCP server needs to perform
write operations via the Gateway API (launching jobs, creating inventories,
etc.), the scope must be expanded:

```python
# In settings or env override
SOCIAL_AUTH_AAP_SCOPE = ["read", "write"]
```

Alternatively, if write access should only apply to the MCP token (not the
login flow), a separate OAuth2 application with `write` scope could be used
for the redirect flow, while the login flow retains `read` scope. This
would require additional configuration (a second set of client
credentials).

## Limitations

- **On-prem only**: This flow requires AAP OAuth2 login. SaaS (RHSSO) and
  upstream (GitHub) deployments use different auth providers and are not
  affected.
- **Refresh token validity**: If the Gateway revokes the refresh token, the
  token exchange returns `None` and MCP headers are omitted. The chatbot
  continues to work for non-MCP queries.
- **One-time redirect**: The OAuth2 redirect happens once per user. After
  the `UserSocialAuth` record is created, subsequent sessions use the stored
  refresh token without any redirect.
- **Auto-approval**: The Gateway should auto-approve the OAuth2 consent for
  users who already have an active session. If it shows a consent screen,
  the user must click "Authorize" once.
