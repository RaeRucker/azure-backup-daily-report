"""Checks logic-app/workflow.json before it's published.

Fails if the file isn't valid JSON, if it has lost the expected structure, or if
a subscription ID, a non-placeholder email address or an embedded image was committed.
Run: python tests/check_workflow.py
"""
import json
import re
import sys
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent / "logic-app" / "workflow.json"
ALLOWED_EMAIL_DOMAINS = {"contoso.com", "example.com"}
ZERO_GUID = "00000000-0000-0000-0000-000000000000"
SUBSCRIPTION_ID = re.compile(r"subscriptions/([0-9a-fA-F-]{36})")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")
    problems = []

    try:
        doc = json.loads(text)
    except json.JSONDecodeError as err:
        print(f"workflow.json is not valid JSON: {err}")
        return 1

    definition = doc.get("definition", {})
    if "Recurrence" not in definition.get("triggers", {}):
        problems.append("missing the Recurrence trigger")
    if "If_Any_Scope_Failed" not in definition.get("actions", {}):
        problems.append("missing the If_Any_Scope_Failed condition")

    for domain in sorted({m.group(1).lower() for m in EMAIL.finditer(text)}):
        if domain not in ALLOWED_EMAIL_DOMAINS:
            problems.append(f"email address at {domain}")

    for sub in sorted({m.group(1) for m in SUBSCRIPTION_ID.finditer(text)}):
        if sub != ZERO_GUID:
            problems.append(f"subscription ID {sub}")

    if "iVBORw0KGgo" in text:
        problems.append("embedded PNG image")

    for p in problems:
        print(f"FAIL: {p}")
    if not problems:
        print("workflow.json OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
