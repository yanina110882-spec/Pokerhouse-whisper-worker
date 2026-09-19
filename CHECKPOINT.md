# Checkpoint — 2026-09-19 — V3 first milestone

## Foundation verified
GitHub main base: 20deb6977c0834c61bc580537164dc3b467c568e.
V2 worker.py, requirements.txt, README.md, CHECKPOINT.md and Dockerfile present.
worker.py/requirements/Dockerfile unchanged; instagram_reel and caption/speech
separation preserved. No Instagram mass processing. Make 6245187 untouched.

## Implemented / tested
Direct getUpdates adapter, no webhook mutations; atomic raw-event + cursor
SQLite commit before AI (WAL/FULL); explicit group allowlist, all senders;
object-based media routing including captionless photo; WAITING_AI/backoff;
dedup updates/messages, preserve edits; source-linked history and unconfirmed
inference; evidence validation; private-owner-only delivery guard/outbox;
AMBIGUOUS handling for uncertain sends; process file locks; snapshot/restore;
code-only gitignore; separate Docker Compose persistent-volume definition.

12/12 local Python integration/contract tests PASS using synthetic Telegram
fixtures and fake provider/API. Database close/reopen recovery PASS. These are
NOT live Telegram, real AI/media, host reboot or Docker image tests.

## Acceptance
| Test | Current evidence |
|---|---|
| A reboot | NOT RUN |
| B other-member text | Synthetic PASS; live NOT RUN |
| C captionless photo | Synthetic routing PASS; live NOT RUN |
| D semantic photo | NOT RUN |
| E Russian ASR on server | NOT RUN |
| F document extraction | NOT RUN |
| G persist before AI | Synthetic integration PASS |
| H WAITING_AI outage | Synthetic integration PASS |
| I resumed after AI/reopen | Injected provider PASS |
| J dedup | Synthetic PASS |
| K ordinary-message silence | Fake provider PASS; real AI NOT RUN |
| L management synthesis | History plumbing PASS; actual quality NOT RUN |
| M no group sends | Guard PASS; deployment NOT RUN |
| N production cost zero | No paid calls; account/runtime NOT VERIFIED |

production_cutover_allowed = false
mass_processing_allowed = false

## Limits
No deployed host, real token access or live update. Default AI router waits.
Media remains WAITING_MEDIA; V2 integration not wired into durable queue yet.
Owner-send function not daemon-enabled. Remote encrypted backups not built.
Docker unavailable in development environment; images not built.
Oracle Cloud Console returned 502 Bad Gateway / Connection refused on initial
load and one reload, not a proven CAPTCHA/bot block. Official signup navigation and subsequent browser
state inspection timed out; no registration/login completed. Runtime review in
RUNTIME_REVIEW.md records official terms checked 2026-09-19.

## Next
Authenticate/verify non-upgraded Oracle Free Tier tenancy and Always Free
capacity/storage/billing restrictions. Owner completes registration/auth only
through secure browser interaction; never request secrets in chat. Deploy an
isolated test environment, prove real text durability, then wire V2 media/AI
and remote backup, complete acceptance before production cutover.

## Policy
No kitchen; non-alcoholic bar only. No work-group notifications. Publication,
spending, external account changes or messages to others require confirmation.
No paid fallback, trial dependency, Work/Make runtime dependency.

## Persistence blocker
Local commit prepared and tests passed. Git push had no shell credentials;
GitHub connector create_tree returned HTTP 403 Resource not accessible by
integration. Remote main remains unchanged. Owner must grant repository Contents
read/write access to the GitHub connection before code/checkpoint publication.
