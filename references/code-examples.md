# Code Examples

## Environment

```bash
export ALLEGRO_CLIENT_ID='...'
export ALLEGRO_CLIENT_SECRET='...'
export ALLEGRO_USER_AGENT='YourRegisteredApp/1.0.0 (+https://example.com/app-info)'
```

Do not commit or print these values in CI logs. Production code should keep tokens in a tenant-partitioned encrypted store.

## Complete Device authorization

```bash
python3 scripts/allegro_api_client.py authorize \
  --scope allegro:api:profile:read \
  --scope allegro:api:orders:read \
  --scope allegro:api:sale:offers:read \
  --show-token
```

The helper prints the user-facing verification URL and code to stderr, waits according to Allegro's interval, and displays the token pair only because `--show-token` is explicit.

Use `--sandbox` with sandbox credentials for the entire sandbox authorization and API lifecycle.

## Split start and polling

```bash
python3 scripts/allegro_api_client.py device-start \
  --scope allegro:api:orders:read \
  --show-device-code

export ALLEGRO_DEVICE_CODE='...'
python3 scripts/allegro_api_client.py device-poll \
  --device-code-env ALLEGRO_DEVICE_CODE \
  --interval 5 \
  --expires-in 3600 \
  --show-token
```

Persist the pending session server-side under encryption and do not create two pollers for one device code.

## Refresh with rotation

```bash
export ALLEGRO_REFRESH_TOKEN='...'
python3 scripts/allegro_api_client.py refresh --show-token
```

Hold a per-account lock and atomically replace both tokens. The old refresh token's short overlap must not allow a late worker to overwrite the newest pair.

## Verify identity and call direct APIs

```bash
export ALLEGRO_ACCESS_TOKEN='...'

python3 scripts/allegro_api_client.py get --path /me

python3 scripts/allegro_api_client.py get \
  --path /order/checkout-forms \
  --query limit=100 \
  --query status=READY_FOR_PROCESSING

python3 scripts/allegro_api_client.py get \
  --path /sale/offers \
  --query limit=1000 \
  --query publication.status=ACTIVE
```

Override `--accept` only with the media type shown for the selected operation. Event consumers should advance their saved event ID only after all preceding events and fetched aggregate updates are durable.
