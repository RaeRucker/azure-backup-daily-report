# Daily Azure Backup Report

A Logic App that emails an Azure Backup health report every morning at 6 AM Eastern.

The whole workflow is in [`logic-app/workflow.json`](logic-app/workflow.json). Paste it into a Logic App's code view, connect it to your environment, and it's ready to run.

## What it does

Every morning it pulls backup data from Log Analytics, Azure Resource Graph and the Azure API, then sends one email that answers four questions. Is everything protected? What failed? Is every vault set up the way it should be? Are the databases covered?

| # | Section | Where the data comes from |
|---|---|---|
| 01 | Summary of protected, failed and stale items by workload type | Log Analytics and Resource Graph |
| 02 | Failed backup jobs | Log Analytics |
| 03 | Which systems are on each backup policy, with the policy settings | Resource Graph |
| 04 | Vault health covering redundancy, immutability, soft delete, cross region restore and missing tier policies | Resource Graph |
| 05 | PostgreSQL backups and Azure SQL short and long term retention | Resource Graph and the Azure API |
| 06 | Backup storage trend per vault | Log Analytics |
| 07 | Storage growth per vault so far this month | Log Analytics |

CSV files are attached for the job list, policy assignments, backup instances, policies, billing groups, policy adherence and optimization findings.

If the main data pulls fail, a short failure email goes to the ops mailbox instead.

I started from Microsoft's [Azure Backup report email template](https://aka.ms/AzureBackupReportEmail) and built my own report on top of it. The HTML layout and sections 03, 04, 05 and 07 are mine.

## Permissions

You need these before you start.

| Who | Role | Where it's assigned | Why |
|---|---|---|---|
| You, while setting it up | Contributor | The resource group the Logic App goes in | To create the Logic App and its connections |
| You, while setting it up | Monitoring Contributor | Each Recovery Services vault and Backup vault | To turn on diagnostic settings |
| You, while setting it up | Log Analytics Contributor | The Log Analytics workspace | So the vaults can send logs to it |
| You, while setting it up | Owner or User Access Administrator | Each subscription in the report | To give the Logic App's identity Reader |
| The Logic App's managed identity | Reader | Each subscription in the report | To query Resource Graph and read SQL backup retention |
| The account used for the Azure Monitor Logs connection | Log Analytics Reader | The Log Analytics workspace | To run the report queries |
| The account used for the Office 365 Outlook connection | A licensed Exchange Online mailbox | n/a | The email is sent from this mailbox |

If you don't have the Owner or User Access Administrator role, ask someone who does to do step 3 for you.

## Setup

### Step 1. Send vault logs to Log Analytics

Do this for every Recovery Services vault and Backup vault you want in the report.

1. In the Azure portal, open the vault.
2. Go to **Monitoring → Diagnostic settings → Add diagnostic setting**.
3. Name it something like `backup-to-law`.
4. Tick every Azure Backup log category.
5. Tick **Send to Log Analytics workspace** and pick your workspace.
6. Set **Destination table** to **Resource specific**. The report won't work with Azure diagnostics mode.
7. Click **Save**.

New data can take a few hours to show up in the workspace.

### Step 2. Create the Logic App

1. In the portal search bar, type **Logic apps** and open it.
2. Click **Add**, then pick **Consumption**.
3. Choose the subscription and resource group, give it a name, pick a region and click **Review + create**, then **Create**.
4. When it's done, click **Go to resource**.

### Step 3. Turn on its identity and give it Reader

1. In the Logic App, go to **Settings → Identity**.
2. On the **System assigned** tab, set **Status** to **On** and click **Save**. Click **Yes** when it asks.
3. Now open a subscription you want in the report. Search **Subscriptions** in the portal and click the one you want.
4. Go to **Access control (IAM) → Add → Add role assignment**.
5. Search for **Reader**, select it and click **Next**.
6. Under **Assign access to**, pick **Managed identity**, then click **Select members**.
7. Under **Managed identity**, pick **Logic app**, select yours and click **Select**.
8. Click **Review + assign** twice.
9. Repeat 3 to 8 for every other subscription.

