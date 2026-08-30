#!/usr/bin/env python3
"""Minimal Allegro Device Flow and read-only REST helper.

Uses only the Python standard library, never persists tokens, and accepts only
relative Allegro API paths so bearer tokens cannot be forwarded to arbitrary hosts.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import sys
import time
from email.utils import parsedate_to_datetime
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
DEFAULT_ACCEPT = "application/vnd.allegro.public.v1+json"
DEFAULT_TIMEOUT = 30.0
ENVIRONMENTS = {
    "production": {
        "auth": "https://allegro.pl",
        "api": "https://api.allegro.pl",
    },
    "sandbox": {
        "auth": "https://allegro.pl.allegrosandbox.pl",
        "api": "https://api.allegro.pl.allegrosandbox.pl",
    },
}
RETRYABLE_API_STATUSES = {429, 500, 502, 503, 504}
TERMINAL_DEVICE_ERRORS = {"access_denied", "invalid_device_code", "Invalid device code"}


class AllegroError(RuntimeError):
    def __init__(self, status: int | None, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


def environment(sandbox: bool) -> dict[str, str]:
    return ENVIRONMENTS["sandbox" if sandbox else "production"]


def client_authorization() -> str:
    raw = f"{required_env('ALLEGRO_CLIENT_ID')}:{required_env('ALLEGRO_CLIENT_SECRET')}"
    return "Basic " + base64.b64encode(raw.encode("utf-8")).decode("ascii")


def decode_json(raw: bytes, context: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AllegroError(None, f"{context} returned a non-JSON response") from error


def decode_object(raw: bytes, context: str) -> dict[str, Any]:
    value = decode_json(raw, context)
    if not isinstance(value, dict):
        raise AllegroError(None, f"{context} returned JSON that is not an object")
    return value


def retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
            return max(0.0, when.timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            return None


def oauth_post(
    path: str,
    form: list[tuple[str, str]],
    *,
    sandbox: bool,
    timeout: float,
) -> tuple[int, dict[str, Any], float | None]:
    url = environment(sandbox)["auth"] + path
    request = Request(
        url,
        data=urlencode(form).encode("utf-8"),
        headers={
            "Authorization": client_authorization(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, decode_object(response.read(), "Allegro OAuth"), None
    except HTTPError as error:
        body = decode_object(error.read(), "Allegro OAuth error")
        return error.code, body, retry_after_seconds(error.headers.get("Retry-After"))
    except URLError as error:
        raise AllegroError(None, f"Allegro OAuth request failed: {error.reason}") from error


def start_device(scopes: list[str], sandbox: bool, timeout: float) -> dict[str, Any]:
    form = [("client_id", required_env("ALLEGRO_CLIENT_ID"))]
    if scopes:
        form.append(("scope", " ".join(dict.fromkeys(scopes))))
    status, body, _ = oauth_post("/auth/oauth/device", form, sandbox=sandbox, timeout=timeout)
    if status != 200:
        raise AllegroError(status, oauth_message(body))
    required = {
        "device_code",
        "user_code",
        "verification_uri",
        "expires_in",
        "interval",
    }
    missing = sorted(required.difference(body))
    if missing:
        raise AllegroError(status, f"Device response is missing fields: {', '.join(missing)}")
    return body


def oauth_message(body: dict[str, Any]) -> str:
    error = body.get("error") or body.get("code") or "oauth_error"
    description = body.get("error_description") or body.get("message")
    return f"{error}: {description}" if description else str(error)


def poll_device(
    device_code: str,
    interval: float,
    expires_in: float,
    *,
    sandbox: bool,
    timeout: float,
) -> dict[str, Any]:
    if interval <= 0 or expires_in <= 0:
        raise ValueError("interval and expires_in must be positive")
    deadline = time.monotonic() + expires_in
    current_interval = interval
    consecutive_network_errors = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AllegroError(400, "Device authorization expired before completion")
        time.sleep(min(current_interval, remaining))
        if time.monotonic() >= deadline:
            raise AllegroError(400, "Device authorization expired before completion")

        try:
            status, body, retry_after = oauth_post(
                "/auth/oauth/token",
                [("grant_type", DEVICE_GRANT), ("device_code", device_code)],
                sandbox=sandbox,
                timeout=timeout,
            )
            consecutive_network_errors = 0
        except AllegroError as error:
            if error.status is not None:
                raise
            consecutive_network_errors += 1
            if consecutive_network_errors >= 4:
                raise
            current_interval = max(current_interval, min(30.0, 2**consecutive_network_errors))
            continue
        if status == 200:
            if not body.get("access_token") or not body.get("refresh_token"):
                raise AllegroError(status, "Token response is missing an access or refresh token")
            return body

        error_code = str(body.get("error") or body.get("code") or "")
        if error_code == "authorization_pending":
            continue
        if error_code == "slow_down":
            current_interval = max(current_interval + 5.0, retry_after or 0.0)
            continue
        if error_code in TERMINAL_DEVICE_ERRORS:
            raise AllegroError(status, oauth_message(body))
        if status >= 500:
            current_interval = max(current_interval, retry_after or 0.0)
            continue
        raise AllegroError(status, oauth_message(body))


def refresh_token(refresh: str, sandbox: bool, timeout: float) -> dict[str, Any]:
    status, body, _ = oauth_post(
        "/auth/oauth/token",
        [("grant_type", "refresh_token"), ("refresh_token", refresh)],
        sandbox=sandbox,
        timeout=timeout,
    )
    if status != 200:
        raise AllegroError(status, oauth_message(body))
    if not body.get("access_token") or not body.get("refresh_token"):
        raise AllegroError(status, "Refresh response is missing an access or refresh token")
    return body


def public_device_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_code": result["user_code"],
        "verification_uri": result["verification_uri"],
        "verification_uri_complete": result.get("verification_uri_complete"),
        "expires_in": int(result["expires_in"]),
        "interval": int(result["interval"]),
        "device_code": "<redacted; use --show-device-code to print>",
    }


def token_result(result: dict[str, Any], show_token: bool) -> dict[str, Any]:
    output = dict(result)
    for key in ("access_token", "refresh_token"):
        if key in output and not show_token:
            output[key] = "<redacted; use --show-token to print>"
    return output


def validate_path(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("--path must begin with one slash")
    if "://" in path or "\r" in path or "\n" in path or "?" in path:
        raise ValueError("--path must be a relative API path without URL, query, CR, or LF")
    return path


def parse_query(values: Iterable[str]) -> list[tuple[str, str]]:
    query: list[tuple[str, str]] = []
    for value in values:
        key, separator, item = value.partition("=")
        if not separator or not key:
            raise ValueError(f"Invalid --query value {value!r}; expected KEY=VALUE")
        query.append((key, item))
    return query


def api_get(args: argparse.Namespace) -> tuple[Any, dict[str, str | None]]:
    path = validate_path(args.path)
    query = urlencode(parse_query(args.query), doseq=True)
    url = environment(args.sandbox)["api"] + path + (("?" + query) if query else "")
    token = required_env(args.access_token_env)
    user_agent = required_env("ALLEGRO_USER_AGENT")

    for attempt in range(args.max_attempts):
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": args.accept,
                "User-Agent": user_agent,
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=args.timeout) as response:
                raw = response.read()
                body = {} if not raw else decode_json(raw, "Allegro API")
                metadata = {
                    "status": str(response.status),
                    "request_id": response.headers.get("x-request-id"),
                    "trace_id": response.headers.get("trace-id"),
                }
                return body, metadata
        except HTTPError as error:
            raw = error.read()
            try:
                body = decode_object(raw, "Allegro API error")
                message = json.dumps(body, ensure_ascii=False)
            except AllegroError:
                message = raw.decode("utf-8", errors="replace")[:4096]
            retry_after = retry_after_seconds(error.headers.get("Retry-After"))
            if error.code not in RETRYABLE_API_STATUSES or attempt + 1 >= args.max_attempts:
                raise AllegroError(error.code, message, retry_after) from error
            delay = retry_after if retry_after is not None else min(30.0, 0.5 * (2**attempt))
            time.sleep(delay + random.uniform(0.0, max(0.1, delay * 0.2)))
        except URLError as error:
            if attempt + 1 >= args.max_attempts:
                raise AllegroError(None, f"Allegro API request failed: {error.reason}") from error
            delay = min(30.0, 0.5 * (2**attempt))
            time.sleep(delay + random.uniform(0.0, max(0.1, delay * 0.2)))
    raise AllegroError(None, "Allegro API request failed without a terminal result")


def command_device_start(args: argparse.Namespace) -> None:
    result = start_device(args.scope, args.sandbox, args.timeout)
    output = public_device_result(result)
    if args.show_device_code:
        output["device_code"] = result["device_code"]
    print(json.dumps(output, ensure_ascii=False, indent=2))


def command_device_poll(args: argparse.Namespace) -> None:
    result = poll_device(
        required_env(args.device_code_env),
        args.interval,
        args.expires_in,
        sandbox=args.sandbox,
        timeout=args.timeout,
    )
    print(json.dumps(token_result(result, args.show_token), ensure_ascii=False, indent=2))


def command_authorize(args: argparse.Namespace) -> None:
    device = start_device(args.scope, args.sandbox, args.timeout)
    verification = device.get("verification_uri_complete") or device["verification_uri"]
    print(f"Open: {verification}", file=sys.stderr)
    print(f"User code: {device['user_code']}", file=sys.stderr)
    print(f"Authorization expires in {int(device['expires_in'])} seconds.", file=sys.stderr)
    result = poll_device(
        str(device["device_code"]),
        float(device["interval"]),
        float(device["expires_in"]),
        sandbox=args.sandbox,
        timeout=args.timeout,
    )
    print(json.dumps(token_result(result, args.show_token), ensure_ascii=False, indent=2))


def command_refresh(args: argparse.Namespace) -> None:
    result = refresh_token(required_env(args.refresh_token_env), args.sandbox, args.timeout)
    print(json.dumps(token_result(result, args.show_token), ensure_ascii=False, indent=2))


def command_get(args: argparse.Namespace) -> None:
    result, metadata = api_get(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.show_metadata:
        print(json.dumps(metadata, ensure_ascii=False), file=sys.stderr)


def add_environment(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sandbox", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Allegro Device Flow and read-only REST helper")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("device-start", help="Create a Device Flow session")
    start.add_argument("--scope", action="append", default=[])
    start.add_argument("--show-device-code", action="store_true", help="Print the private device code")
    add_environment(start)
    start.set_defaults(handler=command_device_start)

    poll = subparsers.add_parser("device-poll", help="Poll an existing Device Flow session")
    poll.add_argument("--device-code-env", default="ALLEGRO_DEVICE_CODE")
    poll.add_argument("--interval", type=float, required=True)
    poll.add_argument("--expires-in", type=float, required=True)
    poll.add_argument("--show-token", action="store_true", help="Print secret tokens")
    add_environment(poll)
    poll.set_defaults(handler=command_device_poll)

    authorize = subparsers.add_parser("authorize", help="Start and complete Device Flow")
    authorize.add_argument("--scope", action="append", default=[])
    authorize.add_argument("--show-token", action="store_true", help="Print secret tokens")
    add_environment(authorize)
    authorize.set_defaults(handler=command_authorize)

    refresh = subparsers.add_parser("refresh", help="Rotate an Allegro refresh token")
    refresh.add_argument("--refresh-token-env", default="ALLEGRO_REFRESH_TOKEN")
    refresh.add_argument("--show-token", action="store_true", help="Print secret tokens")
    add_environment(refresh)
    refresh.set_defaults(handler=command_refresh)

    get = subparsers.add_parser("get", help="Call a read-only Allegro REST resource")
    get.add_argument("--path", required=True)
    get.add_argument("--query", action="append", default=[], metavar="KEY=VALUE")
    get.add_argument("--accept", default=DEFAULT_ACCEPT)
    get.add_argument("--access-token-env", default="ALLEGRO_ACCESS_TOKEN")
    get.add_argument("--max-attempts", type=int, default=4)
    get.add_argument("--show-metadata", action="store_true")
    add_environment(get)
    get.set_defaults(handler=command_get)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "max_attempts", 1) < 1:
        parser.error("--max-attempts must be at least 1")
    try:
        args.handler(args)
    except KeyboardInterrupt:
        print("error: authorization cancelled", file=sys.stderr)
        return 130
    except (ValueError, AllegroError) as error:
        status = f" HTTP {error.status}" if isinstance(error, AllegroError) and error.status else ""
        print(f"error:{status} {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
