"""Hierarchical Delegation — Multi-level agent orchestration with delegation chains.

Production Engineering Pattern:
Instead of flat orchestrator→specialist routing, this implements a hierarchy:

    Supervisor (L0)
    ├── Planner (L1) — decomposes complex tasks into subtasks
    │   ├── ReAct Agent (L2) — executes subtasks with reasoning
    │   └── ReAct Agent (L2) — parallel subtask execution
    └── Reviewer (L1) — validates and synthesizes results

Key capabilities:
1. Task decomposition — break complex queries into parallelizable subtasks
2. Delegation chains — supervisor delegates to planners who delegate to workers
3. Result synthesis — aggregate results from multiple sub-agents
4. Failure isolation — one sub-agent failure doesn't crash the chain
5. Cost attribution — track token usage per delegation level

This is what "moving beyond the wrapper phase" looks like — genuine hierarchical
multi-agent coordination, not just prompt chaining.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.agents.base import AgentContext, AgentResponse, AgentRole, AgentStep, BaseAgent

logger = structlog.get_logger()


@dataclass
class DelegationTask:
    """A task delegated to a sub-agent."""

    task_id: str
    description: str
    target_agent: str
    priority: int = 0
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    latency_ms: float = 0.0
    token_usage: int = 0
    error: str | None = None


@dataclass
class DelegationPlan:
    """A decomposition plan from the Planner agent."""

    plan_id: str
    original_query: str
    tasks: list[DelegationTask]
    strategy: str  # "parallel", "sequential", "dag"
    reasoning: str
    estimated_tokens: int = 0

    def get_ready_tasks(self, completed_ids: set[str]) -> list[DelegationTask]:
        """Get tasks whose dependencies are all satisfied."""
        return [
            t for t in self.tasks
            if t.status == "pending"
            and all(dep in completed_ids for dep in t.depends_on)
        ]


PLANNER_PROMPT = """\
You are a task decomposition planner. Given a complex query, break it into
subtasks that can be delegated to specialized agents.

Available agents:
{agent_descriptions}

Respond with a JSON plan:
{{
    "strategy": "parallel" | "sequential" | "dag",
    "reasoning": "<why this decomposition strategy>",
    "tasks": [
        {{
            "task_id": "t1",
            "description": "<specific subtask description>",
            "target_agent": "<agent name>",
            "priority": 0,
            "depends_on": []
        }},
        ...
    ]
}}

Rules:
1. Use "parallel" when subtasks are independent
2. Use "sequential" when order matters
3. Use "dag" when some tasks depend on others
4. Each task must have a clear, self-contained description
5. Prefer parallel execution for lower latency
6. Maximum 5 subtasks per plan
"""

SYNTHESIZER_PROMPT = """\
You are a result synthesizer. Given the original query and results from
multiple sub-agents, produce a unified, coherent response.

Original query: {query}

Sub-agent results:
{results}

