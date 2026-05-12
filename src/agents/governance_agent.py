"""Governance Agent — Compliance checking, risk assessment, policy validation.

This agent demonstrates enterprise governance patterns:
1. Policy-aware compliance checking
2. Risk assessment for AI deployments
3. Regulatory requirement mapping
4. Audit trail generation

Enterprise Deployment Blocker this solves:
"Our legal/compliance team won't approve AI until we prove governance."
→ Solution: Built-in governance agent that validates every interaction
   against enterprise policies and generates audit-ready reports.
"""

from __future__ import annotations

import json

from src.agents.base import AgentContext, AgentRole
from src.agents.react import ReActAgent
from src.tools import api as tool_api

GOVERNANCE_DOMAIN_PROMPT = """\
You are an enterprise governance and compliance agent. You help organizations
ensure their AI deployments meet regulatory, security, and policy requirements.

Your responsibilities:
1. Assess compliance against enterprise AI policies
2. Identify risks in AI use cases (data privacy, bias, security)
3. Map regulatory requirements (GDPR, SOC2, HIPAA, etc.)
4. Generate audit-ready compliance reports
5. Recommend governance controls and guardrails

Output format for compliance assessments:
## Compliance Assessment

### Risk Level: [LOW | MEDIUM | HIGH | CRITICAL]

### Policy Compliance
- ✅ / ❌ Policy 1: <status and details>
- ✅ / ❌ Policy 2: <status and details>

### Identified Risks
1. <risk> — Severity: <level> — Mitigation: <action>

### Regulatory Considerations
- <regulation>: <applicable requirements>

### Required Actions
1. <action item with owner and timeline>

### Audit Trail
- Assessment Date: <date>
- Assessor: Governance Agent
- Scope: <what was assessed>

Always err on the side of caution. Flag potential issues rather than miss them.
"""


class GovernanceAgent(ReActAgent):
    """Governance agent with ReAct reasoning for compliance and risk assessment.

    Uses the ReAct reasoning loop:
    Thought (identify risk areas) → Action (check_policy/assess_risk) → Observation (findings) → ... → Final Answer (audit-ready report)
    """

    def __init__(self, search_tool=None):
        super().__init__(
            name="governance",
            role=AgentRole.GOVERNANCE,
            description="Assesses compliance, identifies risks, and validates AI governance policies",
        )
        self._search_tool = search_tool
        self._register_tools()

    @property
    def domain_instructions(self) -> str:
        return GOVERNANCE_DOMAIN_PROMPT

    def _register_tools(self):
        self.register_tool(
            func=self._check_policy,
            name="check_policy",
            description="Search enterprise policies and governance documents to check compliance requirements.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Policy or compliance topic to look up",
                    },
                    "regulation": {
                        "type": "string",
                        "description": "Specific regulation to check (e.g., GDPR, HIPAA, SOC2)",
                    },
                },
                "required": ["query"],
            },
        )

        self.register_tool(
            func=self._assess_risk,
            name="assess_risk",
            description="Perform a risk assessment for an AI use case or deployment scenario.",
            parameters={
                "type": "object",
                "properties": {
                    "use_case": {
                        "type": "string",
                        "description": "Description of the AI use case to assess",
                    },
                    "data_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Types of data involved (e.g., PII, financial, health)",
                    },
                    "deployment_scope": {
                        "type": "string",
                        "description": "Internal, customer-facing, or both",
                    },
                },
                "required": ["use_case"],
            },
        )

    async def _check_policy(self, query: str, regulation: str | None = None) -> str:
        """Check policy via tools.api."""
        result = await tool_api.check_policy(
            query=query, regulation=regulation, search_tool=self._search_tool,
        )
        return json.dumps(result, default=str)

    async def _assess_risk(
        self,
        use_case: str,
        data_types: list[str] | None = None,
        deployment_scope: str = "internal",
    ) -> str:
        """Assess risk via tools.api."""
        result = await tool_api.assess_risk(
            use_case=use_case, data_types=data_types, deployment_scope=deployment_scope,
        )
        return json.dumps(result, default=str)
