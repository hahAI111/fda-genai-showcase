"""FDA Architecture Toolkit CLI.

Usage:
    fda                                    # Start copilot (default)
    fda copilot                            # Interactive chat with full agent pipeline
    fda scenario financial-compliance      # Load industry scenario → architecture rec
    fda search "query"                     # Direct hybrid search
    fda docs                               # List indexed documents
    fda health                             # Check platform health (requires running server)

Also works via: python -m src.cli [command]

The CLI connects directly to Azure services — no server needed for copilot/scenario mode.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

# Custom theme for the platform
theme = Theme({
    "agent": "bold cyan",
    "user": "bold green",
    "system": "bold yellow",
    "error": "bold red",
    "governance": "dim",
    "citation": "italic blue",
})

console = Console(theme=theme)


SCENARIO_CATALOG = {
    "financial-compliance": ("Financial Services", "Tier 1 Bank, 50K employees", "$5K/mo"),
    "healthcare-knowledge": ("Healthcare", "Hospital Network, 8 hospitals", "$8K/mo"),
    "manufacturing-qa": ("Manufacturing", "Auto Parts, 12 factories", "$10K/mo"),
    "retail-customer-service": ("Retail / E-Commerce", "Online Retailer, 5M customers", "$15K/mo"),
}

SCENARIO_ALIASES = {
    "1": "financial-compliance",
    "2": "healthcare-knowledge",
    "3": "manufacturing-qa",
    "4": "retail-customer-service",
    "finance": "financial-compliance",
    "financial": "financial-compliance",
    "bank": "financial-compliance",
    "healthcare": "healthcare-knowledge",
    "health": "healthcare-knowledge",
    "hospital": "healthcare-knowledge",
    "manufacturing": "manufacturing-qa",
    "factory": "manufacturing-qa",
    "retail": "retail-customer-service",
    "ecommerce": "retail-customer-service",
}


def _resolve_scenario_id(raw: str) -> str | None:
    normalized = (raw or "").strip().lower()
    if not normalized:
        return None
    if normalized in SCENARIO_CATALOG:
        return normalized
    return SCENARIO_ALIASES.get(normalized)


def _resolve_response_agent(response) -> str:
    routing = (response.metadata or {}).get("routing") if hasattr(response, "metadata") else None
    return (routing or {}).get("target_agent") or response.agent_name


def _init_platform():
    """Initialize agents, governance, and tools (same as server lifespan)."""
    from src.agents.analyst import AnalystAgent
    from src.agents.architect import ArchitectAgent
    from src.agents.governance_agent import GovernanceAgent
    from src.agents.knowledge import KnowledgeAgent
    from src.agents.orchestrator import OrchestratorAgent
    from src.evaluation.pipeline import EvaluationPipeline
    from src.governance.audit import AuditLogger
    from src.governance.content_safety import ContentSafety
    from src.governance.pii_filter import PIIFilter
    from src.observability.tracing import setup_logging
    from src.tools.search import AISearchTool
    from src.tools.storage import BlobStorageTool

    setup_logging()

    search_tool = AISearchTool()
    storage_tool = BlobStorageTool()

    orchestrator = OrchestratorAgent()
    orchestrator.register_agent(KnowledgeAgent(search_tool=search_tool))
    orchestrator.register_agent(AnalystAgent(search_tool=search_tool))
    orchestrator.register_agent(GovernanceAgent(search_tool=search_tool))
    orchestrator.register_agent(ArchitectAgent(search_tool=search_tool))

    return {
        "orchestrator": orchestrator,
        "content_safety": ContentSafety(),
        "pii_filter": PIIFilter(),
        "audit_logger": AuditLogger(),
        "eval_pipeline": EvaluationPipeline(),
        "search_tool": search_tool,
        "storage_tool": storage_tool,
    }


async def _chat_once(platform: dict, message: str, conversation_id: str) -> dict:
    """Run one chat turn through the full governance pipeline."""
    from src.agents.base import AgentContext
    from src.governance.content_safety import SafetyLevel

    start = time.perf_counter()
    ctx = AgentContext(conversation_id=conversation_id)

    # 1. Content safety — input
    safety = platform["content_safety"].screen_input(message)
    if safety.level == SafetyLevel.BLOCKED:
        return {"error": f"Blocked: {safety.message}"}

    # 2. PII masking
    masked, pii = platform["pii_filter"].mask(message)
    pii_info = [d.type for d in pii] if pii else []

    # 3. Orchestrate
    response = await platform["orchestrator"].route(masked, ctx)

    # 4. Content safety — output
    out_safety = platform["content_safety"].screen_output(response.content)
    content = response.content
    if out_safety.level == SafetyLevel.BLOCKED:
        content = "I'm unable to provide that response due to safety policies."

    latency = (time.perf_counter() - start) * 1000
    return {
        "content": content,
        "agent": _resolve_response_agent(response),
        "citations": response.citations,
        "tokens": response.total_tokens,
        "steps": len(response.steps),
        "latency_ms": round(latency, 1),
        "pii_masked": pii_info,
        "routing": response.metadata.get("routing"),
    }


def _try_open_diagram(content: str) -> None:
    """If the response mentions a generated diagram HTML file, open it in the browser."""
    import re
    import webbrowser
    match = re.search(r'(output[\\/][^\s"\'<>]+\.html)', content)
    if match:
        from pathlib import Path
        html_path = Path(__file__).resolve().parent.parent / match.group(1)
        if html_path.exists():
            console.print(f"[green]📊 Opening diagram: {html_path.name}[/green]")
            webbrowser.open(html_path.as_uri())


def _render_response(result: dict) -> None:
    """Render an agent response with rich formatting."""
    if "error" in result:
        console.print(f"\n[error]✗ {result['error']}[/error]\n")
        return

    # Agent badge
    agent_name = result.get("agent", "unknown")
    agent_colors = {
        "knowledge": "cyan",
        "analyst": "magenta",
        "governance": "yellow",
        "architect": "green",
    }
    color = agent_colors.get(agent_name, "white")

    # Response content as Markdown
    md = Markdown(result["content"])
    console.print()
    console.print(Panel(
        md,
        title=f"[bold {color}]◆ {agent_name.upper()} Agent[/bold {color}]",
        border_style=color,
        padding=(1, 2),
    ))

    # Metadata bar
    meta_parts = [
        f"[dim]⏱ {result['latency_ms']}ms[/dim]",
        f"[dim]🔢 {result['tokens']} tokens[/dim]",
        f"[dim]📊 {result['steps']} steps[/dim]",
    ]
    if result.get("pii_masked"):
        meta_parts.append(f"[yellow]🛡 PII masked: {', '.join(result['pii_masked'])}[/yellow]")
    if result.get("citations"):
        meta_parts.append(f"[citation]📄 {len(result['citations'])} citations[/citation]")

    console.print("  ".join(meta_parts))

    # Auto-open diagram if generated
    _try_open_diagram(result.get("content", ""))

    console.print()


def _print_banner() -> None:
    """Print the startup banner."""
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║         Enterprise GenAI Platform — FDA Architecture Toolkit    ║
║                                                                  ║
║  Multi-agent orchestration with governance & evaluation          ║
║  Type your question or describe a customer scenario.             ║
║  Type 'exit' or Ctrl+C to quit.                                 ║
║                                                                  ║
║  Commands:                                                       ║
║    /help                Show command help + examples             ║
║    /agents              List registered agents                   ║
║    /skills (/skill)     List available skills                    ║
║    /docs                List indexed documents                   ║
║    /search <query>      Direct hybrid search                     ║
║    /scenario <id>       Load an industry scenario                ║
║    /scenarios           List available scenarios                 ║
║    /diagram <desc>      Generate architecture diagram            ║
╚══════════════════════════════════════════════════════════════════╝"""
    console.print(banner, style="bold cyan")


