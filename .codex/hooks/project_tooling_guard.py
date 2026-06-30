import json
import re
import sys


PROJECT_PYTHON = r"D:\Anaconda3\envs\ai-content-ops\python.exe"


def emit_allow(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": reason,
                }
            },
            ensure_ascii=True,
        )
    )


def emit_deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            },
            ensure_ascii=True,
        )
    )


def should_block_python_command(command: str) -> bool:
    patterns = [
        r"(^|\s)python(\.exe)?(\s|$)",
        r"(^|\s)pip(\.exe)?(\s|$)",
        r"(^|\s)pytest(\s|$)",
    ]
    return any(re.search(pattern, command, flags=re.IGNORECASE) for pattern in patterns)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        emit_allow(f"hook parse fallback: {exc}")
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    command = tool_input.get("command", "")

    if not isinstance(command, str) or not command.strip():
        emit_allow("no command payload detected")
        return 0

    if tool_name == "Bash":
        if PROJECT_PYTHON.lower() not in command.lower() and should_block_python_command(command):
            emit_deny(
                "Use the project interpreter for Python commands: "
                f"{PROJECT_PYTHON} -m <module>."
            )
            return 0

        if re.search(r"\bdocker\s+compose\b.*\bdown\b.*\s-v\b", command, flags=re.IGNORECASE):
            emit_deny("Avoid destructive Docker volume resets unless they were explicitly requested.")
            return 0

        if re.search(r"\bdocker\s+volume\s+rm\b", command, flags=re.IGNORECASE):
            emit_deny("Avoid removing Docker volumes unless the task explicitly requires it.")
            return 0

        emit_allow("project tooling guard passed")
        return 0

    if tool_name == "apply_patch":
        sensitive_paths = [
            "infra/docker-compose",
            "apps/api/requirements",
            "apps/web/package.json",
            "apps/web/package-lock.json",
        ]
        if any(path in command.replace("\\", "/") for path in sensitive_paths):
            emit_allow(
                "This patch touches infra or dependency files. Mention verification impact and update docs if commands or setup changed."
            )
            return 0

    emit_allow("project tooling guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
