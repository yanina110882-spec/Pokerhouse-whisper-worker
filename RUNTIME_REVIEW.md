# Runtime review — 2026-09-19

Official sources checked today. Free-tier terms can change: fail closed, never
upgrade/pay automatically, retain tasks. No account billing status is verified.

## Oracle first candidate
Current A1 allowance: 1,500 OCPU-hours/9,000 GB-hours monthly, equivalent to
2 OCPU/12 GB RAM (ARM64). Home-region only; capacity is not guaranteed.
200 GB boot/block storage, five volume backups, 20 GB object storage for
Always Free-only accounts, 10 TB monthly outbound transfer. Idle VM reclamation
can follow seven days of low utilization. Do not generate artificial load.
https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

Registration requires identity/card verification; temporary authorization holds
can occur. Use only non-upgraded Free Tier and Always Free resources, never trial
credits. Do not accept billing terms on behalf of the owner. No SLA exists;
free forever plus guaranteed uninterrupted 24/7 cannot honestly be promised.
Verify Console limits, tenancy plan and actual capacity before provisioning.
https://www.oracle.com/cloud/free/faq/
https://www.oracle.com/cloud/free/

Render Free sleeps after 15 minutes without inbound traffic and loses local
SQLite on restart/redeploy. Unsuitable for this poller/persistent DB design.
https://render.com/docs/free
Codespaces has idle timeout and finite allowances; hosted Actions jobs stop
after six hours. Neither is selected as a permanent runtime.
https://docs.github.com/en/codespaces/about-codespaces/understanding-the-codespace-lifecycle
https://docs.github.com/en/actions/reference/limits

## AI privacy/cost
Cloudflare Workers AI Free is a candidate: 10,000 neurons/day, higher use
requires Paid. Verify the actual Free account before enabling any adapter.
Cloudflare says it does not train on customer content without consent.
Model license and semantic-vision suitability still need review and testing.
https://developers.cloudflare.com/workers-ai/platform/pricing/
https://developers.cloudflare.com/workers-ai/platform/data-usage/
Gemini unpaid terms generally permit service improvement/human review and warn
against private/confidential data (EEA/UK/Swiss exceptions exist). Do not enable
it for this work-group data under unverified account/region conditions.
https://ai.google.dev/gemini-api/terms

## Backup design — remote implementation pending
SQLite online backup -> integrity check -> client-side authenticated encryption
-> private off-VM object bucket. Keys outside bucket/git. Proposed rotation:
24 hourly + 7 daily snapshots, hard aggregate storage cap below free allowance.
Restore into an isolated DB and verify cursor/integrity. Online snapshot/restore
is tested. Encryption/upload/schedule/retention/remote restore are NOT yet built.
First storage candidate is OCI Object Storage after tenancy verification.
No public URLs, GitHub artifacts or public backups.
https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/objectstorageoverview.htm

## Telegram
Webhook and getUpdates are exclusive; pending updates are held at most 24 hours.
A longer outage can lose events not yet received. Local durability applies after
SQLite commit; host-loss resilience requires deployed off-VM backup.
https://core.telegram.org/bots/api#getupdates
No production webhook change before acceptance. Use synthetic fixtures or an
isolated test bot first; same-bot testing requires controlled cutover/rollback.
