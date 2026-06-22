"""
core/registry.py

Plugin-style registration. A domain package calls AgentRegistry.register()
on import — core never writes `from agents.devtools import TriageAgent`.

Which domain package gets imported at all is decided in ONE place: the
entrypoint (api/main.py reads SWITCHBOARD_DOMAIN from env/config and
imports that single package). Swapping industries means changing that
one import line, not touching anything under core/.
"""

from __future__ import annotations

import logging

from core.contracts import BaseTool, SpecialistAgent

logger = logging.getLogger("switchboard.registry")


class AgentRegistry:
    _agents: dict[str, SpecialistAgent] = {}

    @classmethod
    def register(cls, agent: SpecialistAgent) -> None:
        if agent.name in cls._agents:
            logger.warning(
                "Agent '%s' already registered — overwriting. "
                "Check for duplicate registration or name collision.",
                agent.name,
            )
        cls._agents[agent.name] = agent
        logger.info("Registered agent: %s", agent.name)

    @classmethod
    def all(cls) -> list[SpecialistAgent]:
        return list(cls._agents.values())

    @classmethod
    def get(cls, name: str) -> SpecialistAgent | None:
        return cls._agents.get(name)

    @classmethod
    def clear(cls) -> None:
        """Test-only: reset registry between test modules to avoid
        cross-contamination when multiple domain packages are imported
        in the same test session."""
        cls._agents.clear()


class ToolRegistry:
    _tools: dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        if tool.name in cls._tools:
            logger.warning("Tool '%s' already registered — overwriting.", tool.name)
        cls._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    @classmethod
    def get(cls, name: str) -> BaseTool | None:
        return cls._tools.get(name)

    @classmethod
    def all(cls) -> list[BaseTool]:
        return list(cls._tools.values())

    @classmethod
    def clear(cls) -> None:
        cls._tools.clear()
