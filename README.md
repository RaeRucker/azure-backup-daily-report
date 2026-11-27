# Daily Azure Backup Report

A Logic App that emails an Azure Backup health report every day on a schedule you choose.

Deploy it with the **Deploy to Azure** button in [Setup](#setup), or paste [`logic-app/workflow.json`](logic-app/workflow.json) into a Logic App's code view. Either way you fill in a handful of settings, sign in to two connections, and it's ready to run.

## What it does

Each run pulls backup data from Log Analytics, Azure Resource Graph and the Azure API, then sends one email that answers four questions. Is everything protected? What failed? Is every vault set up the way it should be? Are the databases covered?

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

If you don't have the Owner or User Access Administrator role, ask someone who does to do step 4 for you.

## What to change for your environment

These are the only things you need to fill in. Everything else works as-is.

| Setting | What to put in | Where you set it |
|---|---|---|
| `workspaceResourceId` / `workspacesToQuery` | Resource ID of the Log Analytics workspace your vaults send logs to. Find it on the workspace under **Overview → JSON View**. It starts with `/subscriptions/` | Deploy form, or **Logic app designer → Parameters** |
| `reportTo` | Who gets the report, as a list like `["backups@yourcompany.com", "manager@yourcompany.com"]` | Deploy form, or **Parameters** |
| `reportCc` | Who gets copied. Use `[]` for nobody | Deploy form, or **Parameters** |
| `failureTo` | The mailbox that gets an alert if the report fails to run | Deploy form, or **Parameters** |
| `emailSubject` | Subject line. Default is `Daily Azure Backup Report` | Deploy form, or **Parameters** |
| `teamName` | Your team's name, shown in the email header and footer. Default is `Azure Operations` | Deploy form, or **Parameters** |
| Azure Monitor Logs connection | Sign in with an account that can read the workspace | Step 3 |
| Office 365 Outlook connection | Sign in with the mailbox the report should be sent from | Step 3 |
| `runHour` and `timeZone` | The hour it runs each day, 0 to 23, and your time zone, like `Eastern Standard Time` or `Pacific Standard Time` | Deploy form, or **Logic app designer → Recurrence** trigger |
| Which vaults are included | Default is every vault the workspace has logs for. To narrow it, change `vaultSubscriptionListFilter`, `vaultListFilter` or `vaultLocationListFilter` from `"*"` to names in quotes separated by commas, like `"rsv-prod-eastus2","rsv-prod-centralus"` | **Parameters** |

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

### Step 2. Deploy the Logic App

Pick one of these. Option A is quicker.

#### Option A: Deploy to Azure button

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FRaeRucker%2Fazure-backup-daily-report%2Fmain%2Fazuredeploy.json)

1. Click the button above. It opens the Azure portal with a deployment form.
2. Pick the subscription and resource group, or click **Create new** for a new resource group.
3. Fill in the form using the table in [What to change for your environment](#what-to-change-for-your-environment). Lists go in with square brackets and quotes, like `["backups@yourcompany.com"]`.
4. Click **Review + create**, then **Create**.
5. When it finishes, click **Go to resource group**. You should see the Logic App and two API connections.

This creates the Logic App with its managed identity already turned on, plus the two connections. The connections still need you to sign in, which is step 3.

#### Option B: Paste it in yourself

1. In the portal search bar, type **Logic apps** and open it.
2. Click **Add**, then pick **Consumption**.
3. Choose the subscription and resource group, give it a name, pick a region, and click **Review + create**, then **Create**.
4. Open the new Logic App and go to **Settings → Identity**. On the **System assigned** tab, set **Status** to **On**, click **Save**, then **Yes**.
5. Go to **Development Tools → Logic app code view**, select everything in the editor and delete it.
6. Paste in the full contents of [`logic-app/workflow.json`](logic-app/workflow.json) and click **Save**. It will complain about the connections. That gets fixed in step 3.
7. Go to **Development Tools → Logic app designer** and click **Parameters** in the top bar. Fill in each setting from the table in [What to change for your environment](#what-to-change-for-your-environment), then click **Save**.

### Step 3. Sign in to the two connections

**If you used Option A:**

1. Open the resource group and click the connection ending in `-azuremonitorlogs`.
2. Go to **General → Edit API connection**, click **Authorize**, sign in, then click **Save**.
3. Do the same for the connection ending in `-office365`. Sign in with the mailbox that should send the report.

**If you used Option B:**

1. In the **Logic app designer**, open any action with a warning icon that uses **Azure Monitor Logs**. Click **Change connection → Add new**, sign in, and save.
2. Do the same for an action that uses **Office 365 Outlook**. Sign in with the mailbox that should send the report.
3. Every other action using the same connector picks up the new connection. Click **Save**.

### Step 4. Give the Logic App Reader

The Logic App uses its own identity to read your vaults and databases. It needs Reader on every subscription you want in the report.

1. In the portal search bar, type **Subscriptions** and click the one you want.
2. Go to **Access control (IAM) → Add → Add role assignment**.
3. Search for **Reader**, select it, and click **Next**.
4. Under **Assign access to**, pick **Managed identity**, then click **Select members**.
5. Under **Managed identity**, pick **Logic app**, select yours, and click **Select**.
6. Click **Review + assign** twice.
7. Repeat for every other subscription.

### Step 5. Test it

1. Open the Logic App, go to **Overview**, and click **Run trigger → Run**.
2. Open **Runs history** and click the newest run. Every scope should show a green check.
3. Check the inbox. The email should arrive within a few minutes.

After that it runs every day at the time you set.

## If something goes wrong

| What you see | What to check |
|---|---|
| An HTTP action fails with 403 or AuthorizationFailed | The managed identity is missing Reader on that subscription. Redo step 4. |
| Sections come back empty | The vault isn't sending logs or the data hasn't arrived yet. Check step 1 and wait a few hours. |
| Log Analytics actions fail | The Azure Monitor Logs connection account doesn't have Log Analytics Reader on the workspace. |
| No email shows up but the run is green | Check the Office 365 connection and the mailbox's Sent Items. |
| A connection shows Unauthenticated or Error | Redo step 3 for that connection. |
| The deploy form rejects `reportTo` | It needs square brackets and quotes, like `["you@yourcompany.com"]`. |
| You got the failure email | Open that run in **Runs history** and look for the first red action. |

## How it's built

```text
Recurrence, daily at the time you set
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

## Files

| File | What it is |
|---|---|
| `logic-app/workflow.json` | The workflow itself. This is the file to edit |
| `azuredeploy.json` | The Deploy to Azure template. Generated from `workflow.json` by `tools/build_arm_template.py`, so don't edit it by hand |
| `tests/check_workflow.py` | The check that runs on every push |

## Checks

`tests/check_workflow.py` runs on every push. It fails if `workflow.json` isn't valid JSON, if a recipient is typed into an action instead of a parameter, if `azuredeploy.json` is out of date, if the schedule or the failure branch goes missing, or if a subscription ID, an email address outside the placeholder domain, or an embedded image gets committed. That keeps environment details out of the repo.

## Known gaps

- The failure check only covers scopes 1 to 3. If scope 4 through 8 fails, the report still sends with that section empty. Adding those scopes to the condition is the next fix.
- Microsoft's report queries make up most of the file. I left them as-is so they're easy to update from Microsoft's version.
