# Daily Azure Backup Report

A Logic App that emails an Azure Backup health report every day on a schedule you choose.

Deploy it with the Deploy to Azure button in [Setup](#setup). You fill in a handful of settings, sign in to two connections, and it's ready to run.

## What it does

Each run pulls backup data from Log Analytics, Azure Resource Graph and the Azure Resource Manager API, then sends one email that answers four questions. Is everything protected? What failed? Is every vault set up the way it should be? Are the databases covered?

| # | Section | Where the data comes from |
|---|---|---|
| 01 | Summary of protected, failed and stale items by workload type | Log Analytics and Resource Graph |
| 02 | Failed backup jobs | Log Analytics |
| 03 | Which systems are on each backup policy, with the policy settings | Resource Graph |
| 04 | Vault health covering redundancy, immutability, soft delete, cross-region restore and VM backup policies | Resource Graph |
| 05 | PostgreSQL backups and Azure SQL short-term and long-term retention | Resource Graph and the Azure Resource Manager API |
| 06 | Backup storage trend | Log Analytics |
| 07 | Storage growth per vault so far this month | Log Analytics |

Sections 06 and 07 only cover Recovery Services vaults. Backup vaults don't report storage to Log Analytics.

CSV files are attached for the job list, policy assignments, backup instances, policies, billing groups, policy adherence and optimization findings.

If the main data pulls fail, a short failure email goes to the `failureTo` mailbox instead.

I started from Microsoft's [Azure Backup report email template](https://aka.ms/AzureBackupReportEmail) and built on it. The HTML layout and sections 03, 04, 05 and 07 are my own.

## Permissions

You need these before you start.

| Who | Role | Where it's assigned | Why |
|---|---|---|---|
| You, while setting it up | Contributor | The resource group the Logic App goes in | To create the Logic App and its connections |
| You, while setting it up | Monitoring Contributor | Each Recovery Services vault and Backup vault | To turn on diagnostic settings |
| You, while setting it up | Log Analytics Contributor | The Log Analytics workspace | To let the vaults send logs to it |
| You, while setting it up | User Access Administrator, Role Based Access Control Administrator, or Owner | Each subscription in the report | To give the Logic App's identity Reader |
| The Logic App's managed identity | Reader | Each subscription in the report | To query Resource Graph and read SQL backup retention |
| The account used for the Azure Monitor Logs connection | Log Analytics Reader | The Log Analytics workspace | To run the report queries |
| The account used for the Office 365 Outlook connection | A licensed Exchange Online mailbox | n/a | To send the email |

A managed identity is an account Azure creates for the Logic App itself, so it can read your resources without a stored password. If you can't assign roles, ask someone who can to do step 4 for you.

## What to change for your environment

These are the only things you need to fill in. Everything else works as-is.

| Setting | What to put in |
|---|---|
| `workspaceResourceId` | Resource ID of the Log Analytics workspace your vaults send logs to. Find it on the workspace under Overview → JSON View. It starts with `/subscriptions/`. |
| `reportTo` | Who gets the report, as a list like `["backups@contoso.com", "manager@contoso.com"]`. |
| `reportCc` | Who gets copied, as a list. Use `[]` for nobody. |
| `failureTo` | The mailbox that gets an alert if the report fails to run. |
| `emailSubject` | Subject line. Default is `Daily Azure Backup Report`. |
| `teamName` | Your team's name, shown in the email header and footer. Default is `Azure Operations`. |
| `runHour` and `timeZone` | The hour it runs each day, 0 to 23, and your time zone, like `Eastern Standard Time` or `Pacific Standard Time`. |
| Azure Monitor Logs connection | Sign in with an account that can read the workspace. This is step 3. |
| Office 365 Outlook connection | Sign in with the mailbox the report should be sent from. This is step 3. |

You fill in all the settings on the deploy form in step 2. To change one later, see [Changing a setting later](#changing-a-setting-later).

## Setup

### Step 1. Send vault logs to Log Analytics

Do this for every Recovery Services vault and Backup vault you want in the report.

1. In the Azure portal, open the vault.
2. Go to Monitoring → Diagnostic settings → Add diagnostic setting.
3. Name it something like `backup-to-law`.
4. Tick these categories:
   - Core Azure Backup Data
   - Addon Azure Backup Job Data
   - Addon Azure Backup Policy Data
   - Addon Azure Backup Storage Data
   - Addon Azure Backup Protected Instance Data
   - Azure Backup Operations

   Leave Azure Backup Reporting Data and Addon Azure Backup Alerts unticked. Those are older categories Microsoft is retiring. You can ignore the Site Recovery categories.
5. Tick Send to Log Analytics workspace and pick your workspace.
6. On a Recovery Services vault, set Destination table to Resource specific. Backup vaults don't show this option because they always use resource-specific tables.
7. Click Save.

The report reads data up to the end of yesterday, so wait until the day after this step before testing in step 5.

### Step 2. Deploy the Logic App

Pick one of these. Both give you the same result.

#### Option A: Deploy to Azure button

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FRaeRucker%2Fazure-backup-daily-report%2Fmain%2Fazuredeploy.json)

1. Click the button above. It opens the Azure portal with a deployment form.
2. Pick the subscription and resource group, or click Create new for a new resource group.
3. Fill in the form using the table in [What to change for your environment](#what-to-change-for-your-environment). Lists go in with square brackets and quotes, like `["backups@contoso.com"]`.
4. Click Review + create, then Create.
5. When it finishes, click Go to resource group. You should see the Logic App and two API connections.

#### Option B: Deploy from the template file

Use this if the button doesn't work for you.

1. Download [`azuredeploy.json`](azuredeploy.json) from this repo.
2. In the portal search bar, type Deploy a custom template and open it.
3. Click Build your own template in the editor, then Load file, and pick `azuredeploy.json`.
4. Click Save. You'll get the same form as Option A.
5. Follow steps 2 to 5 of Option A.

Both options create the Logic App with its managed identity turned on, plus the two connections. The connections still need you to sign in, which is the next step.

### Step 3. Sign in to the two connections

1. Open the resource group and click the connection ending in `-azuremonitorlogs`.
2. Go to General → Edit API connection, click Authorize, sign in, then click Save.
3. Do the same for the connection ending in `-office365`. Sign in with the mailbox that should send the report.

### Step 4. Give the Logic App Reader

The Logic App uses its managed identity to read your vaults and databases. It needs Reader on every subscription you want in the report.

1. In the portal search bar, type Subscriptions and click the one you want.
2. Go to Access control (IAM) → Add → Add role assignment.
3. Search for Reader, select it, and click Next.
4. Under Assign access to, pick Managed identity, then click Select members.
5. Under Managed identity, pick Logic app, select yours, and click Select.
6. Click Review + assign twice.
7. Repeat for every other subscription.

New role assignments can take 5 to 10 minutes to start working.

### Step 5. Test it

Wait until at least the day after step 1.

1. Open the Logic App, go to Development Tools → Logic app designer, and click Run → Run.
2. Go back to Overview, open Runs history and click the newest run.
3. Every step in the run should have a green check. Click any red one to see its error.
4. Check the inbox. The email should arrive within a few minutes.

After that it runs every day at the time you set.

## Changing a setting later

1. Open the Logic App and go to Development Tools → Logic app code view.
2. Scroll to the very bottom. There's a `parameters` section after the end of the workflow definition. It holds the values you entered on the deploy form.
3. Change the value and click Save.

Don't use the Parameters panel in the designer for this. It shows the defaults, and the values at the bottom of code view override them.

To change the run time, open the Recurrence trigger in the Logic app designer instead.

## Limiting which vaults are included

By default the report covers every vault the workspace has logs for. Three optional settings narrow the parts of the report that come from Log Analytics:

| Setting | What to put in |
|---|---|
| `vaultSubscriptionListFilter` | Subscription IDs |
| `vaultListFilter` | Vault names |
| `vaultLocationListFilter` | Regions, like `eastus2` |

Change the value from `"*"` to items in quotes separated by commas, like `"rsv-eastus2","rsv-centralus"`. Set them the same way as [Changing a setting later](#changing-a-setting-later).

Sections 03, 04 and 05 come from Resource Graph and always cover every subscription the Logic App has Reader on. To leave a subscription out of those, don't give the Logic App Reader on it.

## If something goes wrong

| What you see | What to check |
|---|---|
| Sections come back empty on the first day | The report only reads data up to the end of yesterday. Wait a day and run it again. |
| A query fails with "Failed to resolve table" or BadRequest | The vault isn't sending resource-specific logs yet. Check step 1 and wait a day. |
| Log Analytics actions fail with an access error | The Azure Monitor Logs connection account doesn't have Log Analytics Reader on the workspace, or `workspaceResourceId` is wrong. |
| An HTTP action fails with 403 or AuthorizationFailed | The managed identity is missing Reader on that subscription. Redo step 4. If you just did it, wait 10 minutes. |
| A connection shows Unauthenticated or Error | Redo step 3 for that connection. |
| No email shows up but the run is green | Check the Office 365 Outlook connection and the sending mailbox's Sent Items. |
| The deploy form rejects `reportTo` or `reportCc` | They need square brackets and quotes, like `["you@contoso.com"]`. |
| You got the failure email | Open that run in Runs history and look for the first red step. |

## How it's built

```text
Recurrence, daily at the time you set
  │
  ├─ Scopes 1 to 3  Microsoft's Backup Reports queries against Log Analytics
  ├─ Scope 4        Resource Graph: policy assignments
  ├─ Scope 5        Resource Graph: PostgreSQL backups
  │                 Azure Resource Manager API per SQL database: retention
  ├─ Scope 6        Summary numbers and resource counts
  ├─ Scope 7        Vault settings and VM backup policies
  ├─ Scope 8        Month-to-date storage change
  │
  └─ Scopes 1 to 3 failed?  yes → failure email
                            no  → build HTML → create draft in Graph → send
```

A few choices worth explaining:

- The email is sent through Microsoft Graph as a draft that then gets sent. The plain Send an email action can't handle file attachments and inline chart images in the same message.
- Resource Graph and Azure Resource Manager calls use the Logic App's managed identity, so there are no stored passwords or keys.
- An item counts as stale when its backup still exists but the VM or database it protected is gone. Those keep costing money until someone deletes them. If the Logic App doesn't have Reader on a subscription, items there can show as stale by mistake.
- Vault health flags a Recovery Services vault that has no VM backup policy at all, or a policy whose settings differ from a policy with the same name in another vault. That catches vaults that were set up by hand and drifted.

## Files

| File | What it is |
|---|---|
| `logic-app/workflow.json` | The workflow itself. This is the file to edit. |
| `azuredeploy.json` | The deploy template. It's generated from `workflow.json` by `tools/build_arm_template.py`, so don't edit it by hand. |
| `tools/build_arm_template.py` | Rebuilds `azuredeploy.json`. Run it after changing `workflow.json`. |
| `tests/check_workflow.py` | Checks both JSON files before they're published. |

## Checks

CI runs on every push to main and on every pull request. It fails if any of these happen:

- `workflow.json` or `azuredeploy.json` isn't valid JSON
- the schedule, the failure branch or one of the settings above goes missing
- a Log Analytics step points at a fixed workspace instead of `workspaceResourceId`
- an email address is typed into a step instead of a setting
- a subscription ID, resource group, workspace name or email address that isn't a placeholder shows up, or an image is embedded
- `azuredeploy.json` is out of date with `workflow.json`
- gitleaks finds a secret

## Known gaps

- The failure email only covers scopes 1 to 3. If any of scopes 4 to 8 fails, the report still sends with that section empty.
- Resource Graph returns up to 1,000 rows per query. In a very large environment, sections 03 to 05 could be cut short.
- The report reads one Log Analytics workspace.
- Microsoft's report queries make up most of the workflow. I left them as-is so they're easy to update from Microsoft's version.
