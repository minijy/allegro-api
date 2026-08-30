# Device Application Onboarding

## Production prerequisites

1. Use an active Allegro account and enable two-step verification.
2. Open [Allegro Developer Apps](https://apps.developer.allegro.pl/), accept the REST API terms, and create a new application.
3. Select the application type described as operating without browser or keyboard access. Application type cannot be changed after registration.
4. Choose a clear application name because users see it on the consent screen. Select only required scopes.
5. Store the resulting Client ID and Client Secret in a secrets manager. Do not distribute these credentials to sellers or embed the secret in public client binaries.
6. Register and validate the required User-Agent in Allegro's [User-Agent tool](https://apps.developer.allegro.pl/user-agent). Use `ApplicationName/Version (+https://support-or-info-url)`.

Allegro currently allows up to five application keys on one account and expects customers of one integration to authorize that integration's application rather than create separate client credentials.

## Sandbox first

- Manage sandbox applications at [Developer Apps Sandbox](https://apps.developer.allegro.pl.allegrosandbox.pl/).
- Sandbox login/OAuth host: `https://allegro.pl.allegrosandbox.pl`.
- Sandbox API host: `https://api.allegro.pl.allegrosandbox.pl`.
- Sandbox credentials and tokens are distinct from production. Do not infer environment from a JWT or retry a token against another host.
- Sandbox does not require two-step verification and supports core listing, purchase, rating, and simulated-payment workflows.

## Environment matrix

| Purpose | Production | Sandbox |
|---|---|---|
| Device code | `https://allegro.pl/auth/oauth/device` | `https://allegro.pl.allegrosandbox.pl/auth/oauth/device` |
| Token | `https://allegro.pl/auth/oauth/token` | `https://allegro.pl.allegrosandbox.pl/auth/oauth/token` |
| REST API | `https://api.allegro.pl` | `https://api.allegro.pl.allegrosandbox.pl` |
| App management | `https://apps.developer.allegro.pl` | `https://apps.developer.allegro.pl.allegrosandbox.pl` |

Authorization resources live on the Allegro web host, not the API host.

## Production checklist

- Confirm app name, support URL, scopes, privacy/retention terms, and seller consent language.
- Verify tokens are partitioned by environment, application, and Allegro account.
- Confirm token encryption, key rotation, access audit, backup policy, and re-authorization workflow.
- Test denial, expiration, invalid/used device code, refresh collision, revoked access, `401`, `403`, `429`, and transient `5xx`.
- Verify the endpoint and media type against [current REST API documentation](https://developer.allegro.pl/documentation).
- Check deprecations and [Allegro news](https://developer.allegro.pl/news) before releases.

Official references:

- [Getting started](https://developer.allegro.pl/tutorials/pierwsze-kroki-MRwYEoOq0im)
- [Authentication and authorization](https://developer.allegro.pl/tutorials/uwierzytelnianie-i-autoryzacja-zlq9e75GdIR)
- [Basic API conventions](https://developer.allegro.pl/tutorials/informacje-podstawowe-b21569boAI1)
- [REST API rules](https://developer.allegro.pl/rules)
