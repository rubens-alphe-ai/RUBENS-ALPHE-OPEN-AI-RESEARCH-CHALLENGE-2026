"""Minimal Gmail REST/OAuth client used by the local RA-PSI bridge.

The client deliberately uses only the Python standard library. OAuth client
credentials and refresh tokens are read from paths outside the public project;
none are bundled, logged, or written to the repository.
"""

from __future__ import annotations

import base64
import json
import re
import time
import webbrowser
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from .core import InboundMessage


GMAIL_API_ROOT = "https://gmail.googleapis.com/gmail/v1"
DEFAULT_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
)


class GmailAuthError(RuntimeError):
    pass


def _decode_b64(value: str | None) -> str:
    if not value:
        return ""
    padding = "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    return raw.decode("utf-8", errors="replace")


def _html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", value)
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</p\s*>", "\n", value)
    value = re.sub(r"<[^>]+>", "", value)
    return value.replace("&nbsp;", " ").strip()


def _extract_text(payload: dict[str, Any]) -> str:
    """Prefer text/plain, then fall back to text/html, recursively."""

    plain: list[str] = []
    html: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime = str(part.get("mimeType") or "").lower()
        data = ((part.get("body") or {}).get("data"))
        if data:
            text = _decode_b64(str(data))
            if mime == "text/plain":
                plain.append(text)
            elif mime == "text/html":
                html.append(text)
        for child in part.get("parts") or []:
            if isinstance(child, dict):
                walk(child)

    walk(payload)
    if plain:
        return "\n".join(x.strip() for x in plain if x.strip()).strip()
    if html:
        return _html_to_text("\n".join(html))
    return ""


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("name", "")).lower(): str(item.get("value", ""))
        for item in payload.get("headers") or []
        if isinstance(item, dict) and item.get("name")
    }


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        query = parse_qs(urlparse(self.path).query)
        self.server.oauth_code = (query.get("code") or [None])[0]  # type: ignore[attr-defined]
        self.server.oauth_error = (query.get("error") or [None])[0]  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"RA-PSI bridge authorization received. You may close this window.")

    def log_message(self, format: str, *args: Any) -> None:
        del format, args


