"""
agents/_template/tools.py

Tools implement core.contracts.BaseTool structurally (Protocol — no
inheritance required, just matching shape). Register each tool instance
with ToolRegistry on import so the agent can declare it in required_tools()
and the registry can answer capability-check questions.

COPY THIS FILE when starting a new domain.
"""

from __future__ import annotations

from typing import Any

from core.registry import ToolRegistry


class TemplateExampleTool:
    name = "template_example_tool"
    description = "Replace with a real description of what this tool does."

    def run(self, **kwargs: Any) -> Any:
        # Replace with real implementation — API call, DB query, etc.
        return {"status": "ok", "echo": kwargs}


ToolRegistry.register(TemplateExampleTool())
