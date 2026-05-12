"""Base Agent — Production-grade agent with tool-calling loop.

Design Principles (Enterprise-Grade):
1. Structured tool calling with OpenAI function-calling protocol
2. Bounded execution (max iterations to prevent runaway costs)
3. Full observability (every step traced and logged)
4. Governance hooks (pre/post processing for safety & compliance)
5. Context propagation across agent boundaries
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from src.config import CloudProvider, get_azure_openai_client, get_gcp_genai_client, get_settings

logger = structlog.get_logger()


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    KNOWLEDGE = "knowledge"
    ANALYST = "analyst"
    GOVERNANCE = "governance"
    ARCHITECT = "architect"


@dataclass
class AgentContext:
    """Propagated across agent boundaries for tracing and governance."""

    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str | None = None
    tenant_id: str | None = None
    parent_agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class AgentStep:
    """One step in the agent's execution — for observability."""

    step_type: str  # "llm_call", "tool_call", "tool_result"
    agent_name: str
    content: Any
    latency_ms: float
    token_usage: dict[str, int] | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentResponse:
    """Structured response from an agent."""

    content: str
    agent_name: str
    context: AgentContext
    steps: list[AgentStep] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_latency_ms(self) -> float:
        return sum(s.latency_ms for s in self.steps)

    @property
    def total_tokens(self) -> int:
        return sum(
            (s.token_usage or {}).get("total_tokens", 0)
            for s in self.steps
        )