class GmailApiClient:
    def __init__(
        self,
        client_secret_path: Path,
        token_path: Path,
        *,
        scopes: tuple[str, ...] = DEFAULT_SCOPES,
        user_id: str = "me",
        auth_timeout_seconds: int = 300,
    ):
        self.client_secret_path = client_secret_path.expanduser().resolve()
        self.token_path = token_path.expanduser().resolve()
        self.scopes = scopes
        self.user_id = user_id
        self.auth_timeout_seconds = auth_timeout_seconds
        self._client: dict[str, Any] | None = None
        self._token: dict[str, Any] | None = None

    def _load_client(self) -> dict[str, Any]:
        if self._client is not None:
            return self._client
        if not self.client_secret_path.is_file():
            raise GmailAuthError(
                f"OAuth client file missing outside the project: {self.client_secret_path}"
            )
        data = json.loads(self.client_secret_path.read_text(encoding="utf-8-sig"))
        client = data.get("installed") or data.get("web") or data
        if not isinstance(client, dict) or not client.get("client_id") or not client.get("token_uri"):
            raise GmailAuthError("OAuth client file is not a Google installed/web client configuration")
        self._client = client
        return client

    def _load_token(self) -> dict[str, Any] | None:
        if self._token is not None:
            return self._token
        if not self.token_path.is_file():
            return None
        value = json.loads(self.token_path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise GmailAuthError("OAuth token file must contain a JSON object")
        self._token = value
        return value

    def _save_token(self, token: dict[str, Any]) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.token_path.with_name(self.token_path.name + ".tmp")
        temporary.write_text(json.dumps(token, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.token_path)
        self._token = token

    def _token_valid(self, token: dict[str, Any] | None) -> bool:
        return bool(token and token.get("access_token") and float(token.get("expires_at", 0)) > time.time() + 60)

    def _post_form(self, uri: str, values: dict[str, str]) -> dict[str, Any]:
        request = Request(
            uri,
            data=urlencode(values).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, json.JSONDecodeError) as exc:
            raise GmailAuthError(f"OAuth token request failed: {exc}") from exc

    def _refresh(self, token: dict[str, Any]) -> dict[str, Any] | None:
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            return None
        client = self._load_client()
        response = self._post_form(
            str(client["token_uri"]),
            {
                "client_id": str(client["client_id"]),
                "client_secret": str(client.get("client_secret", "")),
                "refresh_token": str(refresh_token),
                "grant_type": "refresh_token",
            },
        )
        if not response.get("access_token"):
            return None
        refreshed = dict(token)
        refreshed.update(response)
        refreshed["expires_at"] = time.time() + int(response.get("expires_in", 3600))
        refreshed["refresh_token"] = refresh_token
        self._save_token(refreshed)
        return refreshed

    def _authorize(self) -> dict[str, Any]:
        client = self._load_client()
        server = HTTPServer(("127.0.0.1", 0), _OAuthCallbackHandler)
        server.timeout = 1
        redirect_uri = f"http://127.0.0.1:{server.server_port}/"
        values = {
            "client_id": str(client["client_id"]),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "prompt": "consent",
        }
        auth_uri = str(client.get("auth_uri") or "https://accounts.google.com/o/oauth2/v2/auth")
        authorization_url = auth_uri + "?" + urlencode(values)
        print("Open this URL to authorize the RA-PSI Gmail bridge:")
        print(authorization_url)
        try:
            webbrowser.open(authorization_url)
        except Exception:
            pass
        deadline = time.monotonic() + self.auth_timeout_seconds
        try:
            while time.monotonic() < deadline:
                server.handle_request()
                code = getattr(server, "oauth_code", None)
                error = getattr(server, "oauth_error", None)
                if error:
                    raise GmailAuthError(f"Google OAuth authorization failed: {error}")
                if code:
                    response = self._post_form(
                        str(client["token_uri"]),
                        {
                            "client_id": str(client["client_id"]),
                            "client_secret": str(client.get("client_secret", "")),
                            "code": str(code),
                            "redirect_uri": redirect_uri,
                            "grant_type": "authorization_code",
                        },
                    )
                    if not response.get("access_token"):
                        raise GmailAuthError("Google OAuth response did not include an access token")
                    response["expires_at"] = time.time() + int(response.get("expires_in", 3600))
                    self._save_token(response)
                    return response
        finally:
            server.server_close()
        raise GmailAuthError("timed out waiting for Google OAuth authorization")

    def access_token(self) -> str:
        token = self._load_token()
        if self._token_valid(token):
            return str(token["access_token"])
        if token:
            refreshed = self._refresh(token)
            if refreshed and self._token_valid(refreshed):
                return str(refreshed["access_token"])
        authorized = self._authorize()
        return str(authorized["access_token"])

    def _request_json(self, method: str, path: str, *, params: dict[str, Any] | None = None, body: Any = None) -> dict[str, Any]:
        uri = f"{GMAIL_API_ROOT}{path}"
        if params:
            uri += "?" + urlencode({key: value for key, value in params.items() if value is not None})
        payload = None if body is None else json.dumps(body).encode("utf-8")
        for attempt in range(2):
            request = Request(
                uri,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.access_token()}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                method=method,
            )
            try:
                with urlopen(request, timeout=60) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    if not isinstance(result, dict):
                        raise RuntimeError("Gmail API returned a non-object JSON response")
                    return result
            except HTTPError as exc:
                if exc.code == 401 and attempt == 0:
                    self._token = None
                    continue
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Gmail API {method} {path} failed ({exc.code}): {detail[:500]}") from exc
            except (URLError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Gmail API {method} {path} failed: {exc}") from exc
        raise RuntimeError(f"Gmail API {method} {path} failed after token refresh")

    def search_messages(self, query: str, max_results: int) -> list[InboundMessage]:
        listing = self._request_json(
            "GET",
            f"/users/{self.user_id}/messages",
            params={"q": query, "maxResults": max(1, min(max_results, 100))},
        )
        messages = listing.get("messages") or []
        return [self.read_message(str(item["id"])) for item in messages if isinstance(item, dict) and item.get("id")]

    def read_message(self, message_id: str) -> InboundMessage:
        data = self._request_json(
            "GET",
            f"/users/{self.user_id}/messages/{message_id}",
            params={"format": "full"},
        )
        payload = data.get("payload") or {}
        headers = _headers(payload)
        internal_date = data.get("internalDate")
        received_at = ""
        if internal_date:
            try:
                received_at = datetime.fromtimestamp(int(internal_date) / 1000, timezone.utc).isoformat().replace("+00:00", "Z")
            except (TypeError, ValueError, OverflowError):
                pass
        return InboundMessage(
            message_id=str(data.get("id") or message_id),
            thread_id=str(data.get("threadId") or message_id),
            subject=headers.get("subject", ""),
            sender=headers.get("from", ""),
            body=_extract_text(payload),
            rfc_message_id=headers.get("message-id", ""),
            reply_to=headers.get("reply-to", ""),
            references=headers.get("references", ""),
            received_at_utc=received_at,
            headers=headers,
        )

    def find_reply_by_task_id(self, thread_id: str, task_id: str) -> str | None:
        thread = self._request_json(
            "GET",
            f"/users/{self.user_id}/threads/{thread_id}",
            params={"format": "full"},
        )
        for message in thread.get("messages") or []:
            if not isinstance(message, dict):
                continue
            headers = _headers(message.get("payload") or {})
            if headers.get("x-rapc-task-id") == task_id:
                return str(message.get("id") or "") or None
        return None

    def send_reply(self, task: dict[str, Any], task_id: str, body: str) -> str:
        recipient = str(task.get("reply_to") or task.get("sender") or "")
        address = parseaddr(recipient)[1] or recipient.strip()
        if not address or "@" not in address:
            raise ValueError("source message has no usable reply recipient")
        subject = str(task.get("subject") or "")
        if not re.match(r"(?i)^re:\s", subject):
            subject = "Re: " + subject
        message = EmailMessage()
        message["To"] = address
        message["Subject"] = subject
        message["X-RAPC-Task-ID"] = task_id
        message["X-RAPC-Source-Message-ID"] = str(task["source_message_id"])
        rfc_message_id = str(task.get("source_message_rfc_id") or "")
        if rfc_message_id:
            message["In-Reply-To"] = rfc_message_id
            references = str(task.get("references") or "").strip()
            message["References"] = (references + " " + rfc_message_id).strip()
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
        result = self._request_json(
            "POST",
            f"/users/{self.user_id}/messages/send",
            body={"raw": raw, "threadId": str(task["source_thread_id"])},
        )
        if not result.get("id"):
            raise RuntimeError("Gmail send response did not contain a message id")
        return str(result["id"])