def _print_help() -> None:
    table = Table(title="CLI Commands", border_style="cyan")
    table.add_column("Command", style="bold")
    table.add_column("Description")
    table.add_column("Example")
    table.add_row("/help", "Show command help", "/help")
    table.add_row("/agents", "List registered agents", "/agents")
    table.add_row("/skills", "List available skills", "/skills")
    table.add_row("/scenarios", "List scenarios", "/scenarios")
    table.add_row("/scenario <id>", "Load a scenario", "/scenario healthcare-knowledge")
    table.add_row("/search <query>", "Run hybrid search", "/search governance policy")
    table.add_row("/diagram <desc>", "Generate diagram", "/diagram multi-agent RAG flow")
    console.print(table)
    console.print("[dim]Tip: scenario id also accepts aliases like finance, healthcare, retail, or 1-4.[/dim]")


def _print_agents_table() -> None:
    """Print registered agents."""
    table = Table(title="Registered Agents", border_style="cyan")
    table.add_column("Agent", style="bold")
    table.add_column("Role")
    table.add_column("Description")
    table.add_row("orchestrator", "Router", "Intent classification → delegate to specialist")
    table.add_row("knowledge", "RAG", "Hybrid search + grounded answers with citations")
    table.add_row("analyst", "Analysis", "Structured insights, comparison, recommendations")
    table.add_row("governance", "Compliance", "Policy checking, risk assessment, audit")
    table.add_row("architect", "Architecture", "Design AI architectures, cost estimation, component selection")
    console.print(table)


