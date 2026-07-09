# MCP Server Authentication Design Options

## Background

The Ansible Lightspeed chatbot integrates with MCP (Model Context Protocol)
servers that need to call AAP Gateway APIs on behalf of the authenticated user.
User-scoped RBAC must be preserved: when an MCP server calls a Gateway API, the
call must execute with the permissions of the user who initiated the chat.

### Current state

The Lightspeed backend receives a DAB JWT (`X-DAB-JW-TOKEN`) from the
authenticated user. This JWT cannot be used by MCP servers to call Gateway
APIs directly because **Gateway's API accepts OAuth2 access tokens, not DAB
JWTs**. These are different token types serving different purposes:

| Token type | Header | Purpose |
|---|---|---|
| DAB JWT | `X-DAB-JW-TOKEN` | Internal DAB service-to-service communication (WebSocket auth, claims loading) |
| OAuth2 access token | `Authorization: Bearer <token>` | Gateway public API access (programmatic) |
| Session cookie | `awx_sessionid` | Gateway browser UI access |

Gateway does not publish a JWKS endpoint, so external services cannot
validate Gateway-issued tokens via standard OIDC discovery. Lightspeed Core
Stack's `jwk-token` authentication module cannot be used here because there
is no JWKS endpoint to point it at, and Gateway would not accept the
validated token on its API regardless.

The `ansible_base.jwt_consumer` module in DAB validates incoming JWTs and
extracts user claims, but this is the inbound direction (tokens coming into
Lightspeed), not the outbound direction (tokens going to Gateway).

### Constraints

- **User RBAC required** -- client credentials (service-level tokens) are
  insufficient because the chatbot is user-facing and users expect their
  permissions to apply to API calls made by MCP servers.
- **AAP Gateway uses Django OAuth Toolkit (DOT)** -- DOT does not support
  RFC 8693 (OAuth 2.0 Token Exchange). There is no open issue or PR for it
  upstream.
- **Security sensitivity** -- any solution that forwards raw user credentials
  (cookies, session tokens) between services will face scrutiny in security
  reviews.

## Options

### Option 1: Lightweight custom token exchange endpoint

Build a small endpoint (in Gateway or Lightspeed) that accepts the user's
existing JWT and issues a scoped OAuth2 access token.

#### Flow

```
Lightspeed backend                    Token Exchange Endpoint
     |                                         |
     |-- POST /api/v1/token-exchange           |
     |   Authorization: Bearer <DAB JWT>       |
     |   Body: { scope: "mcp", audience: ... } |
     |                                         |
     |   1. Validate the JWT                   |
     |   2. Look up the user                   |
     |   3. Create an OAuth2 AccessToken       |
     |      scoped to the user with RBAC       |
     |   4. Return { access_token, expires_in }|
     |                                         |
     |<-- 200 { access_token: "...",           |
     |         expires_in: 3600 }              |
```

#### Implementation

A Django view that:

1. Authenticates the request using the existing DAB JWT
2. Calls Django OAuth Toolkit's
   `AccessToken.objects.create(user=request.user, scope=..., expires=...)` to
   issue a real OAuth2 token
3. Returns the token to the Lightspeed backend
4. The Lightspeed backend passes the token to MCP servers via
   `X-Authorization: Bearer {access_token}`

#### Pros

- Clean separation -- MCP servers call Gateway directly with a standard
  OAuth2 token
- RBAC preserved -- the token is tied to the real user
- Standard mechanism -- OAuth2 bearer tokens are well-understood
- MCP servers are autonomous -- no dependency on Lightspeed for Gateway calls

#### Cons

- Requires code changes in Gateway (or Lightspeed, if Gateway can accept
  tokens issued by Lightspeed)
- Gateway team involvement likely required
- New token type to manage (expiry, revocation, caching)

### Option 2: Proxy pattern

Route all MCP-to-Gateway API calls through the Lightspeed backend, which
already has the user's authenticated session. No new tokens are issued.

#### Flow

```
User (browser)       Lightspeed Backend       MCP Server       Gateway
     |                      |                     |                |
     |-- Chat message ----->|                     |                |
     |                      |-- MCP tool call --->|                |
     |                      |                     |                |
     |                      |<-- proxy request ---|                |
     |                      |   { method, path,   |                |
     |                      |     params }         |                |
     |                      |                     |                |
     |                      |-- Gateway API call -|--------------->|
     |                      |   (with user's      |                |
     |                      |    session or JWT)   |                |
     |                      |                     |                |
     |                      |<--------------------|--- response ---|
     |                      |-- proxy response -->|                |
```

#### Implementation

1. MCP servers call back to the Lightspeed backend when they need Gateway
   data, instead of calling Gateway directly
2. The Lightspeed backend forwards the request to Gateway using the
   credentials it already holds for the user
3. An allowlist restricts which Gateway API endpoints can be proxied

#### Pros

- No new auth infrastructure -- uses existing credentials
- No Gateway team dependency
- Smaller security surface -- no tokens shared with MCP servers
- Fastest to ship

#### Cons

