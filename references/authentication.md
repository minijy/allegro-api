# Device Flow, Scopes, and Token Lifecycle

## Device Flow protocol

Start a session:

```http
POST https://allegro.pl/auth/oauth/device
Authorization: Basic base64(client_id:client_secret)
Content-Type: application/x-www-form-urlencoded

client_id=...&scope=allegro%3Aapi%3Aorders%3Aread
```

The response contains `device_code`, `user_code`, `verification_uri`, `verification_uri_complete`, `expires_in`, and `interval`. Prefer showing `verification_uri_complete`; also show a readable user code for fallback. Keep the device code private and bind the pending session to the initiating tenant/account-connection request.

Poll using POST body fields:

```http
POST https://allegro.pl/auth/oauth/token
Authorization: Basic base64(client_id:client_secret)
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:device_code&device_code=...
```

Never send token parameters in the query string. Allegro stopped supporting GET token generation and query-string token parameters in 2025.

### Polling state machine

| Result | Action |
|---|---|
| `200` token pair | Stop immediately; the device code is single-use |
| `authorization_pending` | Wait at least the current interval and poll again |
| `slow_down` | Increase the interval and continue within the original deadline |
| `access_denied` | Stop; tell the user authorization was declined |
| `Invalid device code` | Stop; the code is invalid or already consumed |
| deadline reached/other permanent `400` | Stop; create a new session only at the user's request |
| network/`5xx` | Bounded retry without violating the polling interval or deadline |

Use a monotonic timer for the deadline. Do not launch multiple pollers for one device code. Cancellation must stop polling promptly.

## Token lifecycle

- Access tokens are normally valid for about 12 hours; `expires_in` is authoritative.
- Refresh tokens have a rolling three-month lifetime. Each refresh returns a new access token and a new refresh token.
- After the first refresh, the old refresh token can still work for about 60 seconds. This overlap is for safe handover, not parallel refresh. Use a per-account lock or compare-and-swap version so a slower worker cannot restore an older token pair.
- Cache and reuse access tokens. Allegro rate-limits token creation per user and can return `429` for abnormal generation.
- Store token pair, token type, scopes, `expires_at`, environment, application identifier, Allegro account ID, token version, and timestamps under envelope encryption.
- Refresh shortly before expiry with jitter. On `401`, refresh once only if the token is plausibly expired; repeated `401` or invalid refresh requires re-authorization.
- Password/email changes, logout from all devices, seller blocks, removed app linkage, or exceeding active sessions can invalidate tokens early.

Refresh using `POST /auth/oauth/token` with Basic client authentication and body fields `grant_type=refresh_token&refresh_token=...`.

## Least-privilege scopes

Request a scope in Device Flow only if it was also enabled for the registered application. Omitting `scope` grants all scopes configured on the application; passing a narrower set grants only that subset.

| Domain | Read | Write/combined |
|---|---|---|
| Profile | `allegro:api:profile:read` | `allegro:api:profile:write` |
| Offers/products | `allegro:api:sale:offers:read` | `allegro:api:sale:offers:write` |
| Orders | `allegro:api:orders:read` | `allegro:api:orders:write` |
| Shipments | `allegro:api:shipments:read` | `allegro:api:shipments:write` |
| Billing | `allegro:api:billing:read` | — |
| Payments/refunds | `allegro:api:payments:read` | `allegro:api:payments:write` |
| Sale settings | `allegro:api:sale:settings:read` | `allegro:api:sale:settings:write` |
| One Fulfillment | `allegro:api:fulfillment:read` | `allegro:api:fulfillment:write` |
| Affiliate | `allegro:api:affiliate:read` | `allegro:api:affiliate:write` |
| Ratings | `allegro:api:ratings` | same combined scope |
| Disputes | `allegro:api:disputes` | same combined scope |
| Messaging | `allegro:api:messaging` | same combined scope |
| Bids | `allegro:api:bids` | same combined scope |
| Campaigns | `allegro:api:campaigns` | same combined scope |

Check the operation's current `Authorizations` and scope in [the official reference](https://developer.allegro.pl/documentation); this table is routing guidance, not a substitute for the operation contract.

## Tenant and secret safety

- Map the authorization back to the initiating tenant only after calling `GET /me` and recording the actual account identity.
- Prevent one tenant from supplying another tenant's token, cursor, order ID, or offer ID.
- Never decode JWTs on third-party websites; local decoding is diagnostic only and does not validate signature or authorization.
- Redact Basic authorization, bearer tokens, device codes, buyer data, and response bodies containing personal data.
- Do not email a device code or complete verification link unless that delivery channel and account-linking workflow were explicitly designed and authorized.

Official reference: [Authentication and authorization](https://developer.allegro.pl/tutorials/uwierzytelnianie-i-autoryzacja-zlq9e75GdIR).
