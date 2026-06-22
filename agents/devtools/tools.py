"""
agents/devtools/tools.py

Mock implementations — replace `run()` bodies with real integrations
(GitHub/Jira API, CI provider API, etc.) when wiring this up for real.
The contract shape is what matters for the portfolio demo: each tool
is independently swappable without touching agent logic.
"""

from __future__ import annotations

from typing import Any

from core.registry import ToolRegistry


class SearchIssuesTool:
    name = "search_issues"
    description = "Search the issue tracker for issues matching a query, for duplicate detection."

    def run(self, **kwargs: Any) -> Any:
        query = kwargs.get("query", "")
        # Mock data — replace with real issue tracker API call.
        return {"matches": [], "query": query}


class ClassifySeverityTool:
    name = "classify_severity"
    description = "Classify an issue's severity based on its description."

    def run(self, **kwargs: Any) -> Any:
        description = kwargs.get("description", "").lower()
        if any(word in description for word in ["down", "outage", "crash", "data loss"]):
            return {"severity": "critical"}
        if any(word in description for word in ["error", "fail", "broken"]):
            return {"severity": "high"}
        return {"severity": "medium"}


class GetBuildStatusTool:
    name = "get_build_status"
    description = "Fetch the current status of a CI build/pipeline."

    def run(self, **kwargs: Any) -> Any:
        build_id = kwargs.get("build_id", "unknown")
        # Mock — replace with real CI provider API call.
        return {"build_id": build_id, "status": "failed", "stage": "test"}


class GetFailureLogsTool:
    name = "get_failure_logs"
    description = "Fetch and summarize failure logs for a failed build."

    def run(self, **kwargs: Any) -> Any:
        build_id = kwargs.get("build_id", "unknown")
        return {"build_id": build_id, "summary": "Mock log summary — wire to real log API."}


class ProposeDeployTool:
    name = "propose_deploy"
    description = (
        "Propose a deploy/rollback action. NEVER executes directly — "
        "DeployAgent.always_gate=True means this always pauses for human approval."
    )

    def run(self, **kwargs: Any) -> Any:
        return {"proposal": kwargs, "status": "pending_approval"}


class ProposePatchTool:
    name = "propose_patch"
    description = (
        "Propose a code patch / draft PR. NEVER executes directly — "
        "CodeAgent.always_gate=True means this always pauses for human approval."
    )

    def run(self, **kwargs: Any) -> Any:
        return {"proposal": kwargs, "status": "pending_approval"}


for tool in (
    SearchIssuesTool(),
    ClassifySeverityTool(),
    GetBuildStatusTool(),
    GetFailureLogsTool(),
    ProposeDeployTool(),
    ProposePatchTool(),
):
    ToolRegistry.register(tool)