- Added latency (extra network hop through Lightspeed)
- Tighter coupling between Lightspeed and MCP servers
- Lightspeed must maintain an allowlist of Gateway endpoints
- MCP servers lose autonomy -- they depend on the proxy for Gateway access

### Option 3: RFC 8693 token exchange (long-term)

Request the Gateway team to implement RFC 8693 (OAuth 2.0 Token Exchange)
as a custom grant type in Django OAuth Toolkit.

This is the standard mechanism for the "service needs a token on behalf of
a user" problem. The backend presents the user's existing token to the
token endpoint with `grant_type=urn:ietf:params:oauth:grant-type:token-exchange`
and receives a new token scoped for downstream services.

#### Pros

- Standards-compliant
- Cleanest long-term architecture
- Reusable by other AAP services with the same need

#### Cons

- Django OAuth Toolkit does not support it natively
- Requires upstream contribution or Gateway-specific extension
- Cross-team effort with the Gateway team
- Longer timeline

## Comparison

| Consideration              | Option 1 (Token Exchange) | Option 2 (Proxy) | Option 3 (RFC 8693) |
|----------------------------|---------------------------|-------------------|---------------------|
| RBAC preserved             | Yes                       | Yes               | Yes                 |
| New auth code needed       | Yes                       | No                | Yes (in Gateway)    |
| Gateway team involvement   | Likely                    | Minimal           | Required            |
| MCP server autonomy        | High                      | Low               | High                |
| Security surface           | Moderate                  | Smallest          | Moderate            |
| Latency                    | Low                       | Higher            | Low                 |
| Time to ship               | Medium                    | Fastest           | Longest             |

## Recommendation

The DAB JWT and Gateway OAuth2 access tokens are fundamentally different
token types. The JWT cannot be "fixed" to work with Gateway's API — a
different authentication mechanism is needed.

1. **To ship quickly**, Option 2 (proxy) avoids cross-team dependencies and
   new auth infrastructure. Lightspeed already has the user's authenticated
   session and can proxy Gateway calls on behalf of MCP servers.
2. **For cleaner long-term architecture**, Option 1 (lightweight token
   exchange) gives MCP servers autonomy. This requires Gateway team
   involvement to either build the exchange endpoint or accept tokens
   issued by Lightspeed.

## Approaches to avoid

The POC in [PR #2049](https://github.com/ansible/ansible-ai-connect-service/pull/2049)
automates the OAuth2 authorization code flow server-side by forwarding the
user's cookies and CSRF token to the authorization endpoint and parsing the
302 redirect. This approach has several security concerns:

- **Cookie/credential forwarding** -- replaying user session cookies
  server-side is a credential forwarding anti-pattern
- **No redirect validation** -- the Location header is trusted without
  verifying the target URL matches the expected redirect URI
- **No `state` parameter** -- missing CSRF protection on the OAuth flow
- **TLS verification disabled** -- `verify=False` on all requests
- **Fragile coupling** -- depends on the authorization server's form
  field names and redirect behavior

This pattern should not move to production regardless of hardening applied.

## Open questions

- [x] ~~What specific error does Gateway return when MCP servers present the
      DAB JWT?~~ — Gateway's API does not accept DAB JWTs. It requires
      OAuth2 access tokens (`Authorization: Bearer`) or session cookies.
- [x] ~~Can the DAB JWT be configured to include Gateway as a valid
      audience?~~ — No. The tokens are different types; this is not an
      audience configuration issue.
- [x] ~~Does Gateway publish a JWKS endpoint?~~ — No. Gateway does not
      expose `.well-known/jwks.json` or OIDC discovery endpoints for
      external token validation.
- [ ] Does the Gateway team have plans for any token delegation mechanism?
- [ ] What Gateway API endpoints do MCP servers actually need to call?
      (Determines scope of the proxy allowlist for Option 2)
- [ ] For Option 1, would the Gateway team accept an endpoint that exchanges
      a DAB JWT for a scoped OAuth2 access token?

## References

- [RFC 8693 - OAuth 2.0 Token Exchange](https://datatracker.ietf.org/doc/html/rfc8693)
- [Django OAuth Toolkit Documentation](https://django-oauth-toolkit.readthedocs.io/)
- [PR #2049 - POC mcp server integration oauth2 tokens](https://github.com/ansible/ansible-ai-connect-service/pull/2049)
- [AAP-75808](https://redhat.atlassian.net/browse/AAP-75808)
- [AAP Gateway](https://github.com/ansible-automation-platform/aap-gateway)
- [Django Ansible Base (DAB)](https://github.com/ansible-automation-platform/django-ansible-base)
- [DAB Channels Authentication](https://github.com/ansible/django-ansible-base/blob/devel/docs/lib/channels_authentication.md)
- [LCS JWK Token Authentication](https://github.com/lightspeed-core/lightspeed-stack/blob/main/docs/auth/jwk-token.md)
- [AAP 2.7 OIDC for HashiCorp Vault](https://developers.redhat.com/articles/2026/06/10/whats-new-red-hat-ansible-automation-platform-2-7)
