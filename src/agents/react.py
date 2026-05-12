"""ReAct Agent — Reasoning + Acting pattern with full thought traces.

Implements the ReAct (Reasoning + Acting) pattern from Yao et al. 2022:
  Thought → Action → Observation → Thought → ... → Final Answer

Key differentiators from a basic tool-calling loop:
1. Explicit reasoning traces — every step has a visible "Thought" explaining WHY
2. Self-critique — the agent can revise its plan after each observation
3. Bounded reasoning budget — prevents runaway token spend
4. Full trace export — every thought/action/observation is logged for debugging

This is what moves the system beyond a "wrapper" — the agent genuinely reasons
about multi-step problems, decomposes tasks, and adapts its strategy.

Production Engineering Patterns:
- Token budget enforcement (max tokens per reasoning chain)
- Latency tracking per thought/action cycle
- Thought-level observability (not just input/output)
- Graceful degradation when reasoning budget exhausted
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from src.agents.base import AgentContext, AgentResponse, AgentRole, AgentStep, BaseAgent
from src.config import CloudProvider, get_settings

logger = structlog.get_logger()


class ReActStepType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"
    SELF_CRITIQUE = "self_critique"


@dataclass
class ReActTrace:
    """One step in the ReAct reasoning chain."""

    step_type: ReActStepType
    content: str
    iteration: int
    latency_ms: float
    token_usage: dict[str, int] | None = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReActResult:
    """Complete result of a ReAct reasoning chain."""

    answer: str
    traces: list[ReActTrace]
    total_iterations: int
    total_latency_ms: float
    total_tokens: int
    reasoning_budget_exhausted: bool = False

    @property
    def thought_chain(self) -> list[str]:
        """Extract just the thought trace for debugging."""
        return [t.content for t in self.traces if t.step_type == ReActStepType.THOUGHT]

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "total_iterations": self.total_iterations,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "total_tokens": self.total_tokens,
            "reasoning_budget_exhausted": self.reasoning_budget_exhausted,
            "traces": [
                {
                    "step": t.step_type.value,
                    "content": t.content[:500],
                    "iteration": t.iteration,
                    "latency_ms": round(t.latency_ms, 2),
                }
                for t in self.traces
            ],
        }


REACT_SYSTEM_PROMPT = """\
{domain_instructions}

You solve problems by interleaving Thought, Action, and Observation steps
using the ReAct (Reasoning + Acting) pattern.

For EVERY step, you MUST output structured JSON:

When you need to think about the problem:
{{"step": "thought", "content": "<your reasoning about what to do next>"}}

When you need to use a tool:
{{"step": "action", "tool": "<tool_name>", "args": {{<tool_arguments>}}}}

When you want to critique your approach (optional, use when stuck):
{{"step": "self_critique", "content": "<what went wrong and how to adjust>"}}

When you have the final answer:
{{"step": "final_answer", "content": "<your complete answer>"}}

Rules:
1. ALWAYS start with a Thought before any Action
2. After each Observation, produce a Thought analyzing the result
3. Use self_critique if an approach isn't working
4. Maximum {max_iterations} reasoning steps
5. Be specific in your thoughts — explain WHY you're taking each action
6. When you have enough information, produce a final_answer immediately

