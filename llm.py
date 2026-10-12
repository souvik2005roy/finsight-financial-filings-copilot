"""Gemini OpenAI-compatible wrapper with bounded retries and quota fail-fast."""
import os
import re
import time
from typing import Optional

from openai import APIStatusError, OpenAI

MODEL = os.getenv("LLM_MODEL", "gemini-3.8-flash")
MIN_INTERVAL_SECONDS = float(os.getenv("LLM_MIN_INTERVAL_SECONDS", "13"))
MAX_AUTOMATIC_RETRY_WAIT_SECONDS = float(
    os.getenv("LLM_MAX_AUTOMATIC_RETRY_WAIT_SECONDS", "30")
)
MAX_RETRIES = 2

_client: Optional[OpenAI] = None
_last_request_started: Optional[float] = None
_blocked_reason: Optional[str] = None


def _get_client() -> OpenAI:
    global _client

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "LLM_API_KEY is not set. Configure it in this PowerShell session."
        )

    if _client is None:
        _client = OpenAI(
            api_key=api_key,
            base_url=os.getenv(
                "LLM_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
            max_retries=0,
            timeout=60.0,
        )
    return _client


def _response_body(error: APIStatusError) -> str:
    try:
        return error.response.text or ""
    except Exception:
        return str(error)


def _requested_delay(error: APIStatusError) -> Optional[float]:
    """Extract server retry delay from headers/body without ever sleeping blindly."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) or {}

    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except (TypeError, ValueError):
            pass

    body = _response_body(error)
    match = re.search(r'"retryDelay"\s*:\s*"([\d.]+)s"', body)
    if match:
        try:
            return max(0.0, float(match.group(1)))
        except ValueError:
            pass
    match = re.search(r"Please retry in\s+([\d.]+)s", body, re.IGNORECASE)
    if match:
        try:
            return max(0.0, float(match.group(1)))
        except ValueError:
            pass
    return None


def _is_daily_or_exhausted_quota(body: str) -> bool:
    lowered = body.lower()
    return (
        "perday" in lowered
        or "requests per day" in lowered
        or "quota exhausted" in lowered
        or "limit: 0" in lowered
    )


def _wait_for_request_slot() -> None:
    global _last_request_started
    if _last_request_started is not None:
        elapsed = time.monotonic() - _last_request_started
        wait = MIN_INTERVAL_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
    _last_request_started = time.monotonic()


def ask_llm(prompt: str) -> str:
    """Call Gemini; cap automatic waits and stop sending calls when quota is blocked."""
    global _blocked_reason

    if _blocked_reason:
        raise RuntimeError(
            "Gemini requests are paused locally after a quota/rate-limit response. "
            + _blocked_reason
        )

    client = _get_client()

    for attempt in range(MAX_RETRIES + 1):
        _wait_for_request_slot()
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("The language model returned an empty response.")
            return content.strip()

        except APIStatusError as exc:
            body = _response_body(exc)
            if exc.status_code not in {429, 500, 502, 503, 504}:
                raise

            # Quota errors with long server delays should never put the user in a
            # multi-hour sleep. Mark the process as blocked to avoid more calls.
            if exc.status_code == 429:
                delay = _requested_delay(exc)
                if (
                    _is_daily_or_exhausted_quota(body)
                    or delay is not None
                    and delay > MAX_AUTOMATIC_RETRY_WAIT_SECONDS
                ):
                    wait_description = (
                        f"Server requested retry after {delay:.0f}s. "
                        if delay is not None else ""
                    )
                    _blocked_reason = (
                        wait_description
                        + "This is treated as a quota exhaustion; no more API calls "
                        "will be sent from this process. Check AI Studio's active "
                        "model/project quotas or wait for reset."
                    )
                    raise RuntimeError(_blocked_reason) from exc

            if attempt >= MAX_RETRIES:
                raise

            delay = _requested_delay(exc)
            if delay is None:
                delay = min(8.0, 2.0 ** attempt)
            if delay > MAX_AUTOMATIC_RETRY_WAIT_SECONDS:
                _blocked_reason = (
                    f"Server requested retry after {delay:.0f}s, above the configured "
                    f"automatic-wait cap of {MAX_AUTOMATIC_RETRY_WAIT_SECONDS:.0f}s. "
                    "No automatic retry will be attempted."
                )
                raise RuntimeError(_blocked_reason) from exc

            print(
                f"Gemini returned HTTP {exc.status_code}; "
                f"retrying in {delay:.0f}s (attempt {attempt + 2}/{MAX_RETRIES + 1})."
            )
            time.sleep(delay)

    raise RuntimeError("Gemini request failed after bounded retries.")
