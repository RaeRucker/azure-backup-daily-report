"""Checks logic-app/workflow.json and azuredeploy.json before they're published.

Fails if:
- either file isn't valid JSON
- the schedule, the failure branch or any setting the README relies on is missing
- a Log Analytics action points at a fixed workspace instead of the workspaceResourceId setting
- a recipient is typed into an action instead of a setting
- a subscription ID, resource group, workspace name or email address that isn't a placeholder
  shows up anywhere, or an image is embedded

Run: python tests/check_workflow.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [ROOT / "logic-app" / "workflow.json", ROOT / "azuredeploy.json"]

REQUIRED_SETTINGS = ("workspaceResourceId", "reportTo", "reportCc", "failureTo", "emailSubject", "teamName")

ZERO_GUID = "00000000-0000-0000-0000-000000000000"
PLACEHOLDER_EMAIL_DOMAINS = {"contoso.com", "example.com"}
PLACEHOLDER_RESOURCE_GROUPS = {"rg-monitoring", "rg-logicapps"}
PLACEHOLDER_WORKSPACES = {"law-backup-reporting"}

GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
RESOURCE_GROUP = re.compile(r"resourceGroups/([^/\"'\s\\]+)", re.I)
WORKSPACE = re.compile(r"workspaces/([^/\"'\s\\]+)", re.I)
EMBEDDED_IMAGE = ("iVBORw0KGgo", "/9j/4", "R0lGOD")  # PNG, JPEG, GIF


def walk(actions):
    for name, action in actions.items():
        yield name, action
        yield from walk(action.get("actions", {}))
        if isinstance(action.get("else"), dict):
            yield from walk(action["else"].get("actions", {}))


def check_structure(doc, problems):
    definition = doc.get("definition", {})
    if "Recurrence" not in definition.get("triggers", {}):
        problems.append("workflow.json: missing the Recurrence trigger")
    if "If_Any_Scope_Failed" not in definition.get("actions", {}):
        problems.append("workflow.json: missing the If_Any_Scope_Failed condition")
    for name in REQUIRED_SETTINGS:
        if name not in definition.get("parameters", {}):
            problems.append(f"workflow.json: missing the {name} setting")

    for name, action in walk(definition.get("actions", {})):
        inputs = action.get("inputs") if isinstance(action.get("inputs"), dict) else {}
        queries = inputs.get("queries")
        if isinstance(queries, dict) and "resourcename" in queries:
            for field in ("subscriptions", "resourcegroups", "resourcename"):
                if not str(queries.get(field, "")).startswith("@"):
                    problems.append(f"workflow.json: {name} has a fixed {field} instead of using workspaceResourceId")

    if EMAIL.search(json.dumps(definition.get("actions", {}))):
        problems.append("workflow.json: an email address is typed into an action instead of a setting")


def check_leaks(label, text, problems):
    for guid in sorted({g.lower() for g in GUID.findall(text)}):
        if guid != ZERO_GUID:
            problems.append(f"{label}: ID {guid}")
    for domain in sorted({m.lower() for m in EMAIL.findall(text)}):
        if domain not in PLACEHOLDER_EMAIL_DOMAINS:
            problems.append(f"{label}: email address at {domain}")
    for rg in sorted(set(RESOURCE_GROUP.findall(text))):
        if rg not in PLACEHOLDER_RESOURCE_GROUPS and not rg.startswith(("@", "[", "{", "<")):
            problems.append(f"{label}: resource group {rg}")
    for ws in sorted(set(WORKSPACE.findall(text))):
        if ws not in PLACEHOLDER_WORKSPACES and not ws.startswith(("@", "[", "{", "<")):
            problems.append(f"{label}: workspace {ws}")
    for marker in EMBEDDED_IMAGE:
        if marker in text:
            problems.append(f"{label}: embedded image")
            break


def main() -> int:
    problems = []
    for path in FILES:
        label = path.relative_to(ROOT).as_posix()
        if not path.exists():
            problems.append(f"{label}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as err:
            problems.append(f"{label}: not valid JSON ({err})")
            continue
        if path.name == "workflow.json":
            check_structure(doc, problems)
        check_leaks(label, text, problems)

    for p in problems:
        print(f"FAIL: {p}")
    if not problems:
        print("workflow.json and azuredeploy.json OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
