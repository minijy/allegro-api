---
name: allegro-api
description: Integrate, review, or troubleshoot Allegro REST API applications that authorize seller accounts with OAuth 2.0 Device Flow. Use for Allegro application registration, scopes, token rotation, offers, products, orders, payments, billing, shipments, returns, disputes, messages, event journals, sandbox testing, or API synchronization. Do not route Amazon, advertising-platform, or storefront scraping work here.
---

# Allegro API

Build Allegro seller integrations around a registered Device application and user-context OAuth tokens. Prefer direct JSON resources and event journals. Verify every operation's current media type, authorization type, scope, limits, and deprecation status in the official reference before implementation.

## Route the Task

- For account prerequisites, Device-app registration, production/sandbox hosts, and rollout, read [references/onboarding.md](references/onboarding.md).
- For Device Flow, polling errors, refresh-token rotation, token storage, and scopes, read [references/authentication.md](references/authentication.md) and use [scripts/allegro_api_client.py](scripts/allegro_api_client.py).
- For direct read APIs and business-domain selection, read [references/data-apis.md](references/data-apis.md).
- For mutations, synchronization, pagination, limits, idempotency, and operational safety, read [references/operations.md](references/operations.md).
- For runnable commands and Python integration patterns, read [references/code-examples.md](references/code-examples.md).

## Establish the Boundary

Confirm before implementation:

1. Production or Allegro Sandbox; credentials and tokens never cross environments.
2. One seller, multiple sellers under one application, or a locally installed instance.
3. Required marketplaces and `Accept-Language`; do not equate marketplace with API host.
4. Read-only or mutation requirements and the smallest matching scopes.
5. Required domains: profile, offers/products, sale settings, orders, billing, payments, shipments, returns, disputes, messages, ratings, campaigns, or fulfillment.
6. Initial import, event-driven incremental sync, and reconciliation cadence.
7. Secret-vault ownership and atomic refresh-token rotation.
8. Whether the endpoint requires a user token or application token. Device Flow produces a user-context token.

Do not ask customers to create applications or provide their Client ID/Client Secret. Allegro expects an integration to use its own registered application credentials and authorize each user through OAuth.

## Core Workflow

1. Register a separate Device application in the matching environment and configure only required scopes.
2. Start Device Flow with `POST /auth/oauth/device`, Basic client authentication, `client_id`, and an optional least-privilege scope set.
3. Present `verification_uri_complete` and the formatted user code; never expose `device_code` as a user credential.
4. Poll the token endpoint no faster than `interval`, stop at `expires_in`, handle terminal denial/invalid-code states, and make one successful redemption only.
5. Store the returned token pair under the authorized Allegro account identity. Reuse the access token until near expiry; do not create a new Device session per API request.
6. Rotate refresh tokens atomically. A successful refresh returns a new access/refresh pair; prevent concurrent refresh workers from overwriting the newest token.
7. Call the production or sandbox API with Bearer authorization, the operation's documented `Accept` media type, and the registered application User-Agent.
8. Use event journals for low-latency changes, persist cursors only after durable processing, and reconcile against list/detail resources.
9. Bound retries for `429` and transient `5xx`; never blindly retry non-idempotent mutations.
10. Validate reads and authorized mutations in Sandbox before production rollout.

## Data Rules

- Treat all resource identifiers as strings even when they look numeric.
- Parse API date-times as ISO 8601 UTC and convert to local time only for display.
- Store price amount as a decimal string together with ISO 4217 currency.
- Preserve unknown enum values and nullable fields; Allegro can add response fields.
- Follow each endpoint's offset, cursor, event-ID, or asynchronous-command pagination model.
- Store seller/account, environment, marketplace, operation, request correlation data, cursor/window, and retrieval time.
- Never log Client Secret, access token, refresh token, device code, buyer personal data, message contents, or shipping details.

## Script Usage

```bash
export ALLEGRO_CLIENT_ID='...'
export ALLEGRO_CLIENT_SECRET='...'
export ALLEGRO_USER_AGENT='YourRegisteredApp/1.0.0 (+https://example.com/app-info)'

python3 scripts/allegro_api_client.py authorize \
  --scope allegro:api:orders:read \
  --scope allegro:api:sale:offers:read \
  --show-token

export ALLEGRO_ACCESS_TOKEN='...'
python3 scripts/allegro_api_client.py get --path /me
```

Use `--sandbox` from the beginning of an authorization session through every later token and API call. The helper sends token parameters in POST bodies, never in token-endpoint query strings. It does not persist credentials; `--show-token` is an explicit secret-display action.

## Required Design or Review Output

- Environment, application owner/type, authorized accounts, marketplaces, and User-Agent.
- Endpoint inventory with method, path, media type, user/application token type, scopes, pagination, and mutation class.
- Device-session state machine and user-facing verification instructions.
- Encrypted token schema, expiry policy, atomic refresh rotation, revocation/re-authorization path, and tenant isolation.
- Initial import, event cursors, deduplication, gap detection, reconciliation, and retention.
- Rate-limit/concurrency policy, idempotency keys or command IDs, retry matrix, and audit logging.
- Sandbox test evidence and a deliberate production enablement plan.

## Authorization Boundary

Documentation, local code generation, offline tests, and read-only Sandbox calls are ordinary implementation work. Do not publish/edit/end offers, alter stock or price, change order fulfillment, create/cancel shipments, issue refunds, send messages, reject returns, or perform other production mutations without explicit authorization for that action. Device authorization grants API capability; it does not itself authorize a particular business mutation.

## Exclusions

- Allegro Ads and external advertising systems require separate API analysis.
- Browser automation or Seller Center scraping is not a substitute for Allegro REST API.
- Authorization Code, client credentials, and DCR are adjacent flows, but this Skill defaults to Device Flow unless the user requests another flow.
