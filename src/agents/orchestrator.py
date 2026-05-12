"""Orchestrator Agent — Intent-based routing to specialized agents.

This is the core of the multi-agent architecture. The orchestrator:
1. Classifies user intent
2. Routes to the best specialized agent
3. Manages cross-agent context propagation
4. Applies governance checks on the final response

Enterprise Pattern: Separation of concerns — each agent is an expert
in one domain, the orchestrator handles coordination.
"""

from __future__ import annotations

import json
import time

import structlog

from src.agents.base import AgentContext, AgentResponse, AgentRole, BaseAgent

logger = structlog.get_logger()

ROUTING_PROMPT = """\
You are the orchestrator of the **FDA Architecture Toolkit** — a tool built for
Field Development Architects (FDAs) to interactively design GenAI architectures
for customer engagements.

This toolkit helps FDAs:
- Load industry scenarios (financial compliance, healthcare, manufacturing, retail)
- Generate architecture recommendations with component selection and cost estimates
- Explore what-if scenarios (budget changes, cloud swaps, feature additions)
- Search architecture patterns (RAG, multi-agent, governance, cost optimization, evaluation, build-vs-buy)
- Compare cloud platforms and managed-vs-custom trade-offs

The platform itself is the reference implementation: it uses RAG with hybrid search,
multi-agent orchestration, governance pipeline, and evaluation framework — all running
on Azure (AI Search, OpenAI, Blob Storage).

Available agents:
{agent_descriptions}

Analyze the user's message and respond with a JSON object:
{{
    "intent": "<brief description of what the user wants>",
    "agent": "<agent name to route to>",
    "reasoning": "<why this agent is the best fit>",
    "refined_query": "<optionally rewrite the query for the target agent>"
}}

Rules:
- If the user asks "what can you do", "what is this", or about the toolkit's capabilities → route to "architect" with refined_query asking to describe the FDA Architecture Toolkit capabilities
- If the query is about designing AI architecture, choosing components, cost estimation, customer scenarios, build-vs-buy decisions, or technology selection → route to "architect"
- If the query is about finding information, policies, procedures → route to "knowledge"
- If the query needs data analysis, comparison, summarization of structured data → route to "analyst"
- If the query is about compliance, risk, audit, or governance → route to "governance"
- If unclear, default to "architect"
- Always provide a refined_query that helps the target agent understand exactly what's needed
"""


class OrchestratorAgent(BaseAgent):
    """Routes requests to specialized agents based on intent classification."""

    def __init__(self, agents: dict[str, BaseAgent] | None = None):
        super().__init__(
            name="orchestrator",
            role=AgentRole.ORCHESTRATOR,
            description="Routes requests to specialized agents",
        )
        self._agents: dict[str, BaseAgent] = agents or {}

    def register_agent(self, agent: BaseAgent):
        self._agents[agent.name] = agent
        logger.info("orchestrator.agent_registered", agent=agent.name, role=agent.role)

    @property
    def system_prompt(self) -> str:
        agent_descs = "\n".join(
            f"- {name}: {agent.description}" for name, agent in self._agents.items()
        )
        return ROUTING_PROMPT.format(agent_descriptions=agent_descs)

    async def route(self, message: str, context: AgentContext | None = None) -> AgentResponse:
        """Classify intent and delegate to the right specialized agent.

        Flow:
        1. LLM classifies intent → picks target agent
        2. Orchestrator delegates to target agent with refined query
        3. Target agent executes (with its own tool-calling loop)
        4. Orchestrator returns combined response with full trace
        """
        context = context or AgentContext()
        all_steps = []

        # Step 1: Intent classification
        start = time.perf_counter()
        routing_response = await super().run(message, context)
        routing_latency = time.perf_counter() - start
        all_steps.extend(routing_response.steps)

        # Parse routing decision
        try:
            routing = json.loads(routing_response.content)
            target_agent_name = routing.get("agent", "knowledge")
            refined_query = routing.get("refined_query", message)
            intent = routing.get("intent", "unknown")
        except (json.JSONDecodeError, AttributeError):
            logger.warning("orchestrator.routing_parse_failed", raw=routing_response.content)
            target_agent_name = "knowledge"
            refined_query = message
            intent = "fallback"

        logger.info(
            "orchestrator.routed",
            intent=intent,
            target=target_agent_name,
            routing_latency_ms=routing_latency * 1000,
        )

        # Step 2: Delegate to target agent
        target_agent = self._agents.get(target_agent_name)
        if not target_agent:
            logger.warning("orchestrator.agent_not_found", target=target_agent_name)
            target_agent = next(iter(self._agents.values())) if self._agents else None
            if not target_agent:
                return AgentResponse(
                    content="No specialized agents available.",
                    agent_name=self.name,
                    context=context,
                    steps=all_steps,
                )

        agent_response = await target_agent.run(refined_query, context)
        all_steps.extend(agent_response.steps)

        return AgentResponse(
            content=agent_response.content,
            agent_name=self.name,
            context=context,
            steps=all_steps,
            citations=agent_response.citations,
            metadata={
                "routing": {
                    "intent": intent,
                    "target_agent": target_agent_name,
                    "refined_query": refined_query,
                },
                "delegated_agent_metadata": agent_response.metadata,
            },
        )