class BaseAgent:
    """Base agent with tool-calling loop and governance hooks.

    Subclasses override:
    - system_prompt: Define the agent's role and constraints
    - tools: Register available tools
    - _pre_process / _post_process: Governance hooks
    """

    def __init__(
        self,
        name: str,
        role: AgentRole,
        description: str,
        max_iterations: int = 10,
    ):
        self.name = name
        self.role = role
        self.description = description
        self.max_iterations = max_iterations
        self._tools: dict[str, callable] = {}
        self._tool_schemas: list[dict] = []
        self._client: Any | None = None

    @property
    def system_prompt(self) -> str:
        raise NotImplementedError

    def _get_client(self) -> Any:
        if self._client is None:
            settings = get_settings()
            if settings.cloud_provider == CloudProvider.GOOGLE:
                self._client = get_gcp_genai_client()
            else:
                self._client = get_azure_openai_client()
        return self._client

    async def _llm_call(self, messages: list[dict[str, Any]], settings) -> Any:
        if settings.cloud_provider == CloudProvider.GOOGLE:
            return await self._gemini_call(messages, settings)
        return await self._azure_call(messages, settings)

    async def _gemini_call(self, messages: list[dict[str, Any]], settings) -> Any:
        from google.genai import types

        client = self._get_client()

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
        return _GeminiResponseWrapper(response)

    async def _azure_call(self, messages: list[dict[str, Any]], settings) -> Any:
        client = self._get_client()
        return await client.chat.completions.create(
            model=settings.azure_ai_chat_deployment,
            messages=messages,
            temperature=0.1,
            tools=self._tool_schemas or None,
        )

    def register_tool(
        self,
        func: callable,
        name: str,
        description: str,
        parameters: dict[str, Any],
    ):
        """Register a tool with its OpenAI function schema."""
        self._tools[name] = func
        self._tool_schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        })

    async def _pre_process(self, message: str, context: AgentContext) -> str:
        """Governance hook — runs before LLM call. Override for PII filtering, etc."""
        return message

    async def _post_process(self, response: str, context: AgentContext) -> str:
        """Governance hook — runs after LLM response. Override for safety checks."""
        return response

    async def run(self, message: str, context: AgentContext | None = None) -> AgentResponse:
        """Execute the agent with a tool-calling loop.

        This implements the core agentic pattern:
        1. Send message + tools to LLM
        2. If LLM returns tool calls → execute tools → feed results back
        3. Repeat until LLM returns a final text response or max iterations hit
        """
        context = context or AgentContext()
        context.parent_agent = self.name
        steps: list[AgentStep] = []
        settings = get_settings()

        # Pre-process (governance)
        processed_message = await self._pre_process(message, context)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": processed_message},
        ]

        for iteration in range(self.max_iterations):
            start = time.perf_counter()

            response = await self._llm_call(messages, settings)
            latency = (time.perf_counter() - start) * 1000

            choice = response.choices[0]
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            } if response.usage else None

            steps.append(AgentStep(
                step_type="llm_call",
                agent_name=self.name,
                content={"iteration": iteration, "finish_reason": choice.finish_reason},
                latency_ms=latency,
                token_usage=usage,
            ))

            # If no tool calls → final response
            if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
                final_content = choice.message.content or ""
                final_content = await self._post_process(final_content, context)

                logger.info(
                    "agent.completed",
                    agent=self.name,
                    iterations=iteration + 1,
                    total_latency_ms=sum(s.latency_ms for s in steps),
                )

                return AgentResponse(
                    content=final_content,
                    agent_name=self.name,
                    context=context,
                    steps=steps,
                )

            # Execute tool calls
            messages.append(choice.message.model_dump())

            for tool_call in choice.message.tool_calls:
                tc = ToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=json.loads(tool_call.function.arguments),
                )

                tool_start = time.perf_counter()
                result = await self._execute_tool(tc, context)
                tool_latency = (time.perf_counter() - tool_start) * 1000

                steps.append(AgentStep(
                    step_type="tool_call",
                    agent_name=self.name,
                    content={"tool": tc.name, "args": tc.arguments, "result_preview": str(result)[:200]},
                    latency_ms=tool_latency,
                ))

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result),
                })

        # Max iterations reached
        logger.warning("agent.max_iterations", agent=self.name, max=self.max_iterations)
        return AgentResponse(
            content="I reached the maximum number of reasoning steps. Please refine your query.",
            agent_name=self.name,
            context=context,
            steps=steps,
            metadata={"max_iterations_reached": True},
        )

    async def _execute_tool(self, tool_call: ToolCall, context: AgentContext) -> str:
        """Execute a registered tool with error handling."""
        func = self._tools.get(tool_call.name)
        if not func:
            logger.error("agent.tool_not_found", tool=tool_call.name, agent=self.name)
            return f"Error: Tool '{tool_call.name}' not found."

        try:
            result = await func(**tool_call.arguments)
            logger.info("agent.tool_executed", tool=tool_call.name, agent=self.name)
            return result
        except Exception as e:
            logger.error("agent.tool_error", tool=tool_call.name, error=str(e), agent=self.name)
            return f"Error executing {tool_call.name}: {e}"


class _GeminiResponseWrapper:
    """Wrap google-genai responses to match the OpenAI chat completion shape."""

    def __init__(self, gemini_response: Any):
        self._response = gemini_response

    @property
    def choices(self) -> list["_GeminiChoice"]:
        return [_GeminiChoice(self._response)]

    @property
    def usage(self) -> "_GeminiUsage | None":
        metadata = getattr(self._response, "usage_metadata", None)
        if metadata:
            return _GeminiUsage(metadata)
        return None


class _GeminiChoice:
    def __init__(self, response: Any):
        self.message = _GeminiMessage(response)
        self.finish_reason = "stop"


class _GeminiMessage:
    def __init__(self, response: Any):
        self.content = response.text if hasattr(response, "text") else ""
        self.tool_calls = None

    def model_dump(self) -> dict[str, str]:
        return {"role": "assistant", "content": self.content}


class _GeminiUsage:
    def __init__(self, metadata: Any):
        self.prompt_tokens = getattr(metadata, "prompt_token_count", 0) or 0
        self.completion_tokens = getattr(metadata, "candidates_token_count", 0) or 0
        self.total_tokens = getattr(metadata, "total_token_count", 0) or 0