### Step 4. Paste in the workflow

1. Back in the Logic App, go to **Development Tools → Logic app code view**.
2. Select everything in the editor and delete it.
3. Paste in the full contents of `logic-app/workflow.json`.
4. Click **Save**. It will complain about the connections. That's expected and gets fixed next.

### Step 5. Fix the connections

1. Go to **Development Tools → Logic app designer**.
2. Open any action with a warning icon that uses **Azure Monitor Logs**. Click **Change connection → Add new**, sign in, and save.
3. Do the same for an action that uses **Office 365 Outlook**. Sign in with the mailbox that should send the report.
4. Every other action using the same connector picks up the new connection. Click **Save**.

### Step 6. Point it at your workspace and recipients

1. In the designer, click **Parameters** in the top bar.
2. Set **workspacesToQuery** to your Log Analytics workspace resource ID. You can find it on the workspace's **Overview → JSON View**. It starts with `/subscriptions/`.
3. Go back to **Logic app code view** and press Ctrl+F to search for `contoso.com`.
4. Replace `backup-reports@contoso.com` and `it-team@contoso.com` with the people who should get the report, and `ops-alerts@contoso.com` with the mailbox that gets failure emails.
5. Click **Save**.

### Step 7. Test it

1. Go to **Overview** and click **Run trigger → Run**.
2. Open **Runs history** and click the newest run. Every scope should show a green check.
3. Check the inbox. The email should arrive within a few minutes.

After that it runs every day at 6 AM Eastern. To change the time, open the **Recurrence** trigger in the designer.

## If something goes wrong

| What you see | What to check |
|---|---|
| An HTTP action fails with 403 or AuthorizationFailed | The managed identity is missing Reader on that subscription. Redo step 3. |
| Sections come back empty | The vault isn't sending logs or the data hasn't arrived yet. Check step 1 and wait a few hours. |
| Log Analytics actions fail | The Azure Monitor Logs connection account doesn't have Log Analytics Reader on the workspace. |
| No email shows up but the run is green | Check the Office 365 connection and the mailbox's Sent Items. |
| You got the failure email | Open that run in **Runs history** and look for the first red action. |

## How it's built

```text
Recurrence, daily at 6:00 AM Eastern
  │
  ├─ Scopes 1-3   Microsoft's Backup Reports queries against Log Analytics
  ├─ Scope 4      Resource Graph: policy assignments
  ├─ Scope 5      Resource Graph: PostgreSQL backups
  │               Azure API per SQL database: short and long term retention
  ├─ Scope 6      Summary numbers and estate counts
  ├─ Scope 7      Vault health, compared against the expected Tier-* policy set
  ├─ Scope 8      Month-to-date storage change
  │
  └─ Main scopes failed?  yes → failure email to ops
                          no  → build HTML → create draft in Graph → send
```

A few choices worth explaining:

- The email is sent through Microsoft Graph as a draft that then gets sent. The plain Send an email action can't handle file attachments and inline chart images in the same message.
- Resource Graph and Azure API calls use the Logic App's managed identity, so there are no stored passwords or keys.
- An item counts as stale when its backup still exists but the VM or database it protected is gone. Those keep costing money until someone deletes them.
- Vault health flags any vault missing a `Tier-*` policy that other vaults have. That's how policy drift between vaults shows up.

## Checks

`tests/check_workflow.py` runs on every push. It fails if `workflow.json` isn't valid JSON, if the schedule or the failure branch goes missing, or if a subscription ID, an email address outside the placeholder domain, or an embedded image gets committed. That keeps environment details out of the repo.

## Known gaps

- The failure check only covers scopes 1 to 3. If scope 4 through 8 fails, the report still sends with that section empty. Adding those scopes to the condition is the next fix.
- Microsoft's report queries make up most of the file. I left them as-is so they're easy to update from Microsoft's version.