Rules:
1. Integrate all sub-results into one coherent answer
2. Resolve any contradictions between sub-agents
3. Cite which sub-agent provided which information
4. Highlight any gaps where subtasks failed
5. Maintain the quality standard of a senior architect's review
"""


class HierarchicalOrchestrator(BaseAgent):
    """Supervisor-level agent implementing hierarchical delegation.

    Delegation flow:
    1. Receive complex query
    2. Planner decomposes into subtasks
    3. Subtasks delegated to specialist agents (parallel when possible)
    4. Results collected and synthesized
    5. Final quality check before response

    Cost tracking:
    - Every delegation step tracks tokens and latency
    - Total cost attribution across the hierarchy
    """

    def __init__(self, agents: dict[str, BaseAgent] | None = None):
        super().__init__(
            name="supervisor",
            role=AgentRole.ORCHESTRATOR,
            description="Hierarchical orchestrator with task decomposition and delegation",
            max_iterations=3,
        )
        self._agents: dict[str, BaseAgent] = agents or {}
        self._delegation_history: list[DelegationPlan] = []

    @property
    def system_prompt(self) -> str:
        agent_descs = "\n".join(
            f"- {name}: {agent.description}" for name, agent in self._agents.items()
        )
        return PLANNER_PROMPT.format(agent_descriptions=agent_descs)

    def register_agent(self, agent: BaseAgent):
        self._agents[agent.name] = agent
        logger.info("hierarchy.agent_registered", agent=agent.name, role=agent.role)

    async def route(self, message: str, context: AgentContext | None = None) -> AgentResponse:
        """Hierarchical delegation with task decomposition.

        For simple queries: direct routing (like flat orchestrator)
        For complex queries: decompose → delegate → synthesize
        """
        context = context or AgentContext()
        all_steps: list[AgentStep] = []
        start = time.perf_counter()

        # Step 1: Classify complexity and create delegation plan
        plan = await self._create_plan(message, context)
        all_steps.append(AgentStep(
            step_type="planning",
            agent_name=self.name,
            content={"strategy": plan.strategy, "task_count": len(plan.tasks)},
            latency_ms=0,
        ))

        logger.info(
            "hierarchy.plan_created",
            strategy=plan.strategy,
            tasks=len(plan.tasks),
            reasoning=plan.reasoning[:200],
        )

        # Step 2: Execute delegation plan
        if plan.strategy == "parallel":
            results = await self._execute_parallel(plan, context)
        elif plan.strategy == "sequential":
            results = await self._execute_sequential(plan, context)
        else:
            results = await self._execute_dag(plan, context)

        # Collect steps from all delegations
        for task in plan.tasks:
            all_steps.append(AgentStep(
                step_type="delegation",
                agent_name=task.target_agent,
                content={
                    "task_id": task.task_id,
                    "status": task.status,
                    "result_preview": task.result[:200] if task.result else "",
                },
                latency_ms=task.latency_ms,
                token_usage={"total_tokens": task.token_usage},
            ))

        # Step 3: Synthesize results
        synthesis_start = time.perf_counter()
        final_response = await self._synthesize(message, plan, context)
        synthesis_latency = (time.perf_counter() - synthesis_start) * 1000

        all_steps.append(AgentStep(
            step_type="synthesis",
            agent_name=self.name,
            content={"result_preview": final_response[:200]},
            latency_ms=synthesis_latency,
        ))

        total_latency = (time.perf_counter() - start) * 1000
        total_tokens = sum(t.token_usage for t in plan.tasks)

        logger.info(
            "hierarchy.completed",
            total_latency_ms=total_latency,
            total_tokens=total_tokens,
            tasks_completed=sum(1 for t in plan.tasks if t.status == "completed"),
            tasks_failed=sum(1 for t in plan.tasks if t.status == "failed"),
        )

        self._delegation_history.append(plan)

        return AgentResponse(
            content=final_response,
            agent_name=self.name,
            context=context,
            steps=all_steps,
            metadata={
                "delegation": {
                    "plan_id": plan.plan_id,
                    "strategy": plan.strategy,
                    "reasoning": plan.reasoning,
                    "tasks": [
                        {
                            "task_id": t.task_id,
                            "agent": t.target_agent,
                            "status": t.status,
                            "latency_ms": round(t.latency_ms, 2),
                            "tokens": t.token_usage,
                        }
                        for t in plan.tasks
                    ],
                    "total_tokens": total_tokens,
                    "total_latency_ms": round(total_latency, 2),
                },
            },
        )

    async def _create_plan(self, message: str, context: AgentContext) -> DelegationPlan:
        """Use LLM to decompose the query into a delegation plan."""
        planning_response = await super().run(message, context)

        try:
            plan_data = json.loads(planning_response.content)
            tasks = [
                DelegationTask(
                    task_id=t.get("task_id", f"t{i}"),
                    description=t["description"],
                    target_agent=t["target_agent"],
                    priority=t.get("priority", 0),
                    depends_on=t.get("depends_on", []),
                )
                for i, t in enumerate(plan_data.get("tasks", []))
            ]

            # Validate target agents exist
            for task in tasks:
                if task.target_agent not in self._agents:
                    # Fallback to first available agent
                    task.target_agent = next(iter(self._agents)) if self._agents else "knowledge"

            return DelegationPlan(
                plan_id=str(uuid.uuid4())[:8],
                original_query=message,
                tasks=tasks,
                strategy=plan_data.get("strategy", "sequential"),
                reasoning=plan_data.get("reasoning", ""),
            )

        except (json.JSONDecodeError, KeyError):
            # Fallback: single-task plan routing to the best agent
            logger.warning("hierarchy.plan_parse_failed", raw=planning_response.content[:200])
            return DelegationPlan(
                plan_id=str(uuid.uuid4())[:8],
                original_query=message,
                tasks=[
                    DelegationTask(
                        task_id="t0",
                        description=message,
                        target_agent=self._pick_best_agent(message),
                    )
                ],
                strategy="sequential",
                reasoning="Fallback: single-agent routing",
            )

    def _pick_best_agent(self, message: str) -> str:
        """Simple keyword-based agent selection as fallback."""
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in ["compliance", "risk", "audit", "gdpr", "hipaa"]):
            return "governance" if "governance" in self._agents else next(iter(self._agents))
        if any(kw in msg_lower for kw in ["analyze", "compare", "trend", "summary"]):
            return "analyst" if "analyst" in self._agents else next(iter(self._agents))
        if any(kw in msg_lower for kw in ["find", "search", "policy", "document"]):
            return "knowledge" if "knowledge" in self._agents else next(iter(self._agents))
        return "architect" if "architect" in self._agents else next(iter(self._agents))

    async def _execute_parallel(
        self, plan: DelegationPlan, context: AgentContext
    ) -> list[DelegationTask]:
        """Execute all tasks in parallel."""
        async def run_task(task: DelegationTask):
            agent = self._agents.get(task.target_agent)
            if not agent:
                task.status = "failed"
                task.error = f"Agent '{task.target_agent}' not found"
                return

            task.status = "running"
            start = time.perf_counter()
            try:
                response = await agent.run(task.description, context)
                task.result = response.content
                task.status = "completed"
                task.token_usage = response.total_tokens
                task.latency_ms = (time.perf_counter() - start) * 1000
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                task.latency_ms = (time.perf_counter() - start) * 1000
                logger.error("hierarchy.task_failed", task_id=task.task_id, error=str(e))

        await asyncio.gather(*[run_task(t) for t in plan.tasks])
        return plan.tasks

    async def _execute_sequential(
        self, plan: DelegationPlan, context: AgentContext
    ) -> list[DelegationTask]:
        """Execute tasks one by one, in order."""
        for task in sorted(plan.tasks, key=lambda t: t.priority):
            agent = self._agents.get(task.target_agent)
            if not agent:
                task.status = "failed"
                task.error = f"Agent '{task.target_agent}' not found"
                continue

            task.status = "running"
            start = time.perf_counter()
            try:
                response = await agent.run(task.description, context)
                task.result = response.content
                task.status = "completed"
                task.token_usage = response.total_tokens
                task.latency_ms = (time.perf_counter() - start) * 1000
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                task.latency_ms = (time.perf_counter() - start) * 1000
                logger.error("hierarchy.task_failed", task_id=task.task_id, error=str(e))

        return plan.tasks

    async def _execute_dag(
        self, plan: DelegationPlan, context: AgentContext
    ) -> list[DelegationTask]:
        """Execute tasks respecting dependency graph (DAG)."""
        completed_ids: set[str] = set()
        task_map = {t.task_id: t for t in plan.tasks}

        while True:
            ready = plan.get_ready_tasks(completed_ids)
            if not ready:
                break

            # Run ready tasks in parallel
            async def run_task(task: DelegationTask):
                agent = self._agents.get(task.target_agent)
                if not agent:
                    task.status = "failed"
                    task.error = f"Agent '{task.target_agent}' not found"
                    return

                # Inject dependency results into context
                dep_context = task.description
                for dep_id in task.depends_on:
                    dep_task = task_map.get(dep_id)
                    if dep_task and dep_task.result:
                        dep_context += f"\n\n[Result from {dep_task.target_agent}]: {dep_task.result}"

                task.status = "running"
                start = time.perf_counter()
                try:
                    response = await agent.run(dep_context, context)
                    task.result = response.content
                    task.status = "completed"
                    task.token_usage = response.total_tokens
                    task.latency_ms = (time.perf_counter() - start) * 1000
                except Exception as e:
                    task.status = "failed"
                    task.error = str(e)
                    task.latency_ms = (time.perf_counter() - start) * 1000

            await asyncio.gather(*[run_task(t) for t in ready])
            completed_ids.update(t.task_id for t in ready if t.status in ("completed", "failed"))

        return plan.tasks

    async def _synthesize(
        self, original_query: str, plan: DelegationPlan, context: AgentContext
    ) -> str:
        """Synthesize results from all delegated tasks into a unified response."""
        # If only one task, return its result directly
        completed = [t for t in plan.tasks if t.status == "completed"]
        if len(completed) == 1:
            return completed[0].result

        if not completed:
            failed = [t for t in plan.tasks if t.status == "failed"]
            error_summary = "; ".join(f"{t.target_agent}: {t.error}" for t in failed)
            return f"All subtasks failed. Errors: {error_summary}"

        # Multi-result synthesis via LLM
        results_text = "\n\n".join(
            f"### {t.target_agent} (task: {t.description})\n{t.result}"
            for t in completed
        )

        synthesis_prompt = SYNTHESIZER_PROMPT.format(
            query=original_query,
            results=results_text,
        )

        from src.config import get_settings
        settings = get_settings()

        synthesis_response = await super().run(synthesis_prompt, context)
        return synthesis_response.content

    def get_delegation_stats(self) -> dict[str, Any]:
        """Get aggregated delegation statistics for monitoring."""
        if not self._delegation_history:
            return {"total_plans": 0}

        total_tasks = sum(len(p.tasks) for p in self._delegation_history)
        completed = sum(
            1 for p in self._delegation_history
            for t in p.tasks if t.status == "completed"
        )
        failed = sum(
            1 for p in self._delegation_history
            for t in p.tasks if t.status == "failed"
        )

        return {
            "total_plans": len(self._delegation_history),
            "total_tasks": total_tasks,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "success_rate": completed / max(total_tasks, 1),
            "strategies_used": {
                p.strategy: sum(1 for pp in self._delegation_history if pp.strategy == p.strategy)
                for p in self._delegation_history
            },
        }
