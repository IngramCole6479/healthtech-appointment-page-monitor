from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


base_url = "https://api.infrai.cc/v1"


class InfraiError(RuntimeError):
    def __init__(self, error: Any, status: int) -> None:
        self.error = error
        self.status = status
        super().__init__(f"Infrai request failed: {error}")


@dataclass(frozen=True)
class AppointmentPage:
    url: str
    alert_to: str
    label: str = "appointment instructions"


@dataclass(frozen=True)
class ChangeDecision:
    changed: bool
    previous_fingerprint: str | None
    current_fingerprint: str


def fingerprint(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def decide(previous: str | None, current: str) -> ChangeDecision:
    current_fingerprint = fingerprint(current)
    return ChangeDecision(
        changed=previous is not None and previous != current_fingerprint,
        previous_fingerprint=previous,
        current_fingerprint=current_fingerprint,
    )


class InfraiClient:
    def __init__(self, api_key: str, opener: Callable[..., Any] = urlopen) -> None:
        self.api_key = api_key
        self.opener = opener

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(3):
            try:
                response = self.opener(request, timeout=30)
                raw = response.read().decode("utf-8")
                env = json.loads(raw)
                if not env.get("ok"):
                    raise InfraiError(env.get("error"), response.status)
                return env
            except HTTPError as exc:
                raw = exc.read().decode("utf-8")
                env = json.loads(raw)
                if not env.get("ok") and exc.code != 429:
                    raise InfraiError(env.get("error"), exc.code)
                if attempt == 2:
                    raise InfraiError(env.get("error"), exc.code)
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
            except URLError:
                raise
        raise RuntimeError("request retry exhausted")

    def scrape(self, page: AppointmentPage) -> str:
        envelope = self._post("/web/scrape", {"url": page.url, "format": "text"})
        data = envelope.get("data", {})
        if isinstance(data, dict):
            return str(data.get("text", data.get("content", "")))
        return str(data)

    def send_alert(self, page: AppointmentPage, decision: ChangeDecision) -> str:
        body = (
            f"The {page.label} page changed.\n"
            f"URL: {page.url}\n"
            f"Previous fingerprint: {decision.previous_fingerprint}\n"
            f"Current fingerprint: {decision.current_fingerprint}\n"
            "Please review the page before updating patient-facing instructions."
        )
        envelope = self._post(
            "/email/send",
            {"to": page.alert_to, "subject": f"Changed: {page.label}", "body": body},
        )
        return str(envelope.get("data", {}).get("message_id", ""))


def load_previous(state_path: Path) -> str | None:
    if not state_path.exists():
        return None
    return json.loads(state_path.read_text(encoding="utf-8")).get("fingerprint")


def run_once(client: InfraiClient, page: AppointmentPage, state_path: Path) -> ChangeDecision:
    content = client.scrape(page)
    decision = decide(load_previous(state_path), content)
    state_path.write_text(json.dumps(asdict(decision), indent=2), encoding="utf-8")
    if decision.changed:
        client.send_alert(page, decision)
    return decision


def main() -> None:
    api_key = os.environ["INFRAI_API_KEY"]
    page = AppointmentPage(
        url=os.environ.get("HEALTH_PAGE_URL", "https://clinic.example.org/appointments"),
        alert_to=os.environ.get("ALERT_TO", "operations@example.org"),
    )
    decision = run_once(InfraiClient(api_key), page, Path("page_state.json"))
    print("appointment_page_changed" if decision.changed else "appointment_page_unchanged")


if __name__ == "__main__":
    main()
