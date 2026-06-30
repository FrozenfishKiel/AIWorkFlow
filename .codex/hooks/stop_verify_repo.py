import json
import re
import sys


SUCCESS_HINTS = [
    "done",
    "fixed",
    "complete",
    "completed",
    "pass",
    "passing",
    "verified",
]

VERIFY_HINTS = [
    "scripts/qa/verify.ps1",
    "verify.ps1",
    "npm run build",
    "pytest",
    "compileall",
    "python.exe -m",
]


def emit_continue() -> None:
    print(json.dumps({"continue": True}, ensure_ascii=True))


def emit_follow_up(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        emit_continue()
        return 0

    message = (payload.get("last_assistant_message") or "").lower()
    if not message:
        emit_continue()
        return 0

    has_success_claim = any(token in message for token in SUCCESS_HINTS)
    has_verification_hint = any(token in message for token in VERIFY_HINTS)
    has_limit_note = bool(re.search(r"\b(could not run|did not run|unable to run|not run)\b", message))

    if has_success_claim and not has_verification_hint and not has_limit_note:
        emit_follow_up(
            "Before stopping, run the relevant repository verification command, usually "
            "`powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope api|web|all`, "
            "then report the actual result or clearly state what could not be verified."
        )
        return 0

    emit_continue()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
