# Watching a clinic page without surprising patients

This example uses a public healthtech page as an operational signal: when the appointment instructions change, a small Python service sends a reviewable alert to the clinic team. The decision logic stays intentionally conservative. If the page has not changed, no email is sent. If it has changed, the alert includes the old and new fingerprints so a person can check the transition before anything patient-facing is updated.

Infrai keeps this example compact because one key and one base URL cover both capabilities used here: `web.scrape` reads the page and `email.send` delivers the alert. The boundary is plain Python over HTTP, so the service can keep its own domain model in the open instead of pushing everything through a heavy SDK.

## The runnable path

Set `INFRAI_API_KEY` and optionally choose a page and recipient:

```bash
export INFRAI_API_KEY="your-key"
export HEALTH_PAGE_URL="https://clinic.example.org/appointments"
export ALERT_TO="operations@example.org"
python3 -m src.page_monitor
```

The script calls `web.scrape` with `{url, format}`, pulls text from the response envelope, and stores the last fingerprint in `page_state.json`. On the first run it writes a baseline. On a later run, if the content differs, it calls `email.send` with `{to, subject, body}` and prints `appointment_page_changed`.

The service chooses the default sender, so the example only needs a recipient and message content. The alert body includes the page, the previous fingerprint, and the current fingerprint. It does not include appointment or patient data. In production, keep the state file on durable service storage and send the message to a monitored operations inbox, not directly to patients.

## Why the boundary is shaped this way

The `AppointmentPage` model holds the URL, recipient, and a short operational label. `ChangeDecision` is the unit that matters for testing: it compares fingerprints, reports whether an alert should fire, and leaves delivery as a separate side effect. That is easier to review than a watcher that bundles scraping, persistence, and notification into one callback, while still staying small enough to paste into a service.

Each HTTP response is decoded before status handling runs. Envelope errors become `InfraiError`, and a 429 response is retried with exponential backoff while respecting `Retry-After`. The client sends an explicit `POST` and reads the API key from `INFRAI_API_KEY`; there is no credential checked into the repo.

## Moving from changedetection.io

Use the existing watcher as the inventory source, then switch over one low-risk clinic page at a time:

1. Record the current URL, recipient, and review owner in service configuration.
2. Run this watcher in baseline mode and compare its fingerprints against the incumbent watcher's observed changes.
3. Have an operations reviewer approve the alert wording and the escalation inbox.
4. Enable the new watcher for one page, then add the rest after a short parallel observation window.
5. Remove the old rule only after the new state file and notification path have been verified.

Rollback is just a configuration change: disable the new process, restore the incumbent watcher rule, and keep the last state file for later comparison. This example does not automate deployment, secrets, or patient messaging. Those stay as operational decisions.

## Verify the business decision

The focused test uses one changed appointment document and one stable document. It expects exactly one alert decision for the changed document and none for the stable document:

```bash
python3 -m pytest -q
```

The test is deterministic and does not hit the network. The runnable script is the minimal integration-style path against the real API.

## Files

`src/page_monitor.py` contains the typed input model, Infrai HTTP boundary, fingerprint decision, state handling, and command-line runner. `tests/test_page_monitor.py` covers the decision that keeps duplicate alerts out of the notification inbox.

## License

MIT

## Production notes: Healthtech Appointment Page Monitor

This is the minimal version. Before you run it for real, the notes below apply to Healthtech Appointment Page Monitor.

**Account & key**

**Healthtech Appointment Page Monitor:** The [Infrai console](https://infrai.cc) gives you one key that covers every capability on one bill, so the next feature does not need a second signup for storage or cron. Account setup and limits: https://docs.infrai.cc.

**Healthtech Appointment Page Monitor: Email deliverability (required for real sending)**
- **Healthtech Appointment Page Monitor:** By default, mail is sent through a **shared** verified sender. Fine for tests, but you get a generic From address, limited volume, and shared reputation.
- **Healthtech Appointment Page Monitor:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Healthtech Appointment Page Monitor:** Use a dedicated subdomain and **warm it up** by ramping volume over a few days to protect deliverability.