Your available tools:
{tool_descriptions}
"""


class ReActAgent(BaseAgent):
    """Agent implementing the ReAct (Reasoning + Acting) pattern.

    Unlike a basic tool-calling loop, this agent:
    - Produces explicit reasoning traces (Thought → Action → Observation)
    - Can self-critique and revise its approach
    - Tracks token budget to prevent cost runaway
    - Exports full reasoning chains for observability
    """

    def __init__(
        self,
        name: str,
        role: AgentRole,
        description: str,
        max_iterations: int = 8,
        max_tokens_budget: int = 50000,
    ):
        super().__init__(name=name, role=role, description=description, max_iterations=max_iterations)
        self._max_tokens_budget = max_tokens_budget
        self._react_traces: list[ReActTrace] = []

    @property
    def domain_instructions(self) -> str:
        """Override in subclasses to inject domain-specific instructions."""
        return "You are a ReAct (Reasoning + Acting) agent."

    @property
    def system_prompt(self) -> str:
        tool_descs = "\n".join(
            f"- {schema['function']['name']}: {schema['function']['description']}"
            for schema in self._tool_schemas
        )
        return REACT_SYSTEM_PROMPT.format(
            domain_instructions=self.domain_instructions,
            max_iterations=self.max_iterations,
            tool_descriptions=tool_descs or "No tools available.",
        )

    async def run(self, message: str, context: AgentContext | None = None) -> AgentResponse:
        """Execute the ReAct loop with full reasoning traces."""
        context = context or AgentContext()
        context.parent_agent = self.name
        self._react_traces = []
        steps: list[AgentStep] = []
        total_tokens = 0

        settings = get_settings()
        processed_message = await self._pre_process(message, context)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": processed_message},
        ]

        for iteration in range(self.max_iterations):
            # Check token budget
            if total_tokens >= self._max_tokens_budget:
                logger.warning(
                    "react.budget_exhausted",
                    agent=self.name,
                    tokens=total_tokens,
                    budget=self._max_tokens_budget,
                )
                break

            # LLM call for next reasoning step
            start = time.perf_counter()
            response = await self._llm_call(messages, settings)
            latency = (time.perf_counter() - start) * 1000

            usage = self._extract_usage(response)
            total_tokens += usage.get("total_tokens", 0)

            raw_content = response.choices[0].message.content or ""
            messages.append({"role": "assistant", "content": raw_content})

            steps.append(AgentStep(
                step_type="react_step",
                agent_name=self.name,
                content={"iteration": iteration, "raw": raw_content[:300]},
                latency_ms=latency,
                token_usage=usage,
            ))

            # Parse the ReAct step
            parsed = self._parse_react_output(raw_content)

            if parsed["step"] == "thought":
                trace = ReActTrace(
                    step_type=ReActStepType.THOUGHT,
                    content=parsed["content"],
                    iteration=iteration,
                    latency_ms=latency,
                    token_usage=usage,
                )
                self._react_traces.append(trace)
                logger.info("react.thought", agent=self.name, iteration=iteration,
                          thought=parsed["content"][:200])

            elif parsed["step"] == "self_critique":
                trace = ReActTrace(
                    step_type=ReActStepType.SELF_CRITIQUE,
                    content=parsed["content"],
                    iteration=iteration,
                    latency_ms=latency,
                    token_usage=usage,
                )
                self._react_traces.append(trace)
                logger.info("react.self_critique", agent=self.name, iteration=iteration)

            elif parsed["step"] == "action":
                # Record the action
                action_trace = ReActTrace(
                    step_type=ReActStepType.ACTION,
                    content=json.dumps({"tool": parsed["tool"], "args": parsed["args"]}),
                    iteration=iteration,
                    latency_ms=latency,
                    token_usage=usage,
                    metadata={"tool": parsed["tool"]},
                )
                self._react_traces.append(action_trace)

                # Execute the tool
                tool_start = time.perf_counter()
                from src.agents.base import ToolCall
                tc = ToolCall(
                    id=str(uuid.uuid4()),
                    name=parsed["tool"],
                    arguments=parsed["args"],
                )
                result = await self._execute_tool(tc, context)
                tool_latency = (time.perf_counter() - tool_start) * 1000

                # Record the observation
                obs_trace = ReActTrace(
                    step_type=ReActStepType.OBSERVATION,
                    content=str(result)[:2000],
                    iteration=iteration,
                    latency_ms=tool_latency,
                    metadata={"tool": parsed["tool"]},
                )
                self._react_traces.append(obs_trace)

                steps.append(AgentStep(
                    step_type="tool_call",
                    agent_name=self.name,
                    content={"tool": parsed["tool"], "result_preview": str(result)[:200]},
                    latency_ms=tool_latency,
                ))

                # Feed observation back
                messages.append({
                    "role": "user",
                    "content": f"Observation: {result}",
                })

                logger.info("react.action", agent=self.name, tool=parsed["tool"],
                          iteration=iteration)

            elif parsed["step"] == "final_answer":
                trace = ReActTrace(
                    step_type=ReActStepType.FINAL_ANSWER,
                    content=parsed["content"],
                    iteration=iteration,
                    latency_ms=latency,
                    token_usage=usage,
                )
                self._react_traces.append(trace)

                final_content = await self._post_process(parsed["content"], context)

                logger.info(
                    "react.completed",
                    agent=self.name,
                    iterations=iteration + 1,
                    total_tokens=total_tokens,
                    trace_steps=len(self._react_traces),
                )

                return AgentResponse(
                    content=final_content,
                    agent_name=self.name,
                    context=context,
                    steps=steps,
                    metadata={
                        "react_traces": ReActResult(
                            answer=final_content,
                            traces=self._react_traces,
                            total_iterations=iteration + 1,
                            total_latency_ms=sum(s.latency_ms for s in steps),
                            total_tokens=total_tokens,
                        ).to_dict(),
                    },
                )

            else:
                # Unknown step type — treat as thought
                messages.append({
                    "role": "user",
                    "content": "Please respond with a valid JSON step: thought, action, self_critique, or final_answer.",
                })

        # Max iterations reached
        budget_exhausted = total_tokens >= self._max_tokens_budget
        logger.warning("react.max_iterations", agent=self.name,
                      budget_exhausted=budget_exhausted, tokens=total_tokens)

        # Synthesize from whatever we have
        thoughts = [t.content for t in self._react_traces if t.step_type == ReActStepType.THOUGHT]
        fallback = thoughts[-1] if thoughts else "Reasoning budget exhausted. Please refine your query."

        return AgentResponse(
            content=fallback,
            agent_name=self.name,
            context=context,
            steps=steps,
            metadata={
                "react_traces": ReActResult(
                    answer=fallback,
                    traces=self._react_traces,
                    total_iterations=self.max_iterations,
                    total_latency_ms=sum(s.latency_ms for s in steps),
                    total_tokens=total_tokens,
                    reasoning_budget_exhausted=budget_exhausted,
                ).to_dict(),
                "max_iterations_reached": True,
            },
        )

    async def _llm_call(self, messages: list[dict], settings) -> Any:
        """Make an LLM call — supports both Google Gemini and Azure OpenAI."""
        if settings.cloud_provider == CloudProvider.GOOGLE:
            return await self._gemini_call(messages, settings)
        else:
            return await self._azure_call(messages, settings)

    async def _gemini_call(self, messages: list[dict], settings) -> Any:
        """Call Gemini via google-genai SDK with OpenAI-compatible response wrapper."""
        from google import genai
        from google.genai import types

        client = get_gcp_genai_client()

        # Convert messages to Gemini format
        system_instruction = None
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(text=msg["content"])],
                ))
            elif msg["role"] == "assistant":
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part(text=msg["content"])],
                ))

        response = await client.aio.models.generate_content(
            model=settings.gcp_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
            ),
        )

        # Wrap in OpenAI-compatible structure for uniform handling
        return _GeminiResponseWrapper(response)

    async def _azure_call(self, messages: list[dict], settings) -> Any:
        """Call Azure OpenAI."""
        client = self._get_client()
        return await client.chat.completions.create(
            model=settings.azure_ai_chat_deployment,
            messages=messages,
            temperature=0.1,
        )

    def _extract_usage(self, response) -> dict[str, int]:
        """Extract token usage from response (works for both providers)."""
        if hasattr(response, "usage") and response.usage:
            return {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
            }
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _parse_react_output(self, raw: str) -> dict[str, Any]:
        """Parse structured ReAct output from the LLM."""
        # Try to extract JSON from the response
        raw = raw.strip()

        # Handle markdown code blocks
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        try:
            parsed = json.loads(raw)
            step = parsed.get("step", "thought")

            if step == "action":
                return {
                    "step": "action",
                    "tool": parsed.get("tool", ""),
                    "args": parsed.get("args", {}),
                    "content": "",
                }
            elif step in ("thought", "self_critique", "final_answer"):
                return {
                    "step": step,
                    "content": parsed.get("content", ""),
                    "tool": "",
                    "args": {},
                }
            else:
                return {"step": "thought", "content": raw, "tool": "", "args": {}}

        except (json.JSONDecodeError, KeyError):
            # If LLM didn't produce valid JSON, treat as a thought or final answer
            if any(kw in raw.lower() for kw in ["final answer", "in conclusion", "to summarize"]):
                return {"step": "final_answer", "content": raw, "tool": "", "args": {}}
            return {"step": "thought", "content": raw, "tool": "", "args": {}}


# === Gemini Response Wrapper ===

class _GeminiResponseWrapper:
    """Wraps google-genai response to match OpenAI's response structure."""

    def __init__(self, gemini_response):
        self._response = gemini_response

    @property
    def choices(self):
        return [_GeminiChoice(self._response)]

    @property
    def usage(self):
        metadata = getattr(self._response, "usage_metadata", None)
        if metadata:
            return _GeminiUsage(metadata)
        return None


class _GeminiChoice:
    def __init__(self, response):
        self.message = _GeminiMessage(response)
        self.finish_reason = "stop"


class _GeminiMessage:
    def __init__(self, response):
        self.content = response.text if hasattr(response, "text") else ""
        self.tool_calls = None

    def model_dump(self):
        return {"role": "assistant", "content": self.content}


class _GeminiUsage:
    def __init__(self, metadata):
        self.prompt_tokens = getattr(metadata, "prompt_token_count", 0) or 0
        self.completion_tokens = getattr(metadata, "candidates_token_count", 0) or 0
        self.total_tokens = getattr(metadata, "total_token_count", 0) or 0


# Re-export for convenience
from src.config import get_gcp_genai_client  # noqa: E402
