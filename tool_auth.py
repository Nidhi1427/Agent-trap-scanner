"""Allowlist gate and mock executor; unauthorized requests never reach execute()."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "tool_allowlist.json"


class MockExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, request):
        self.calls.append(request["tool"])
        return {"status": "mock_executed", "tool": request["tool"]}


def authorize_and_execute(request, executor, config_path=DEFAULT_CONFIG):
    config = json.loads(pathlib.Path(config_path).read_text(encoding="utf-8"))
    allowed = set(config["allowed_tools"])
    tool = request.get("tool")
    if tool not in allowed:
        return {"authorized": False, "outcome": "rejected", "tool": tool, "executor_called": False}
    result = executor.execute(request)
    return {"authorized": True, "outcome": result["status"], "tool": tool, "executor_called": True}
