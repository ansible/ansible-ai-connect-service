# POC: Lightweight Token Exchange for MCP Server Authentication

## Context

MCP servers need Gateway OAuth2 access tokens to call Gateway APIs with user
RBAC. The current DAB JWT (`X-DAB-JW-TOKEN`) is not accepted by Gateway's
API. PR #2049's approach (automating the 302 redirect flow) has security
concerns. See `docs/MCP-Authentication.md` for full background.

**Key insight:** Users who log in via AAP OAuth2 (on-prem) already have a
**refresh token from Gateway** stored in `UserSocialAuth.extra_data`. We can
exchange that for a fresh Gateway access token via a standard
`grant_type=refresh_token` call — no browser flow, no cookie forwarding.

## Approach

Create a token exchange utility function and integrate it into `get_mcp_headers`.
The function:
1. Looks up the user's `UserSocialAuth` record for the AAP provider
2. Uses the stored `refresh_token` to call Gateway's `/o/token/`
3. Caches the resulting access token (keyed by user ID, with TTL)
4. Returns the access token for MCP servers

## Files to modify

### 1. `ansible_ai_connect/ai/api/views.py`

- Add `_get_gateway_access_token(user)` function near `get_mcp_headers`
- Replace the `_AUTH_ACCESS` plain dict with Django's cache framework
- Update `get_mcp_headers` to call the new function for `"mcp-server"` type servers

The function (~40 lines):

```python
from django.core.cache import cache
from social_django.models import UserSocialAuth

def _get_gateway_access_token(user) -> str | None:
    cache_key = f"mcp_gateway_token_{user.id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        social = UserSocialAuth.objects.get(
            user=user,
            provider=USER_SOCIAL_AUTH_PROVIDER_AAP,
        )
    except UserSocialAuth.DoesNotExist:
        return None

    refresh_token = social.extra_data.get("refresh_token")
    if not refresh_token:
        return None

    resp = requests.post(
        f"{settings.AAP_API_URL}/o/token/",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.SOCIAL_AUTH_AAP_KEY,
            "client_secret": settings.SOCIAL_AUTH_AAP_SECRET,
        },
    )
    if resp.status_code != 200:
        logger.warning("Gateway token exchange failed: %s", resp.status_code)
        return None

    token_data = resp.json()
    access_token = token_data["access_token"]

    # Cache with buffer before expiry (default 10 min before)
    expires_in = max(token_data.get("expires_in", 3600) - 600, 60)
    cache.set(cache_key, access_token, timeout=expires_in)

    # Update stored refresh token if rotated
    new_refresh = token_data.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        social.extra_data["refresh_token"] = new_refresh
        social.save(update_fields=["extra_data"])

    return access_token
```

Then update `get_mcp_headers`:

```python
@staticmethod
def get_mcp_headers(request, config):
    mcp_headers = {}
    jwt_header_name = "X-DAB-JW-TOKEN"
    token = request.headers.get(jwt_header_name, None)
    user = request.user
    if token and user.is_authenticated and user.aap_user and config.mcp_servers:
        gateway_token = _get_gateway_access_token(user)
        for mcp_server in config.mcp_servers:
            if mcp_server["type"] == "mcp-server" and gateway_token:
                mcp_headers[mcp_server["name"]] = {
                    "Authorization": f"Bearer {gateway_token}"
                }
            elif mcp_server["type"] in ["controller", "eda", "hub", "lightspeed"]:
                mcp_headers[mcp_server["name"]] = {jwt_header_name: token}
    return mcp_headers
```

### 2. Remove `_AUTH_ACCESS` dict

Delete the `_AUTH_ACCESS = {}` module-level dict (from PR #2049) since
we're using Django's cache framework instead.

## What this does NOT need

- No new URL endpoint (the exchange happens internally in `get_mcp_headers`)
- No new Django app or model
- No changes to Gateway
- No cookie/CSRF forwarding
- No 302 redirect handling

## Line count

The `_get_gateway_access_token` function is ~35 lines. The `get_mcp_headers`
update is ~12 lines. Total: ~47 lines of new code.

## Limitations (POC scope)

- Only works for on-prem deployments where users log in via AAP OAuth2
  (not SaaS/RHSSO or upstream/GitHub)
- Depends on the refresh token being valid — if the user's Gateway session
  expired and the refresh token is revoked, this returns None
- The `requests.post` call should use TLS verification in production
  (not `verify=False`)

## Verification

1. Log in via AAP OAuth2 (on-prem mode)
2. Send a chat message that triggers an MCP server tool call
3. Verify the MCP server receives `Authorization: Bearer <gateway-token>`
4. Verify the MCP server can call Gateway APIs with the token