async def cmd_copilot(_args: argparse.Namespace) -> None:
    """Interactive copilot session — direct agent access, no server needed."""
    import uuid

    console.print("\n[system]Initializing platform...[/system]")
    platform = _init_platform()
    console.print("[system]✓ Platform ready (4 agents, governance enabled)[/system]")

    _print_banner()

    conversation_id = str(uuid.uuid4())
    console.print(f"[dim]Session: {conversation_id}[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold green]You ▸ [/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[system]Goodbye![/system]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "/quit", "/exit"):
            console.print("[system]Goodbye![/system]")
            break

        # Slash commands
        if user_input.lower() == "/help":
            _print_help()
            continue
        if user_input.lower() == "/agents":
            _print_agents_table()
            continue
        if user_input.lower() in ("/skills", "/skill"):
            from src.skills import SkillRegistry
            from src.skills.search_skill import SearchSkill
            from src.skills.analysis_skill import AnalysisSkill
            from src.skills.compliance_skill import ComplianceSkill
            from src.skills.markdown_loader import load_markdown_skills
            from pathlib import Path

            reg = SkillRegistry()
            reg.register(SearchSkill())
            reg.register(AnalysisSkill())
            reg.register(ComplianceSkill())
            load_markdown_skills(Path(__file__).resolve().parent.parent / "skills", reg)

            table = Table(title="Registered Skills", border_style="cyan")
            table.add_column("Name", style="bold")
            table.add_column("Type")
            table.add_column("Description")
            for s in reg.list_skills():
                stype = "Markdown" if s.get("has_prompt") and not s.get("tools") else "Python"
                table.add_row(s["name"], stype, s["description"][:60] + "...")
            console.print(table)
            continue
        if user_input.lower() == "/docs":
            with console.status("[cyan]Listing documents from Azure Blob Storage...[/cyan]"):
                docs = platform["storage_tool"].list_documents()
            table = Table(title=f"Indexed Documents ({len(docs)})", border_style="cyan")
            table.add_column("Name", style="bold")
            table.add_column("Size", justify="right")
            table.add_column("Category")
            for d in docs:
                size_kb = f"{d['size'] / 1024:.1f} KB"
                cat = d.get("metadata", {}).get("category", "—")
                table.add_row(d["name"], size_kb, cat)
            console.print(table)
            continue
        if user_input.lower().startswith("/search "):
            query = user_input[8:].strip()
            if not query:
                console.print("[error]Usage: /search <query>[/error]")
                continue
            with console.status(f"[cyan]Searching: {query}[/cyan]"):
                results = await platform["search_tool"].search(query, top_k=5)
            if not results:
                console.print("[yellow]No results found.[/yellow]")
                continue
            table = Table(title=f"Search Results for '{query}'", border_style="cyan")
            table.add_column("#", style="dim", width=3)
            table.add_column("Title", style="bold")
            table.add_column("Category")
            table.add_column("Score", justify="right")
            table.add_column("Snippet")
            for i, r in enumerate(results, 1):
                snippet = r.get("content", "")[:80] + "..."
                score = f"{r.get('reranker_score', r.get('score', 0)):.2f}"
                table.add_row(str(i), r.get("title", "—"), r.get("category", "—"), score, snippet)
            console.print(table)
            continue

        # /scenarios — list available scenarios
        if user_input.lower() == "/scenarios":
            _print_scenarios_table()
            continue

        # /diagram <description> — generate architecture diagram
        if user_input.lower().startswith("/diagram "):
            desc = user_input[9:].strip()
            if not desc:
                console.print("[error]Usage: /diagram <architecture description>[/error]")
                continue
            diagram_prompt = (
                f"Generate an architecture diagram for: {desc}. "
                "Use the generate_diagram tool with appropriate Mermaid code."
            )
            with console.status(f"[cyan]Generating diagram: {desc}...[/cyan]"):
                result = await _chat_once(platform, diagram_prompt, conversation_id)
            _render_response(result)
            continue

        # /scenario <id> — load and discuss a scenario
        if user_input.lower().startswith("/scenario "):
            raw_scenario_id = user_input[10:].strip()
            scenario_id = _resolve_scenario_id(raw_scenario_id)
            if not raw_scenario_id:
                console.print("[error]Usage: /scenario <id>  (use /scenarios to list)[/error]")
                continue
            if not scenario_id:
                console.print(f"[error]Unknown scenario: '{raw_scenario_id}'.[/error]")
                console.print("[dim]Run /scenarios to list valid ids, or use aliases like finance/healthcare/retail/1-4.[/dim]")
                continue
            scenario_prompt = f"Load the '{scenario_id}' customer scenario and recommend an architecture. Use the load_scenario and search_patterns tools."
            with console.status(f"[cyan]Loading scenario: {scenario_id}...[/cyan]"):
                result = await _chat_once(platform, scenario_prompt, conversation_id)
            _render_response(result)
            continue

        if user_input.startswith("/"):
            console.print(f"[error]Unknown command: {user_input}[/error]")
            console.print("[dim]Run /help to view available commands.[/dim]")
            continue

        # Normal chat — send through full pipeline
        with console.status("[cyan]Thinking...[/cyan]"):
            result = await _chat_once(platform, user_input, conversation_id)

        _render_response(result)


def _print_scenarios_table() -> None:
    """Print available industry scenarios."""
    from pathlib import Path

    scenarios_dir = Path(__file__).resolve().parent.parent / "scenarios"
    table = Table(title="Available Industry Scenarios", border_style="green")
    table.add_column("ID", style="bold")
    table.add_column("Industry")
    table.add_column("Customer")
    table.add_column("Budget")

    if scenarios_dir.exists():
        for d in sorted(scenarios_dir.iterdir()):
            if d.is_dir() and d.name in SCENARIO_CATALOG:
                info = SCENARIO_CATALOG[d.name]
                table.add_row(d.name, info[0], info[1], info[2])

    console.print(table)
    console.print("[dim]Use /scenario <id> to load a scenario[/dim]")


async def cmd_scenario(args: argparse.Namespace) -> None:
    """Load an industry scenario and generate architecture recommendation."""
    import uuid

    scenario_id = _resolve_scenario_id(args.scenario_id or "")

    # Interactive picker if no scenario_id provided
    if scenario_id is None and args.scenario_id:
        console.print(f"[error]Unknown scenario id: {args.scenario_id}[/error]")
        console.print("[dim]Use one of: financial-compliance, healthcare-knowledge, manufacturing-qa, retail-customer-service[/dim]")
        return

    if scenario_id is None:
        scenarios = [
            ("1", "financial-compliance", "Financial Services", "Tier 1 Bank, 50K employees, $5K/mo"),
            ("2", "healthcare-knowledge", "Healthcare", "Hospital Network, 8 hospitals, $8K/mo"),
            ("3", "manufacturing-qa", "Manufacturing", "Auto Parts, 12 factories, $10K/mo"),
            ("4", "retail-customer-service", "Retail / E-Commerce", "Online Retailer, 5M customers, $15K/mo"),
        ]
        console.print("\n[bold]Select a scenario:[/bold]\n")
        for num, sid, industry, desc in scenarios:
            console.print(f"  [bold cyan]{num}[/bold cyan]. {industry} — {desc}")
        console.print()
        try:
            choice = console.input("[bold green]Enter number (1-4): [/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[system]Goodbye![/system]")
            return
        choice_map = {s[0]: s[1] for s in scenarios}
        scenario_id = choice_map.get(choice)
        if not scenario_id:
            console.print("[error]Invalid choice. Use 1-4.[/error]")
            return

    console.print("\n[system]Initializing platform...[/system]")
    platform = _init_platform()
    console.print("[system]✓ Platform ready[/system]\n")

    conversation_id = str(uuid.uuid4())

    # Show scenario info
    _print_scenarios_table()
    console.print(f"\n[bold green]Loading scenario: {scenario_id}[/bold green]\n")

    prompt = (
        f"Load the '{scenario_id}' customer scenario using the load_scenario tool. "
        f"Then search the architecture patterns knowledge base for relevant patterns. "
        f"Based on the scenario requirements, constraints, and budget, recommend a "
        f"complete architecture with component selection, cost estimate, risks, and "
        f"implementation roadmap."
    )

    with console.status("[cyan]Analyzing scenario and generating architecture recommendation...[/cyan]"):
        result = await _chat_once(platform, prompt, conversation_id)

    _render_response(result)

    # Continue with interactive follow-up
    console.print("[dim]You can now ask follow-up questions about this scenario. Type 'exit' to quit.[/dim]\n")
    while True:
        try:
            user_input = console.input("[bold green]You ▸ [/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[system]Goodbye![/system]")
            break
        if not user_input or user_input.lower() in ("exit", "quit"):
            console.print("[system]Goodbye![/system]")
            break
        with console.status("[cyan]Thinking...[/cyan]"):
            result = await _chat_once(platform, user_input, conversation_id)
        _render_response(result)


async def cmd_search(args: argparse.Namespace) -> None:
    """Direct hybrid search."""
    from src.tools.search import AISearchTool

    query = " ".join(args.query)
    console.print(f"[system]Searching: {query}[/system]")

    tool = AISearchTool()
    with console.status("[cyan]Hybrid search (vector + keyword + semantic ranking)...[/cyan]"):
        results = await tool.search(query, top_k=args.top)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        score = r.get("reranker_score", r.get("score", 0))
        category = r.get("category", "—")
        content = r.get("content", "")[:300]

        console.print(Panel(
            f"{content}...",
            title=f"[bold]#{i} {title}[/bold]  [dim]{category}  score={score:.2f}[/dim]",
            border_style="cyan",
        ))


async def cmd_docs(_args: argparse.Namespace) -> None:
    """List documents in Azure Blob Storage."""
    from src.tools.storage import BlobStorageTool

    tool = BlobStorageTool()
    with console.status("[cyan]Listing documents from Azure Blob Storage...[/cyan]"):
        docs = tool.list_documents()

    table = Table(title=f"Enterprise Documents ({len(docs)} files)", border_style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Size", justify="right")
    table.add_column("Category")
    table.add_column("Last Modified")

    for d in docs:
        size_kb = f"{d['size'] / 1024:.1f} KB"
        cat = d.get("metadata", {}).get("category", "—")
        modified = str(d.get("last_modified", "—"))[:19]
        table.add_row(d["name"], size_kb, cat, modified)

    console.print(table)


async def cmd_health(_args: argparse.Namespace) -> None:
    """Check platform health (requires running server)."""
    import httpx

    url = "http://127.0.0.1:8000/health"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=5)
            data = r.json()
    except httpx.ConnectError:
        console.print(f"[error]Cannot connect to {url} — is the server running?[/error]")
        console.print("[dim]Start with: uvicorn src.main:app --port 8000[/dim]")
        return

    table = Table(title="Platform Health", border_style="green")
    table.add_column("Component", style="bold")
    table.add_column("Status")

    table.add_row("Platform", f"[green]{data.get('status', '?')}[/green]")
    for agent, status in data.get("agents", {}).items():
        table.add_row(f"  Agent: {agent}", f"[green]{status}[/green]")
    for gov, enabled in data.get("governance", {}).items():
        color = "green" if enabled else "red"
        table.add_row(f"  Governance: {gov}", f"[{color}]{enabled}[/{color}]")

    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fda",
        description="FDA Architecture Toolkit — Interactive GenAI Architecture Advisor",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # copilot
    sub.add_parser("copilot", help="Interactive copilot chat session (direct agent access)")

    # scenario
    sp_scenario = sub.add_parser("scenario", help="Load industry scenario and generate architecture recommendation")
    sp_scenario.add_argument(
        "scenario_id",
        nargs="?",
        default=None,
        help="Scenario to load (id, alias, or 1-4; interactive picker if omitted)",
    )

    # search
    sp_search = sub.add_parser("search", help="Direct hybrid search against AI Search index")
    sp_search.add_argument("query", nargs="+", help="Search query")
    sp_search.add_argument("--top", type=int, default=5, help="Number of results")

    # docs
    sub.add_parser("docs", help="List indexed documents in Azure Blob Storage")

    # health
    sub.add_parser("health", help="Check platform health (requires running server)")

    args = parser.parse_args()

    # Default to copilot mode if no command specified
    if args.command is None:
        args.command = "copilot"

    handlers = {
        "copilot": cmd_copilot,
        "scenario": cmd_scenario,
        "search": cmd_search,
        "docs": cmd_docs,
        "health": cmd_health,
    }

    asyncio.run(handlers[args.command](args))


if __name__ == "__main__":
    main()
