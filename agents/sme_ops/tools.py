"""
agents/sme_ops/tools.py

Mock tools for the SME-operations vertical. Replace run() bodies with
real integrations (Zendesk, Confluence, billing API, etc.).
"""

from __future__ import annotations

from typing import Any

from core.registry import ToolRegistry


class OpenTicketTool:
    name = "open_ticket"
    description = "Open a new support ticket and classify its priority."

    def run(self, **kwargs: Any) -> Any:
        description = kwargs.get("description", "").lower()
        if any(w in description for w in ["down", "outage", "data loss", "cannot access"]):
            priority = "urgent"
        elif any(w in description for w in ["error", "broken", "fail", "not working"]):
            priority = "high"
        elif any(w in description for w in ["slow", "delay", "laggy"]):
            priority = "medium"
        else:
            priority = "low"
        return {"ticket_id": "TKT-9999", "priority": priority, "status": "open"}


class SearchTicketsTool:
    name = "search_tickets"
    description = "Search existing support tickets for similar issues."

    def run(self, **kwargs: Any) -> Any:
        return {"matches": [], "query": kwargs.get("query", "")}


class PolicyLookupTool:
    name = "policy_lookup"
    description = "Search the company policy and procedures knowledge base."

    def run(self, **kwargs: Any) -> Any:
        topic = kwargs.get("topic", "")
        return {
            "topic": topic,
            "excerpt": f"Mock policy excerpt for '{topic}' — wire to Confluence/Notion API.",
            "source": "company-handbook-v3.pdf",
        }


class GetInvoiceTool:
    name = "get_invoice"
    description = "Retrieve invoice or billing record for a customer."

    def run(self, **kwargs: Any) -> Any:
        return {
            "customer_id": kwargs.get("customer_id", "unknown"),
            "billing_reference": kwargs.get("billing_reference"),
            "status": "paid",
            "amount": "MYR 299.00",
            "due_date": "2026-06-30",
        }


class ProposeEscalationTool:
    name = "propose_escalation"
    description = (
        "Propose escalating a ticket to the senior team or a human manager. "
        "EscalationAgent.always_gate=True — always pauses for approval."
    )

    def run(self, **kwargs: Any) -> Any:
        return {"proposal": kwargs, "status": "pending_approval"}


for tool in (
    OpenTicketTool(),
    SearchTicketsTool(),
    PolicyLookupTool(),
    GetInvoiceTool(),
    ProposeEscalationTool(),
):
    ToolRegistry.register(tool)
