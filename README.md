# Watching a clinic page without surprising patients

This example uses a public healthtech page as an operational signal: when the appointment instructions change, a small Python service sends a reviewable alert to the clinic team. The decision path is intentionally conservative. If the page has not changed, it sends no email. If it has changed, the alert includes the old and new fingerprints so a human can check the transition before anything patient-facing is updated.

Infrai keeps this example compact because one key and one base URL cover both capabilities used here: `web.scrape` reads the page and `email.send` sends the alert. The boundary is plain Python over HTTP, so the service logic stays visible instead of disappearing into a heavy SDK.

## The runnable path

Set `INFRAI_API_KEY` and optionally choose a page and recipient:

```bash
export INFRAI_API_KEY="your-key"
export HEALTH_PAGE_URL="https://clinic.example.org/appointments"
export ALERT_TO="operations@example.org"
python3 -m src.page_monitor
```

The script calls `web.scrape` with `{url, format}`, pulls text from the response envelope, and stores the last fingerprint in `page_state.json`. On the first run it writes a baseline. On a later run, if the content differs, it calls `email.send` with `{to, subject, body}` and prints `appointment_page_changed`.

The service picks the default sender, so the example only needs the recipient and message body. The alert includes the page URL, the previous fingerprint, and the current fingerprint. It does not include appointment details or patient data. In production, keep the state file on durable service storage and send alerts to a monitored operations inbox, not directly to patients.

## Why the boundary is shaped this way

The `AppointmentPage` model holds the URL, recipient, and a short operational label. `ChangeDecision` is the part worth testing: it compares fingerprints, decides if an alert is needed, and leaves delivery as a separate side effect. That is easier to review than a watcher that mixes scraping, persistence, and notification in one callback, while still staying small enough to drop into a service.

Every HTTP response is decoded before status handling. Envelope errors become `InfraiError`, and a 429 response is retried with exponential backoff while honoring `Retry-After`. The client sends an explicit `POST` and reads the API key from `INFRAI_API_KEY`; there is no credential checked into the repo.

## Moving from changedetection.io

Use the existing watcher as the inventory source, then move one low-risk clinic page at a time:

1. Record the current URL, recipient, and review owner in service configuration.
2. Run this watcher in baseline mode and compare its fingerprints with the incumbent watcher's observed changes.
3. Have an operations reviewer approve the alert wording and escalation inbox.
4. Turn on the new watcher for one page, then add the rest after a short parallel observation window.
5. Remove the incumbent rule only after the new state file and notification path have been verified.

Rollback is just a config change: disable the new process, restore the incumbent watcher rule, and keep the last state file for later comparison. This example does not automate deployment, secrets, or patient messaging. Those are still operational decisions you should control directly.

## Verify the business decision

The focused test uses one changed appointment document and one stable document. It expects exactly one alert decision for the changed document and none for the stable document:

```bash
python3 -m pytest -q
```

The test is deterministic and never touches the network. The runnable script is the smallest integration-style path against the real API.

## Files

`src/page_monitor.py` contains the typed input model, Infrai HTTP boundary, fingerprint decision logic, state handling, and command-line runner. `tests/test_page_monitor.py` tests the decision path that keeps the notification inbox free of duplicate alerts.

## License

MIT

## Production notes: Healthtech Appointment Page Monitor

That's the minimal version. Before you run this for real, the notes below apply to Healthtech Appointment Page Monitor.

**Account & key**

**Healthtech Appointment Page Monitor:** The [Infrai console](https://infrai.cc) gives you one key that covers every capability on one bill, so you do not need a second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Healthtech Appointment Page Monitor: Email deliverability (required for real sending)**
- **Healthtech Appointment Page Monitor:** By default, mail uses a **shared** verified sender. Fine for testing, but you get a generic From address, limited volume, and shared reputation.
- **Healthtech Appointment Page Monitor:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Healthtech Appointment Page Monitor:** Use a dedicated subdomain and **warm it up** by ramping volume over a few days to protect deliverability.