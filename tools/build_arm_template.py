"""Builds azuredeploy.json (the Deploy to Azure template) from logic-app/workflow.json.

Run this after any change to workflow.json:
    python tools/build_arm_template.py
CI fails if azuredeploy.json is out of date.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "logic-app" / "workflow.json"
OUTPUT = ROOT / "azuredeploy.json"


def escape_brackets(value):
    """ARM treats a string that starts with '[' and ends with ']' as an expression. '[[' keeps it literal."""
    if isinstance(value, str):
        return "[" + value if value.startswith("[") and value.endswith("]") else value
    if isinstance(value, list):
        return [escape_brackets(v) for v in value]
    if isinstance(value, dict):
        return {k: escape_brackets(v) for k, v in value.items()}
    return value


def connection(name, api):
    return {
        "connectionId": f"[resourceId('Microsoft.Web/connections', variables('{name}'))]",
        "connectionName": f"[variables('{name}')]",
        "id": f"[subscriptionResourceId('Microsoft.Web/locations/managedApis', parameters('location'), '{api}')]",
    }


def build():
    definition = json.loads(WORKFLOW.read_text(encoding="utf-8"))["definition"]

    definition = escape_brackets(definition)

    # The schedule comes from the deploy form instead of the copy in workflow.json.
    # Set after escaping so these stay live template expressions.
    trigger = definition["triggers"]["Recurrence"]
    trigger.pop("evaluatedRecurrence", None)
    trigger["recurrence"] = {
        "frequency": "Day",
        "interval": 1,
        "timeZone": "[parameters('timeZone')]",
        "schedule": {"hours": ["[parameters('runHour')]"], "minutes": [0]},
    }

    template = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "metadata": {"description": "Daily Azure Backup Report Logic App. Generated from logic-app/workflow.json by tools/build_arm_template.py. Don't edit by hand."},
        "parameters": {
            "logicAppName": {"type": "string", "defaultValue": "la-backup-daily-report", "metadata": {"description": "Name for the Logic App."}},
            "location": {"type": "string", "defaultValue": "[resourceGroup().location]", "metadata": {"description": "Region. Defaults to the resource group's region."}},
            "workspaceResourceId": {"type": "string", "metadata": {"description": "Resource ID of the Log Analytics workspace the vaults send diagnostics to. Starts with /subscriptions/."}},
            "reportTo": {"type": "array", "metadata": {"description": "Who gets the report, as a JSON list. Example: [\"backups@contoso.com\"]"}},
            "reportCc": {"type": "array", "defaultValue": [], "metadata": {"description": "Who gets copied, as a JSON list. Leave as [] for nobody."}},
            "failureTo": {"type": "string", "metadata": {"description": "Mailbox that gets the email if the report fails to run."}},
            "emailSubject": {"type": "string", "defaultValue": "Daily Azure Backup Report", "metadata": {"description": "Subject line of the report email."}},
            "teamName": {"type": "string", "defaultValue": "Azure Operations", "metadata": {"description": "Team name shown in the email header and footer."}},
            "runHour": {"type": "int", "defaultValue": 6, "minValue": 0, "maxValue": 23, "metadata": {"description": "Hour of the day the report runs, 0 to 23."}},
            "timeZone": {"type": "string", "defaultValue": "Eastern Standard Time", "metadata": {"description": "Windows time zone name for the schedule, like Eastern Standard Time or Pacific Standard Time."}},
        },
        "variables": {
            "logsConnectionName": "[concat(parameters('logicAppName'), '-azuremonitorlogs')]",
            "outlookConnectionName": "[concat(parameters('logicAppName'), '-office365')]",
        },
        "resources": [
            {
                "type": "Microsoft.Web/connections",
                "apiVersion": "2016-06-01",
                "name": "[variables('logsConnectionName')]",
                "location": "[parameters('location')]",
                "properties": {
                    "displayName": "Backup report - Azure Monitor Logs",
                    "api": {"id": "[subscriptionResourceId('Microsoft.Web/locations/managedApis', parameters('location'), 'azuremonitorlogs')]"},
                },
            },
            {
                "type": "Microsoft.Web/connections",
                "apiVersion": "2016-06-01",
                "name": "[variables('outlookConnectionName')]",
                "location": "[parameters('location')]",
                "properties": {
                    "displayName": "Backup report - Office 365 Outlook",
                    "api": {"id": "[subscriptionResourceId('Microsoft.Web/locations/managedApis', parameters('location'), 'office365')]"},
                },
            },
            {
                "type": "Microsoft.Logic/workflows",
                "apiVersion": "2019-05-01",
                "name": "[parameters('logicAppName')]",
                "location": "[parameters('location')]",
                "identity": {"type": "SystemAssigned"},
                "dependsOn": [
                    "[resourceId('Microsoft.Web/connections', variables('logsConnectionName'))]",
                    "[resourceId('Microsoft.Web/connections', variables('outlookConnectionName'))]",
                ],
                "properties": {
                    "state": "Enabled",
                    "definition": definition,
                    "parameters": {
                        "$connections": {"value": {
                            "azuremonitorlogs": connection("logsConnectionName", "azuremonitorlogs"),
                            "office365": connection("outlookConnectionName", "office365"),
                        }},
                        "workspaceResourceId": {"value": "[parameters('workspaceResourceId')]"},
                        "reportTo": {"value": "[parameters('reportTo')]"},
                        "reportCc": {"value": "[parameters('reportCc')]"},
                        "failureTo": {"value": "[parameters('failureTo')]"},
                        "emailSubject": {"value": "[parameters('emailSubject')]"},
                        "teamName": {"value": "[parameters('teamName')]"},
                    },
                },
            },
        ],
        "outputs": {
            "managedIdentityPrincipalId": {
                "type": "string",
                "value": "[reference(resourceId('Microsoft.Logic/workflows', parameters('logicAppName')), '2019-05-01', 'full').identity.principalId]",
            }
        },
    }
    return json.dumps(template, indent=2) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
