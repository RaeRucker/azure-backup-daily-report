# Daily Azure Backup Report

A Logic App that emails a backup health report every morning at 6 AM Eastern. I built it and it runs in production.

[`logic-app/workflow.json`](logic-app/workflow.json) is the workflow exported from code view. Names, recipients, IDs and the company logo are stripped out, and the logic, queries and layout are untouched.

## Why I built it

Microsoft's built-in backup report email gives you charts and CSVs, but it doesn't answer the questions people actually ask. Is everything protected? What failed? Is every vault set up the way it should be? Are the databases covered?

I started from Microsoft's [Azure Backup report email template](https://aka.ms/AzureBackupReportEmail) and built my own report on top of it. The HTML layout is mine, and so are the new sections that query Resource Graph and the ARM API directly.

## What's in the email

| # | Section | Where the data comes from |
|---|---|---|
| 01 | Summary of protected, failed and stale items by workload type | Log Analytics and Resource Graph |
| 02 | Failed backup jobs | Log Analytics |
| 03 | Which systems are on each backup policy, with the policy settings | Resource Graph |
| 04 | Vault health covering redundancy, immutability, soft delete, cross region restore and missing tier policies | Resource Graph |
| 05 | PostgreSQL backups and Azure SQL short and long term retention | Resource Graph and the ARM API |
| 06 | Backup storage trend per vault | Log Analytics |
| 07 | Storage growth per vault so far this month | Log Analytics |

It also attaches CSVs for the job list, policy assignments, backup instances, policies, billing groups, policy adherence and optimization findings.

If the core data pulls fail, a separate failure email goes to the ops mailbox instead.

## How it works

```text
Recurrence, daily at 6:00 AM Eastern
  │
  ├─ Scopes 1-3   Microsoft's Backup Reports KQL functions against Log Analytics
  ├─ Scope 4      Resource Graph: policy assignments
  ├─ Scope 5      Resource Graph: PostgreSQL backups
  │               ARM API per SQL database: short and long term retention
  ├─ Scope 6      Summary numbers and estate counts
  ├─ Scope 7      Vault health, compared against the expected Tier-* policy set
  ├─ Scope 8      Month-to-date storage change
  │
  └─ Core scopes failed?  yes → failure email to ops
                          no  → build HTML → create draft in Graph → send
```

A few choices worth explaining:

- The email goes out through Microsoft Graph as a draft that then gets sent. The plain Send an email action can't handle file attachments and inline chart images in the same message.
- Resource Graph and ARM calls use the Logic App's managed identity, so there are no stored credentials.
- An item counts as stale when the backup still exists but the VM or database it protected is gone. Those keep costing money until someone deletes them.
- Vault health flags any vault missing a `Tier-*` policy that other vaults have. That's how policy drift between vaults shows up.

## Setup

You'll need:

- Diagnostic settings on each Recovery Services vault and Backup vault, sending to Log Analytics with resource-specific tables
- An Azure Monitor Logs connection with read access to that workspace
- An Office 365 Outlook connection signed in as the mailbox that sends the report

Then:

1. Create a Consumption Logic App and turn on its system-assigned managed identity under Identity.
2. Give that identity Reader on each subscription you want in the report, under Access control (IAM) on the subscription.
3. Open the Logic App in code view and paste in `workflow.json`.
4. In the designer, point the two connections at the ones you created.
5. Set the `workspacesToQuery` parameter to your Log Analytics workspace resource ID.
6. Swap the `contoso.com` placeholder recipients in the Compose action and the failure email for real ones.
7. Run the trigger manually and check the email before you trust the schedule.

## Checks

`tests/check_workflow.py` runs in CI on every push. It fails if `workflow.json` isn't valid JSON, if the trigger or failure branch has gone missing, or if a real email address, subscription ID or embedded image ends up in the file.

## Known gaps

- The failure check only covers the first three scopes. If one of scopes 4-8 fails, the report still sends with that section empty. Adding those scopes to the condition is the next fix.
- Microsoft's report functions make up most of the file's size. I left them as-is so they're easy to update from Microsoft's version.
