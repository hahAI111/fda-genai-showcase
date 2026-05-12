"""Compliance Skill — Policy checking, risk assessment, regulatory mapping.

Reusable skill for enterprise governance and compliance validation.

Enterprise Pattern Solved:
"Legal won't approve AI until we prove governance."
→ Built-in compliance checking that any agent can use.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.skills.base import Skill, ToolSchema


class ComplianceSkill(Skill):
    """Policy compliance checking, risk assessment, and audit support."""

    @property
    def name(self) -> str:
        return "compliance"

    @property
    def description(self) -> str:
        return (
            "Check compliance against enterprise policies, assess risks for "
            "AI use cases, map regulatory requirements (GDPR, HIPAA, SOC2), "
            "and generate audit-ready compliance reports."
        )

    @property
    def tags(self) -> list[str]:
        return ["compliance", "governance", "risk", "audit", "regulatory"]

    def get_tools(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="check_compliance",
                description=(
                    "Check an AI use case against enterprise policies and regulations. "
                    "Returns compliance status, required actions, and risk level."
                ),
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
                            "description": "Data types involved: PII, financial, health, internal",
                        },
                        "deployment_scope": {
                            "type": "string",
                            "enum": ["internal", "customer-facing", "both"],
                            "description": "Who will use this AI system",
                        },
                    },
                    "required": ["use_case"],
                },
                handler=self._check_compliance_handler,
            ),
            ToolSchema(
                name="generate_risk_assessment",
                description="Generate a structured risk assessment for an AI deployment.",
                parameters={
                    "type": "object",
                    "properties": {
                        "system_description": {
                            "type": "string",
                            "description": "Description of the AI system",
                        },
                        "regulations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Applicable regulations (GDPR, HIPAA, SOC2, etc.)",
                        },
                    },
                    "required": ["system_description"],
                },
                handler=self._risk_assessment_handler,
            ),
        ]

    def get_system_prompt_fragment(self) -> str:
        return (
            "When assessing compliance, always check: data classification, "
            "regulatory requirements, security controls, audit trail needs, "
            "and bias/fairness considerations. Err on the side of caution."
        )

    async def _check_compliance_handler(
        self,
        use_case: str,
        data_types: list[str] | None = None,
        deployment_scope: str = "internal",
    ) -> str:
        data_types = data_types or []
        requirements = []
        risk_level = "LOW"

        # Policy-based compliance rules
        if "PII" in data_types or "pii" in data_types:
            risk_level = "HIGH"
            requirements.extend([
                {"policy": "AI Governance Policy §3.2", "requirement": "Data minimization and purpose limitation", "status": "required"},
                {"policy": "GDPR Art. 5", "requirement": "Lawful basis for processing", "status": "required"},
                {"policy": "AI Governance Policy §4.1", "requirement": "Privacy Impact Assessment", "status": "required"},
            ])

        if "health" in data_types:
            risk_level = "CRITICAL"
            requirements.append(
                {"policy": "HIPAA", "requirement": "PHI encryption + access logging + BAA", "status": "required"}
            )

        if "financial" in data_types:
            risk_level = max(risk_level, "HIGH")
            requirements.append(
                {"policy": "PCI-DSS / SOX", "requirement": "Data tokenization before AI processing", "status": "required"}
            )

        if deployment_scope == "customer-facing":
            requirements.extend([
                {"policy": "AI Governance Policy §4.1", "requirement": "Bias and fairness testing", "status": "required"},
                {"policy": "Content Safety Policy", "requirement": "Input/output screening enabled", "status": "required"},
            ])

        # Universal requirements
        requirements.extend([
            {"policy": "AI Governance Policy §4.2", "requirement": "Continuous evaluation (≥10% sampling)", "status": "required"},
            {"policy": "AI Governance Policy §4.1", "requirement": "Security review and threat modeling", "status": "required"},
            {"policy": "SOC 2", "requirement": "Audit logging of all AI interactions", "status": "required"},
        ])

        return json.dumps({
            "use_case": use_case,
            "risk_level": risk_level,
            "data_types": data_types,
            "deployment_scope": deployment_scope,
            "requirements": requirements,
            "assessment_date": datetime.now(timezone.utc).isoformat(),
        }, indent=2)

    async def _risk_assessment_handler(
        self,
        system_description: str,
        regulations: list[str] | None = None,
    ) -> str:
        regulations = regulations or ["SOC2"]
        risk_categories = [
            {"category": "Data Privacy", "severity": "MEDIUM", "description": "AI system processes user data", "mitigation": "Implement PII filtering and data minimization"},
            {"category": "Model Reliability", "severity": "MEDIUM", "description": "LLM outputs may be inaccurate", "mitigation": "Deploy evaluation pipeline with groundedness checks"},
            {"category": "Security", "severity": "HIGH", "description": "Prompt injection and data exfiltration risks", "mitigation": "Content safety screening on all inputs/outputs"},
            {"category": "Bias & Fairness", "severity": "MEDIUM", "description": "Model may produce biased outputs", "mitigation": "Regular bias testing and diverse evaluation datasets"},
            {"category": "Operational", "severity": "LOW", "description": "System availability and performance", "mitigation": "Health monitoring, auto-scaling, and fallback responses"},
        ]

        return json.dumps({
            "system": system_description,
            "regulations": regulations,
            "risk_categories": risk_categories,
            "overall_risk": "MEDIUM",
            "recommendation": "Proceed with governance controls specified in mitigation column",
            "next_review_date": "90 days from deployment",
        }, indent=2)
