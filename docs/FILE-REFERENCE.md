# File Reference and Module Inventory

> Maintenance note (2026-05-12): parts of this document describe planned or historical modules.
> Runtime source of truth should be checked from `src/main.py`, `src/routers/`, `src/tools/`, and `.github/workflows/container-deploy.yml`.
> If this file conflicts with code, treat code as authoritative.

## 1. Overview

This document provides a complete file-by-file reference guide mapping source code modules to the architecture service layers defined in [ARCHITECTURE.md](ARCHITECTURE.md).

Each module entry includes:
- **Purpose**: What the module does
- **Service Layer**: Which architectural layer it belongs to (API, Orchestration, Agent, Tool, Data, Web)
- **Dependencies**: Internal and external imports
- **Test Coverage**: Related test files
- **Ownership**: Team responsible for this module

## 2. Root Project Files

### pyproject.toml
- **Purpose**: Python project metadata, dependencies, build configuration, tool settings (pytest, black, mypy)
- **Service Layer**: Project configuration (shared)
- **Key Dependencies**: FastAPI, Pydantic, azure-*, google-cloud-*, redis, sqlalchemy, playwright
- **Maintenance**: Kept current with security patches for all transitive dependencies
- **Change Control**: Any new dependency requires security review and cost impact analysis

### README.md, INDEX.md, ARCHITECTURE.md (and related docs)
- **Purpose**: Project documentation, architecture explanation, onboarding, interview prep
- **Ownership**: Platform architect + technical writing
- **Review Gate**: Updated before any major feature release or architecture change

---

## 3. Source Code Modules: src/

### 3.1 API Layer

#### src/main.py
- **Purpose**: FastAPI application entrypoint, HTTP server bootstrap, middleware orchestration, lifecycle management
- **Service Layer**: API Gateway
- **Key Responsibilities**:
  - Initialize FastAPI app with lifespan context manager
  - Register all route handlers (from routers/*, agents/*, tools/*)
  - Configure CORS, security headers, request logging
  - Setup error handlers (400, 401, 403, 404, 500)
  - Initialize telemetry and observability pipelines
  - Health checks and readiness probes
  - Startup: load config, connect to databases, initialize caches, warm up embeddings
  - Shutdown: flush audit logs, close connections, cleanup temp files
- **Key Exports**:
  - `app`: FastAPI application instance (ASGI)
  - `lifespan()`: Async context manager for startup/shutdown
- **Test Coverage**: `tests/test_api_smoke.py`, `tests/test_api_runtime_readiness.py`
- **Ownership**: Platform backend team
- **Dependencies**:
  - `fastapi` (HTTP framework)
  - `src.config` (environment and runtime config)
  - `src.auth` (authentication middleware)
  - `src.governance` (input/output safety guardrails)
  - `src.observability` (tracing, logging)
  - `src.routers` (all endpoint routers)

#### src/__main__.py
- **Purpose**: CLI entry point for running the application via `python -m src`
- **Service Layer**: API (deployment helper)
- **Implementation**: Delegates to uvicorn server with configurable host/port
- **Usage**: `python -m src` or `python -m src --host 0.0.0.0 --port 8000`

#### src/cli.py
- **Purpose**: Command-line interface for administrative tasks (not user-facing)
- **Service Layer**: Operations/DevOps tooling
- **Subcommands**:
  - `skill-validate`: Verify SKILL.md syntax and frontmatter
  - `index-reset`: Rebuild search index from source documents
  - `user-delete`: GDPR deletion request execution
  - `audit-export`: Export audit logs for compliance reporting
  - `metrics-report`: Generate LLM cost and performance report
- **Dependencies**: `click` (CLI framework), `src.agents`, `src.tools`, `src.governance`

### 3.2 Configuration and Runtime

#### src/config.py
- **Purpose**: Environment variable parsing, credential loading, service endpoints, feature flags, SLO thresholds
- **Service Layer**: Configuration (shared across all layers)
- **Key Classes**:
  - `EnvConfig`: Reads from environment (AZURE_*, GOOGLE_*, REDIS_*, etc.)
  - `AppConfig`: Runtime config derived from EnvConfig + BMAD phase
  - `FeatureFlags`: Toggle features (e.g., enable_hierarchical_orchestration, enable_media_generation)
  - `SLOThresholds`: Latency budgets (TTFT_SLO_MS, TOKENS_PER_SEC_SLO)
- **Usage**: Injected as dependency in main.py and all endpoints
- **Validation**: Pydantic model ensures type safety and catches missing/invalid env vars at startup
- **Ownership**: Platform infrastructure team
- **Related Files**: `.env` (local development, NOT checked in), `.env.example` (template)

#### src/__init__.py
- **Purpose**: Package initialization, version exports
- **Exports**: `__version__`, `__app_name__`

### 3.3 Authentication and Security

#### src/auth/
- **Purpose**: Identity verification, token validation, role-based access control
- **Service Layer**: Security middleware
- **Module Structure**:
  - `__init__.py`: Export public API
  - `azure_auth.py`: Azure DefaultAzureCredential + OAuth 2.0 token validation
  - `google_auth.py`: Google Cloud ADC + OIDC token validation
  - `rbac.py`: Role definitions, permission checks (Admin, Analyst, User)
  - `middleware.py`: Middleware decorator for FastAPI endpoints

#### src/auth/azure_auth.py
- **Purpose**: Azure AD identity provider integration
- **Key Functions**:
  - `get_azure_credential()`: Return DefaultAzureCredential (respects AzureCliCredential, EnvironmentCredential, ManagedIdentityCredential)
  - `validate_azure_token(token)`: Verify JWT signature, expiry, scopes
  - `get_user_info(token)`: Extract user ID, email, organization from token claims
- **Dependencies**: `azure-identity`, `PyJWT`
- **Ownership**: Identity and access management team

#### src/auth/google_auth.py
- **Purpose**: Google Cloud identity provider integration
- **Key Functions**:
  - `get_google_credential()`: Return ADC (respects GOOGLE_APPLICATION_CREDENTIALS)
  - `validate_google_token(token)`: Verify OIDC token via Google public keys
  - `get_user_info(token)`: Extract user ID, email, organization
- **Dependencies**: `google-auth`, `google-auth-httplib2`

#### src/auth/rbac.py
- **Purpose**: Role-based access control (RBAC) definitions and enforcement
- **Key Classes**:
  - `Role`: Enum (ADMIN, ANALYST, USER)
  - `Permission`: Enum (READ, WRITE, DELETE, AUDIT, ADMIN)
  - `RolePermissionMap`: Matrix defining which roles have which permissions
- **Key Functions**:
  - `require_role(role: Role)`: FastAPI dependency decorator
  - `check_permission(user: User, permission: Permission)`: Boolean check
- **Ownership**: Security team

#### src/auth/middleware.py
- **Purpose**: FastAPI middleware for automatic auth validation on all requests
- **Key Classes**:
  - `AuthMiddleware`: Extracts token from Authorization header, validates, attaches user context to request
- **Behavior**:
  - Skip auth for public routes (e.g., `/health`, `/docs`)
  - Return 401 Unauthorized if token missing or invalid
  - Return 403 Forbidden if user lacks required permission for endpoint

### 3.4 Governance and Compliance

#### src/governance/
- **Purpose**: Safety controls, policy compliance, audit logging, GDPR data handling
- **Service Layer**: Governance middleware (runs on all input/output paths)
- **Module Structure**:
  - `__init__.py`: Export public API
  - `pii_filter.py`: Mask PII before sending to LLM
  - `content_safety.py`: Check prompt/response for harmful content
  - `audit_logger.py`: Log all requests, responses, decisions
  - `gdpr_controller.py`: Handle data access/deletion/retention
  - `risk_assessor.py`: Score governance risk on each request

#### src/governance/pii_filter.py
- **Purpose**: Detect and mask PII (email, phone, SSN, credit card, address) before model invocation
- **Key Functions**:
  - `detect_pii(text)`: Return list of (type, value, position) tuples
  - `mask_pii(text)`: Replace PII with [PII_EMAIL], [PII_PHONE], etc.
  - `redact_response(text, original_pii)`: Remove PII from model response to avoid leakage
- **Dependencies**: `presidio-analyzer`, `presidio-anonymizer` (Microsoft PII detection)
- **Behavior**: Runs pre-LLM (governance input guardrail) and post-LLM (governance output guardrail)

#### src/governance/content_safety.py
- **Purpose**: Detect harmful content, injections, and policy violations
- **Key Functions**:
  - `check_content_safety(text)`: Call Azure Content Safety API
  - `score_harm_categories(scores)`: Aggregate scores for hate, violence, sexual, self-harm
  - `enforce_safety_policy(text, threshold)`: Block if risk exceeds threshold
- **Dependencies**: `azure-ai-contentsafety`
- **Ownership**: Security and compliance team

#### src/governance/audit_logger.py
- **Purpose**: Immutable audit trail for all requests, decisions, data access
- **Key Functions**:
  - `log_request(user_id, endpoint, input, timestamp)`: Record incoming request
  - `log_decision(user_id, decision_type, reasoning, outcome)`: Record governance decision
  - `log_data_access(user_id, data_type, scope, timestamp)`: Record GDPR data access
  - `export_audit_trail(user_id, start_date, end_date)`: Retrieve user's audit records
- **Storage**: PostgreSQL `audit_trails` table with append-only semantics
- **Dependencies**: `src.tools.postgres_store`
- **Ownership**: Compliance and security team

#### src/governance/gdpr_controller.py
- **Purpose**: Handle GDPR obligations (Article 15 right to access, Article 17 right to erasure, Article 5 data minimization)
- **Key Functions**:
  - `process_data_access_request(user_id)`: Gather all user data from PostgreSQL, Cosmos, Blob Storage
  - `process_deletion_request(user_id, reason)`: Delete user data from all systems
  - `process_retention_policy()`: Clean up data older than retention window
  - `verify_consent(user_id, data_type)`: Check if user consented to processing
- **Behavior**:
  - Data access: encrypted export + delivery via secure channel
  - Deletion: synchronous delete with 7-day grace period before actual purge
  - Retention: automated cleanup per policy (90 days media, 365 days audit)
- **Dependencies**: `src.tools.postgres_store`, `src.tools.cosmos_store`, `src.tools.storage`
- **Ownership**: Data protection officer (DPO) + compliance team

#### src/governance/risk_assessor.py
- **Purpose**: Score governance risk on each request (is this request risky? does it need escalation?)
- **Key Classes**:
  - `RiskScore`: Dataclass with subcategory scores (pii_risk, safety_risk, policy_risk, etc.)
  - `RiskThreshold`: Configuration for risk levels (LOW, MEDIUM, HIGH, CRITICAL)
- **Key Functions**:
  - `assess_request_risk(request, user, context)`: Aggregate all risk signals
  - `should_escalate(risk_score)`: Boolean decision to block or flag for human review
  - `apply_mitigations(text, risk_score)`: Suggest guardrails (e.g., disable media generation)
- **Behavior**: High-risk requests may timeout to 3-tier escalation (support agent → analyst → admin)

### 3.5 Observability and Metrics

#### src/observability/
- **Purpose**: Tracing, logging, structured telemetry
- **Service Layer**: Observability middleware
- **Module Structure**:
  - `__init__.py`: Export public API
  - `logger.py`: Structured JSON logging
  - `tracing.py`: OpenTelemetry spans for distributed tracing
  - `telemetry_encoder.py`: Format telemetry for PostgreSQL ingest

#### src/observability/logger.py
- **Purpose**: Structured JSON logging with request context
- **Key Functions**:
  - `get_logger(name)`: Return Python logger configured for JSON output
  - `log_request(level, endpoint, payload)`: Log with structured fields
  - `log_agent_action(agent, action, tool, result)`: Log ReAct step
- **Behavior**: All logs include request_id, user_id, timestamp, trace_id for correlation
- **Output**: stdout (JSON format) → collected by Docker, App Service, or ELK

#### src/observability/tracing.py
- **Purpose**: Distributed tracing with OpenTelemetry
- **Key Functions**:
  - `get_tracer()`: Return OpenTelemetry tracer instance
  - `span_for_endpoint(endpoint_name)`: Create parent span for HTTP request
  - `span_for_agent_action(agent_name, action)`: Create child span for agent step
- **Spans Recorded**:
  - Request received → response sent (request span)
    - -> Orchestration routing (orchestrator span)
      - -> Agent execution (agent span)
        - -> Tool invocation (tool span)
- **Backends**: Azure App Insights, Google Cloud Trace, Jaeger
- **Ownership**: SRE team

### 3.6 Metrics and Evaluation

#### src/metrics/
- **Purpose**: LLM-native metrics collection, cost tracking, quality signals, SLO enforcement
- **Service Layer**: Metrics and evaluation pipeline
- **Module Structure**:
  - `__init__.py`: Export public API
  - `llm_metrics.py`: Token count, latency, cost per request
  - `quality_metrics.py`: User satisfaction, correctness, groundedness
  - `slo_enforcement.py`: Check against latency/throughput SLO targets
  - `cost_tracker.py`: Aggregate cost by user, agent, model

#### src/metrics/llm_metrics.py
- **Purpose**: Track LLM-specific metrics per request
- **Key Classes**:
  - `LLMMetrics`: Dataclass with input_tokens, output_tokens, latency_ms, cost_usd, ttft_ms (time-to-first-token)
  - `ModelCostMap`: Look up cost per token for each LLM (e.g., gpt-4: $0.03/$0.06, gemini-2.5: $0.02/$0.04)
- **Key Functions**:
  - `record_llm_call(model, input_tokens, output_tokens, latency_ms)`: Create LLMMetrics
  - `calculate_cost(model, tokens)`: Look up and compute cost
  - `record_ttft(model, start_time, first_token_time)`: Measure time-to-first-token
- **Storage**: PostgreSQL `telemetry_logs` table
- **Ownership**: Platform architect + finance

#### src/metrics/quality_metrics.py
- **Purpose**: Measure RAG answer quality, agent correctness, user satisfaction
- **Key Classes**:
  - `QualityMetrics`: User satisfaction (CSAT 1-5), answer correctness (0-100), groundedness (is answer supported by citations?)
  - `GroundednessChecker`: LLM evaluator to score if answer is grounded in retrieved context
- **Key Functions**:
  - `evaluate_rag_answer(question, answer, context)`: Score groundedness
  - `evaluate_agent_decision(agent_output, expected_output)`: Score correctness
  - `record_user_feedback(request_id, csat, feedback_text)`: Capture user satisfaction
- **Storage**: PostgreSQL `feedback_signals` table, Cosmos `media_quality` collection
- **Ownership**: Product team + data science

#### src/metrics/slo_enforcement.py
- **Purpose**: Enforce Service Level Objectives (SLOs) on latency, throughput, cost
- **Key Functions**:
  - `check_latency_slo(endpoint, actual_ms)`: Return pass/fail against threshold (e.g., 2000ms)
  - `check_throughput_slo(tokens_per_second)`: Return pass/fail against target (e.g., 100 tok/s)
  - `track_slo_breach(metric, actual, threshold)`: Log SLO miss for alerting
- **Thresholds** (from src/config.py):
  - `LATENCY_SLO_MS`: 2000 (p99 response time)
  - `TOKENS_PER_SEC_SLO`: 100
  - `COST_PER_REQUEST_SLO`: $0.10
- **Ownership**: SRE team

#### src/metrics/cost_tracker.py
- **Purpose**: Aggregate and report LLM costs
- **Key Functions**:
  - `get_cost_by_user(user_id, period)`: Sum cost for user in time period
  - `get_cost_by_agent(agent_name, period)`: Sum cost by agent
  - `get_cost_by_model(model_name, period)`: Sum cost by LLM model
  - `forecast_monthly_cost()`: Project end-of-month spend
- **Output**: Dashboard charts in customer_home.html

### 3.7 Feedback and Product Loop

#### src/feedback/
- **Purpose**: Capture user friction signals and transform into feature requests
- **Service Layer**: Product feedback loop
- **Module Structure**:
  - `__init__.py`: Export public API
  - `friction_detector.py`: Identify UX friction (timeout, error, slow response)
  - `feature_request_generator.py`: Convert friction into actionable feature requests
  - `feedback_storage.py`: Persist friction and feature requests

#### src/feedback/friction_detector.py
- **Purpose**: Identify UX friction signals (high latency, errors, retries)
- **Key Classes**:
  - `FrictionSignal`: Type, severity, context (endpoint, user, timestamp, error_msg)
- **Key Functions**:
  - `detect_timeout(request_time_ms, slo_ms)`: Flag if latency exceeds SLO
  - `detect_error(response_status, error_type)`: Flag HTTP errors and exceptions
  - `detect_retry_storm(request_id, retry_count)`: Flag if user retries > 3x
  - `detect_long_queue(queue_depth, wait_time)`: Flag if request waited too long
- **Storage**: PostgreSQL `friction_signals` table with daily aggregation
- **Ownership**: Product and UX team

#### src/feedback/feature_request_generator.py
- **Purpose**: Convert friction signals into structured feature requests
- **Key Functions**:
  - `generate_from_friction(friction_signal)`: Create feature request
  - `prioritize_requests(signals)`: Score by frequency and impact
  - `group_requests(requests)`: Cluster by theme (e.g., "slow media generation", "RAG precision")
- **Example Transformations**:
  - 10 timeouts on `/media/video` → Feature request: "Add async video status polling"
  - 5 low groundedness scores on RAG → Feature request: "Improve citation filtering"
  - 3 retry storms on `/chat` → Feature request: "Add request queuing with priority"
- **Storage**: PostgreSQL `feature_requests` table
- **Ownership**: Product manager

### 3.8 Agents Layer

#### src/agents/
- **Purpose**: Multi-agent orchestration, ReAct reasoning, hierarchical delegation
- **Service Layer**: Orchestration + Specialist agents
- **Module Structure**:
  - `__init__.py`: Export public API
  - `orchestrator.py`: Flat intent routing
  - `hierarchy.py`: Hierarchical delegation (plan → delegate → synthesize)
  - `react.py`: ReAct reasoning engine (Thought → Action → Observation)
  - `knowledge.py`: Knowledge agent (RAG retrieval)
  - `analyst.py`: Analyst agent (structured analysis, comparison)
  - `governance_agent.py`: Governance agent (policy checks, risk assessment)
  - `architect.py`: Architecture agent (design tradeoffs, recommendations)
  - `media_agent.py`: Media agent (image, video, PPT generation)
  - `base.py`: Base agent class and interfaces

#### src/agents/base.py
- **Purpose**: Abstract base class for all agents
- **Key Classes**:
  - `Agent`: Abstract base with `execute(input, context)` method
  - `AgentResponse`: Dataclass with output, reasoning_trace, citations, metrics
  - `Tool`: Interface for agent tools (invoke, validate args)
- **Key Functions**:
  - `register_skill(skill_name, skill_module)`: Load reusable skill module (from SKILL.md)
  - `validate_agent_output(output, schema)`: Type-check and sanitize output
- **Ownership**: Platform architect

#### src/agents/orchestrator.py
- **Purpose**: Intent classification and flat routing to specialist agents
- **Service Layer**: Flat Orchestrator (for simple, single-step requests)
- **Key Classes**:
  - `Orchestrator(Agent)`: Routes request to best specialist
  - `IntentClassifier`: LLM-based intent detector (question type, urgency, complexity)
- **Key Functions**:
  - `classify_intent(user_input)`: Return intent type + confidence
  - `route_to_agent(intent)`: Select specialist agent (knowledge, analyst, governance, media)
  - `execute(user_input, context)`: Classify, route, execute, synthesize response
- **Routing Examples**:
  - "What policies apply to PII?" → Governance agent (policy + risk check)
  - "Compare these two architectures" → Analyst agent (structured comparison)
  - "Generate a logo" → Media agent (image generation)
  - "Find docs on RAG" → Knowledge agent (retrieval + citation)
- **Metrics**: Record routing decision, latency, cost per intent type
- **Ownership**: Platform architect

#### src/agents/hierarchy.py
- **Purpose**: Hierarchical agent orchestration for complex, multi-step tasks
- **Service Layer**: Hierarchical Orchestrator
- **Key Classes**:
  - `HierarchicalOrchestrator(Agent)`: Plan → Delegate → Synthesize pattern
  - `Plan`: Structured plan with steps, dependencies, agent assignments
  - `PlanningSupervisor`: Creates and updates plans
  - `DelegationCoordinator`: Orchestrates step execution in dependency order
- **Key Functions**:
  - `plan(objective)`: Break objective into steps, assign to agents
  - `delegate(plan)`: Execute steps in order, handle retries/errors
  - `synthesize(outputs)`: Combine step outputs into final response
  - `execute(objective, context)`: Orchestrate full workflow
- **Example Workflow** (from ARCHITECTURE.md):
  - Objective: "Assess compliance risk of this feature for GDPR and HIPAA"
  - Plan:
    1. Analyst: Compare feature against GDPR requirements → Risk assessment
    2. Governance agent: Check policy compliance → Recommendations
    3. Analyst: Synthesize findings → Executive summary
  - Synthesize: Combine all outputs + reasoning traces into final report
- **Fallback**: If plan fails, orchestrator rolls back and re-plans with reduced scope
- **Ownership**: Platform architect

#### src/agents/react.py
- **Purpose**: ReAct reasoning engine (Thought → Action → Observation loop)
- **Service Layer**: ReAct Runtime
- **Key Classes**:
  - `ReActRunner`: Manages reasoning loop
  - `ReActStep`: Dataclass with (thought, action, observation, reasoning)
- **Key Functions**:
  - `run(task, max_steps)`: Execute ReAct loop until task solved or max steps reached
  - `execute_step(current_state)`: Generate thought → select action → observe result
  - `format_reasoning_trace()`: Pretty-print thought-action-observation chain
- **Behavior**:
  - Model generates next thought in natural language (e.g., "I need to find policies on data retention")
  - Model selects action and tool (e.g., action="search", tool="knowledge_retrieval", args={query=...})
  - Tool executes and returns observation (e.g., "Found 3 docs on retention")
  - Model updates state with new information and repeats
  - Loop terminates when model outputs "Final Answer:" or max_steps reached
- **Reasoning Trace Storage**: Persisted in response for transparency and audit
- **Ownership**: Platform architect

#### src/agents/knowledge.py
- **Purpose**: Knowledge retrieval agent (RAG: question → search → rank → answer)
- **Service Layer**: Knowledge specialist agent
- **Key Classes**:
  - `KnowledgeAgent(Agent)`: Orchestrates RAG workflow
- **Key Functions**:
  - `retrieve(question)`: Hybrid search (semantic + vector + keyword)
  - `rerank(results, question)`: Semantic rerank to top K results
  - `generate_answer(question, context)`: LLM-grounded answer with citations
  - `execute(question, context)`: Full RAG pipeline
- **Citations**: Each answer includes [source-id] markers linked to retrieved chunks
- **Metrics**: Record search latency, retrieval precision, answer groundedness
- **Dependencies**: `src.tools.search`, AI Search API
- **Ownership**: RAG + data team

#### src/agents/analyst.py
- **Purpose**: Analyst agent (structured analysis, comparison, trend analysis)
- **Service Layer**: Analyst specialist agent
- **Key Classes**:
  - `AnalystAgent(Agent)`: Orchestrates analysis workflows
- **Key Functions**:
  - `compare_entities(entity_a, entity_b)`: Structured comparison (features, tradeoffs, winner)
  - `analyze_trends(data_points)`: Identify patterns, predict next period
  - `summarize_findings(analysis)`: Executive summary with key insights
  - `execute(task_type, input_data)`: Route to appropriate analysis function
- **Output Format**: Structured JSON with findings, evidence, recommendations
- **Ownership**: Analytics + data science team

#### src/agents/governance_agent.py
- **Purpose**: Governance agent (policy checks, risk assessment, audit)
- **Service Layer**: Governance specialist agent
- **Key Classes**:
  - `GovernanceAgent(Agent)`: Assesses governance risk
- **Key Functions**:
  - `check_policy_compliance(feature, policies)`: Is feature compliant?
  - `assess_security_risk(feature, threat_model)`: What are risks?
  - `assess_gdpr_risk(feature)`: GDPR Article compliance (1-99)
  - `execute(feature, context)`: Full governance assessment
- **Output**: Risk score (0-100), specific policy violations, remediation recommendations
- **Dependencies**: Policy definitions (from rules/), threat models
- **Ownership**: Security and compliance team

#### src/agents/architect.py
- **Purpose**: Architecture agent (design tradeoffs, recommendations)
- **Service Layer**: Architect specialist agent (optional, for complex design reviews)
- **Key Functions**:
  - `evaluate_architecture(design)`: Score against quality attributes (scalability, resilience, security, cost)
  - `compare_architectures(design_a, design_b)`: Structured comparison
  - `recommend_improvements(design)`: Identify bottlenecks and alternatives
  - `execute(design, objectives)`: Full architecture evaluation
- **Output**: Architecture assessment with tradeoffs, risk, and recommendations
- **Ownership**: Platform architect

#### src/agents/media_agent.py
- **Purpose**: Media agent (image, video, PPT generation)
- **Service Layer**: Media specialist agent
- **Key Functions**:
  - `generate_image(prompt, style, size)`: Image generation via Azure OpenAI
  - `generate_video(script, duration, style)`: Video generation (async task)
  - `generate_ppt(content, audience, style)`: PowerPoint generation
  - `execute(task_type, params)`: Route to appropriate media generation function
- **Dependencies**: `src.tools.media`, `src.tools.ppt`, Azure OpenAI API
- **Ownership**: Media + creative team

### 3.9 Tools Layer

#### src/tools/
- **Purpose**: Reusable tools for agents (search, storage, API calls, media generation)
- **Service Layer**: Tool implementations
- **Module Structure**:
  - `__init__.py`: Export public API
  - `search.py`: AI Search hybrid retrieval
  - `storage.py`: Blob Storage document and artifact management
  - `cosmos_store.py`: Cosmos DB conversation and media history
  - `postgres_store.py`: PostgreSQL telemetry and audit logs
  - `redis_cache.py`: Redis cache for hot data
  - `media.py`: Image/video generation via Azure OpenAI
  - `ppt.py`: PowerPoint generation pipeline
  - `base.py`: Base Tool class interface

#### src/tools/base.py
- **Purpose**: Abstract base class for all tools
- **Key Classes**:
  - `Tool`: Abstract base with `invoke(args, context)` method
  - `ToolResult`: Dataclass with output, execution_time_ms, cost_usd, error
- **Key Functions**:
  - `register_tool(tool_name, tool_class)`: Register tool for use by agents
  - `validate_tool_args(args, schema)`: Type-check tool arguments before invocation

#### src/tools/search.py
- **Purpose**: Hybrid search (semantic, vector, keyword) via Azure AI Search
- **Service Layer**: AI Search data service
- **Key Classes**:
  - `SearchClient`: Wrapper around Azure SDK
  - `SearchQuery`: Dataclass with text, filters, top_k, rerank_score_threshold
  - `SearchResult`: Document with score, rank, content, source_url, metadata
- **Key Functions**:
  - `search_hybrid(query, filters, top_k)`: Hybrid retrieval (BM25 + semantic)
  - `search_vector(query_embedding, top_k)`: Vector similarity search
  - `rerank_results(results, query)`: Semantic rerank to top K
  - `expand_query(query)`: Query expansion for recall (synonyms, related terms)
- **Indices Used**: `enterprise-knowledge` (67 documents), searchable by content, metadata_storage_path, created_date
- **Metrics**: Search latency, retrieval precision, rerank effectiveness
- **Dependencies**: `azure-search-documents`, `azure-identity`
- **Ownership**: RAG + data team

#### src/tools/storage.py
- **Purpose**: Blob Storage operations (upload, download, list, delete)
- **Service Layer**: Blob Storage data service
- **Key Classes**:
  - `StorageClient`: Wrapper around Azure SDK
  - `StorageObject`: File metadata (path, size, created_date, tags)
- **Key Functions**:
  - `upload_blob(container, name, data, metadata)`: Store blob
  - `download_blob(container, name)`: Retrieve blob
  - `list_blobs(container, prefix)`: List objects in container
  - `delete_blob(container, name)`: Delete object (soft-delete via versioning)
  - `set_blob_tier(container, name, tier)`: Archive/Hot/Cool tier management
- **Containers**:
  - `generated-media`: Images, videos, PPTs (90-day retention)
  - `source-documents`: Policy documents, technical specs (permanent)
  - `user-artifacts`: User-specific files (follow user GDPR policy)
  - `audit-archive`: Audit logs for legal hold (365-day retention)
- **Ownership**: Data and infrastructure team

#### src/tools/cosmos_store.py
- **Purpose**: Cosmos DB CRUD operations (conversations, media, evaluations)
- **Service Layer**: Cosmos DB data service (NoSQL)
- **Key Classes**:
  - `CosmosClient`: Wrapper around Azure SDK
  - `Conversation`: Document schema with user_id, turns, created_date, model_checkpoint
  - `MediaGeneration`: Document schema with user_id, prompt, output_path, status, cost
- **Key Functions**:
  - `create_conversation(user_id, initial_turn)`: Start new conversation
  - `append_turn(conversation_id, role, content)`: Add human/assistant message
  - `get_conversation(conversation_id)`: Retrieve full history
  - `delete_conversation(conversation_id)`: Soft delete (for GDPR)
  - `list_media_by_user(user_id)`: Retrieve user's generated media
- **Collections**:
  - `conversations`: One doc per conversation (up to 2 MB per doc)
  - `media_metadata`: One doc per generated image/video/PPT
  - `evaluation_signals`: Quality metrics and user feedback
- **Partitioning**: By user_id for good distribution
- **TTL**: Configurable per-document (media 90 days, conversations 180 days)
- **Dependencies**: `azure-cosmos`
- **Ownership**: Data and application team

#### src/tools/postgres_store.py
- **Purpose**: PostgreSQL CRUD operations (telemetry, audit, feedback)
- **Service Layer**: PostgreSQL relational data service
- **Key Classes**:
  - `PostgresClient`: Connection pool + SQLAlchemy ORM
  - `TelemetryLog`: ORM model for LLM metrics
  - `AuditTrail`: ORM model for governance decisions
  - `SearchLog`: ORM model for RAG queries
- **Key Functions**:
  - `log_telemetry(user_id, endpoint, model, tokens, latency, cost)`: Record metrics
  - `log_audit(user_id, decision_type, policy_check, outcome)`: Record decisions
  - `log_search(user_id, query, top_k, latency, precision)`: Record RAG queries
  - `query_telemetry(user_id, start_date, end_date)`: Retrieve metrics
  - `export_audit_trail(user_id)`: Export audit records for GDPR
- **Tables**:
  - `telemetry_logs`: (id, user_id, endpoint, model, input_tokens, output_tokens, latency_ms, cost_usd, timestamp)
  - `audit_trails`: (id, user_id, event_type, decision, reasoning, outcome, timestamp)
  - `search_logs`: (id, user_id, query, results_count, latency_ms, precision_score, timestamp)
  - `feedback_signals`: (id, user_id, friction_type, severity, context, timestamp)
  - `feature_requests`: (id, friction_signal_id, title, description, priority, status, timestamp)
- **Indexing**: Timestamp, user_id, event_type (for efficient retrieval and analysis)
- **Dependencies**: `sqlalchemy`, `psycopg2`
- **Ownership**: Data and infrastructure team

#### src/tools/redis_cache.py
- **Purpose**: Redis cache for hot data (session state, embeddings, counters)
- **Service Layer**: Redis cache
- **Key Classes**:
  - `RedisClient`: Connection pool + helper methods
- **Key Functions**:
  - `get_session(session_id)`: Retrieve conversation context
  - `set_session(session_id, data, ttl)`: Store session state
  - `get_embedding(doc_id)`: Retrieve cached vector embedding
  - `set_embedding(doc_id, vector, ttl)`: Cache embedding
  - `increment_counter(counter_name)`: Rate-limit and quota tracking
  - `delete_key(key)`: Remove from cache
- **Cache Keys**:
  - `session:<session_id>` → Conversation context (TTL 8 hours)
  - `embed:<doc_id>` → Document vector (TTL 24 hours)
  - `rate:<user_id>:<endpoint>` → Request counter (TTL 1 minute)
  - `quota:<user_id>` → User quota usage (TTL 1 day)
- **Dependencies**: `redis`
- **Ownership**: Infrastructure and caching team

#### src/tools/media.py
- **Purpose**: Image and video generation via Azure OpenAI APIs
- **Service Layer**: Media generation
- **Key Classes**:
  - `ImageGenerator`: Dalle-3 image generation
  - `VideoGenerator`: Video generation (async, polling-based)
- **Key Functions**:
  - `generate_image(prompt, size, quality, style)`: Create image
  - `generate_video(script, duration, style)`: Async video generation
  - `get_video_status(job_id)`: Poll video generation progress
  - `download_media(output_path)`: Retrieve generated artifact
- **Image Parameters**: size (1024x1024, 1024x1792), quality (standard, hd), style (natural, vivid)
- **Video Parameters**: duration (5-60 sec), style (cinematic, documentary, commercial)
- **Output**: Artifacts stored in Blob Storage (`generated-media` container)
- **Cost Tracking**: Record cost per generation for telemetry
- **Dependencies**: `openai` (Azure OpenAI SDK)
- **Ownership**: Media and creative team

#### src/tools/ppt.py
- **Purpose**: PowerPoint presentation generation
- **Service Layer**: PPT generation
- **Key Classes**:
  - `PPTGenerator`: Build and export PPTX files
- **Key Functions**:
  - `create_presentation(title, slides, audience, style)`: Generate PPTX
  - `add_slide(slide_type, content)`: Add title, content, image, chart slide
  - `export_pptx(output_path)`: Write to file
- **Slide Types**: Title, Content, Image, Comparison, Agenda, Closing
- **Styles**: Corporate (blue), Creative (colorful), Minimalist (grayscale)
- **Output**: Saved to Blob Storage, link returned to user
- **Dependencies**: `python-pptx`
- **Ownership**: Media and creative team

### 3.10 Skills System

#### src/skills/
- **Purpose**: Reusable capability modules loaded at runtime from SKILL.md files
- **Service Layer**: Skills configuration
- **Module Structure**:
  - `__init__.py`: Export public API
  - `skill_loader.py`: Parse SKILL.md frontmatter and body
  - `skill_registry.py`: Register and query loaded skills
  - `skill_validator.py`: Validate SKILL.md syntax and required fields

#### src/skills/skill_loader.py
- **Purpose**: Load and parse SKILL.md files from skills/ directory
- **Key Functions**:
  - `load_skill(skill_name)`: Read SKILL.md, parse frontmatter, return Skill object
  - `load_all_skills()`: Load all skills from skills/*/SKILL.md
  - `parse_frontmatter(markdown_text)`: Extract YAML header (name, description, allowed-tools)
- **Frontmatter Schema** (required in each SKILL.md):
  ```yaml
  ---
  name: knowledge-retrieval
  description: RAG with hybrid search and citations
  allowed-tools:
    - search
    - storage
    - llm
  ---
  ```
- **Ownership**: Platform architect

#### src/skills/skill_registry.py
- **Purpose**: Runtime registry of loaded skills
- **Key Classes**:
  - `SkillRegistry`: Singleton that stores all loaded skills
  - `Skill`: Dataclass with name, description, instructions, examples, allowed_tools
- **Key Functions**:
  - `register_skill(skill)`: Add skill to registry
  - `get_skill(skill_name)`: Retrieve skill definition
  - `list_skills()`: Return all available skills
  - `check_tool_allowed_for_skill(tool_name, skill_name)`: RBAC check for tool usage
- **Ownership**: Platform architect

### 3.11 Routers and Endpoints

#### src/routers/
- **Purpose**: FastAPI route handlers grouped by feature area
- **Module Structure**:
  - `chat.py`: `/chat` endpoint (question-answering, conversation)
  - `search.py`: `/search` endpoint (RAG retrieval)
  - `media.py`: `/media/*` endpoints (image, video, PPT generation)
  - `governance.py`: `/governance/*` endpoints (data access, deletion, audit)
  - `architecture.py`: `/architecture/status` endpoint (health, readiness)
  - `metrics.py`: `/metrics` endpoint (cost, performance, SLO status)
  - `feedback.py`: `/feedback/*` endpoints (friction signals, feature requests)

#### src/routers/chat.py
  - `GET /chat/{conversation_id}`: Retrieve conversation history
  - `DELETE /chat/{conversation_id}`: Delete conversation (soft delete, audit logged)
- **Request Schema**: { "prompt", "conversation_id", "context_filters" }
- **Response Schema**: { "response", "citations", "reasoning_trace", "metrics" }
- **Orchestration**: Route to flat or hierarchical orchestrator based on complexity
- **Ownership**: Application team
- **Purpose**: RAG search endpoint
- **Endpoints**:
  - `POST /search`: Execute hybrid search
  - `POST /search/reindex`: Trigger reindex (admin only)
- **Request Schema**: { "query", "top_k", "filters", "rerank_threshold" }
- **Response Schema**: { "results", "citations", "rerank_scores", "latency_ms" }
- **Ownership**: RAG + data team

#### src/routers/media.py
- **Purpose**: Media generation endpoints
- **Endpoints**:
  - `POST /media/image`: Generate image
  - `POST /media/video`: Start video generation (async)
  - `POST /media/ppt`: Generate presentation
- **Request Schemas**: { "prompt", "size", "quality" } for image; { "script", "duration", "style" } for video; { "content", "audience", "style" } for PPT

#### src/routers/governance.py
- **Endpoints**:
  - `POST /governance/data-access-request`: Initiate GDPR data access
  - `POST /governance/deletion-request`: Initiate GDPR data deletion
  - `GET /governance/audit-trail`: Export audit logs

#### Skills Runtime Workflow (Startup → Execution)

**Initialization** (src/main.py § lifespan, lines 370-378):
```python
# Load Python-coded skills
skill_registry = SkillRegistry()
skill_registry.register(SearchSkill())      # Python class
skill_registry.register(AnalysisSkill())    # Python class
skill_registry.register(ComplianceSkill())  # Python class

# Load Markdown declarative skills from skills/ directory
project_root = Path(__file__).resolve().parent.parent
md_count = load_markdown_skills(project_root / "skills", skill_registry)
logger.info("platform.markdown_skills_loaded", count=md_count, total=skill_registry.count)
```

**File Structure** for Markdown skills:
```
skills/
├── knowledge-retrieval/
│   └── SKILL.md          ← Frontmatter (name, description, allowed-tools) + Markdown body (instructions)
├── analysis/
│   └── SKILL.md
├── compliance-check/
│   └── SKILL.md
└── ...
```

**Agent Binding** (src/main.py § lifespan, lines 380-400):
```python
# Create specialist agents
knowledge_agent = KnowledgeAgent(search_tool=search_tool)
analyst_agent = AnalystAgent(search_tool=search_tool)
governance_agent = GovernanceAgent(search_tool=search_tool)

# Register agents to orchestrators
orchestrator.register_agent(knowledge_agent)
orchestrator.register_agent(analyst_agent)
orchestrator.register_agent(governance_agent)

hierarchical_orchestrator.register_agent(knowledge_agent)
hierarchical_orchestrator.register_agent(analyst_agent)
hierarchical_orchestrator.register_agent(governance_agent)
```

**Runtime Execution** (src/main.py § /chat endpoint, lines 790-860):
1. User posts message to `/chat`
2. Governance pipeline: input safety + PII masking
3. Orchestrator selects flat or hierarchical router
4. Selected agent receives context + skill definitions from registry
5. Agent executes skill instructions + tool calls
6. Results returned with citations and reasoning trace
7. Governance pipeline: output safety check
8. Metrics, audit, and evaluation recorded

**Example Request Flow**:
```
User: "Check if our data processing complies with GDPR"
  ↓
/chat endpoint (input safety + PII masking)
  ↓
Orchestrator detects complexity ("compliance" + "check") → use hierarchical router
  ↓
HierarchicalOrchestrator.plan():
  - Step 1: Knowledge Agent loads `knowledge-retrieval` skill → fetch GDPR docs
  - Step 2: Governance Agent loads `compliance-check` skill → assess risk
  - Step 3: Analyst Agent loads `analysis` skill → synthesize report
  ↓
Each agent executes its skill + tools:
  - Knowledge Agent: search_hybrid("GDPR data processing", top_k=10) → returns chunks + sources
  - Governance Agent: assess_risk(retrieved_docs, current_processes) → risk score + recommendations
  - Analyst Agent: synthesize(all_outputs) → structured report
  ↓
HierarchicalOrchestrator.synthesize(): Merge outputs
  ↓
Response with citations + reasoning trace + governance status
  ↓
Output safety check + metrics recording + audit logging
```

  ## 4. Startup and Lifecycle (lifespan context manager)

  ### 4.1 FastAPI Lifespan Bootstrap

  The `lifespan()` async context manager in [src/main.py](src/main.py#L250) orchestrates initialization in this order:

  **Phase 1: Governance & Security** (lines 300-310):
  - Initialize `GuardrailPipeline` (input + output safety)
  - Initialize `ContentSafety` (Azure Content Safety API)
  - Initialize `PIIFilter` (Presidio-based PII detection)
  - Initialize `AuditLogger` (compliance trail persistence)

  **Phase 2: Data Stores** (lines 312-335):
  - Connect to `CosmosStore` (conversations + media metadata)
  - Connect to `RedisCache` (session state + hot data)
  - Connect to `PostgresStore` (telemetry + audit events)
  - Initialize `AISearchTool` (Azure AI Search hybrid retrieval)
  - Initialize `BlobStorageTool` (document + artifact storage)

  **Phase 3: Skills and Registry** (lines 370-378):
  - Create `SkillRegistry` singleton
  - Register Python-coded skills (SearchSkill, AnalysisSkill, ComplianceSkill)
  - Load Markdown declarative skills from `skills/*/SKILL.md`
  - Log total skill count

  **Phase 4: Agents** (lines 380-400):
  - Create specialist agents (Knowledge, Analyst, Governance, Architect, Media)
  - Register agents to flat `Orchestrator`
  - Register agents to `HierarchicalOrchestrator`

  **Phase 5: Metrics and Evaluation** (lines 405-415):
  - Initialize `EvaluationPipeline` (quality sampling + evaluation model)
  - Initialize `MetricsCollector` (LLM-native metrics: TTFT, tokens/sec, cost)
  - Initialize `FeedbackCollector` (friction → feature request conversion)

  **Phase 6: Watchdog** (lines 420-430):
  - Start `idle_watchdog_task` if auto-stop is enabled
  - Monitors activity and can trigger soft-stop or hard-stop

  **Shutdown** (lines 432-440):
  - Cancel idle watchdog task
  - Flush remaining audit logs
  - Close database connections
  - Release resources

  **Code Reference**:
  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
    # Startup
    global orchestrator, skill_registry, cosmos_store, postgres_store, ...
    
    # Phase 1: Governance
    content_safety = ContentSafety(...)
    pii_filter = PIIFilter()
    audit_logger = AuditLogger()
    
    # Phase 2: Data stores
    cosmos_store = CosmosStore()
    cosmos_store.initialize()
    
    redis_cache = RedisCache()
    redis_cache.ping()
    
    postgres_store = PostgresStore()
    postgres_store.initialize()
    
    search_tool = AISearchTool()  # Azure AI Search
    storage_tool = BlobStorageTool()  # Blob Storage
    
    # Phase 3: Skills
    skill_registry = SkillRegistry()
    skill_registry.register(SearchSkill())
    skill_registry.register(AnalysisSkill())
    skill_registry.register(ComplianceSkill())
    
    md_count = load_markdown_skills(project_root / "skills", skill_registry)
    
    # Phase 4: Agents
    knowledge_agent = KnowledgeAgent(search_tool=search_tool)
    analyst_agent = AnalystAgent(search_tool=search_tool)
    governance_agent = GovernanceAgent(search_tool=search_tool)
    
    orchestrator = OrchestratorAgent()
    orchestrator.register_agent(knowledge_agent)
    orchestrator.register_agent(analyst_agent)
    orchestrator.register_agent(governance_agent)
    
    hierarchical_orchestrator = HierarchicalOrchestrator()
    hierarchical_orchestrator.register_agent(knowledge_agent)
    hierarchical_orchestrator.register_agent(analyst_agent)
    hierarchical_orchestrator.register_agent(governance_agent)
    
    # Phase 5: Metrics
    eval_pipeline = EvaluationPipeline()
    metrics_collector = MetricsCollector()
    feedback_collector = FeedbackCollector()
    
    # Phase 6: Watchdog
    if settings.auto_stop_enabled:
      idle_watchdog_task = asyncio.create_task(_idle_watchdog_loop())
    
    logger.info("platform.ready", agents=4, governance="enabled", evaluation="enabled")
    
    yield  # Application runs
    
    # Shutdown
    if idle_watchdog_task:
      idle_watchdog_task.cancel()
    
    logger.info("platform.shutdown")
  ```

  ### 4.2 Dependency Initialization Order

  **Critical Dependencies**:
  - Auth system must load before governance (DefaultAzureCredential)
  - Data stores must initialize before agents (agents need access to storage tools)
  - Skills must load before agents (agents query skill registry at runtime)
  - Agents must register before orchestrators (orchestrator routes to registered agents)

  **If any step fails**:
  - Startup is logged with ERROR
  - Specific component marked as unavailable
  - Platform continues (degraded mode) or raises 503 Service Unavailable

  **Health Check** (GET /health):
  - Reports status of each component
  - Returns 200 OK only if all required components are initialized
  - Returns 503 Service Unavailable if critical component missing
  - `GET /governance/status`: Overall governance status
- **Request Schema**: { "user_id", "reason" } for GDPR requests; { "feature", "policies" } for policy check
- **Response Schema**: { "request_id", "status", "data"/"recommendation" }
- **Ownership**: Compliance and security team

#### src/routers/architecture.py
- **Purpose**: Architecture and operational status endpoints
- **Endpoints**:
  - `GET /architecture/status`: Health, readiness, dependencies, versions
  - `GET /architecture/deployment-config`: Current config (non-sensitive)
  - `POST /architecture/readiness-check`: Full runtime validation
- **Response Schema**: { "status", "components", "readiness", "checks" }
- **Ownership**: Platform architect and SRE

#### src/routers/metrics.py
- **Purpose**: Metrics and observability endpoints
- **Endpoints**:
  - `GET /metrics`: Prometheus-format metrics
  - `GET /metrics/cost-report`: Cost by user, agent, model
  - `GET /metrics/slo-status`: SLO compliance dashboard
  - `GET /metrics/quality-signals`: User satisfaction and correctness scores
- **Response Schema**: { "timestamp", "metric_name", "value", "dimensions" }
- **Ownership**: SRE and product team

#### src/routers/feedback.py
- **Purpose**: Feedback and product signals endpoints
- **Endpoints**:
  - `POST /feedback/friction`: Report UX friction
  - `GET /feedback/feature-requests`: List feature requests by priority
  - `POST /feedback/csat`: Submit user satisfaction score
  - `GET /feedback/trends`: Friction and feature request trends
- **Request Schema**: { "friction_type", "severity", "context" } for friction; { "csat_score", "feedback_text" } for CSAT
- **Response Schema**: { "signal_id", "recorded", "aggregated_signal_count" }
- **Ownership**: Product and UX team

### 3.12 Web Interface

#### src/web/
- **Purpose**: HTML, CSS, JavaScript for customer-facing UI
- **Module Structure**:
  - `customer_home.html`: Main dashboard (chat, RAG search, media, governance, metrics)
  - `styles.css`: Styling
  - `scripts.js`: Client-side logic (API calls, form handling, result rendering)
  - `admin_dashboard.html`: Admin-only operations (index management, user deletion)

#### src/web/customer_home.html
- **Purpose**: Customer-facing UI for all major features
- **Sections**:
  1. **Chat and Conversation**: Input for `/chat`, display response with reasoning trace
  2. **Internal Knowledge Search**: Input for `/search`, display results with citations and rerank scores
  3. **Media Generation**: Forms for `/media/image`, `/media/video`, `/media/ppt` with status polling
  4. **Governance Status**: Display governance checks, policy violations, audit trail access
  5. **Metrics Dashboard**: Cost, SLO status, quality signals
  6. **Feedback Panel**: Friction reporting, feature request viewing
- **Dependencies**: No framework (vanilla JS); calls `/api/*` endpoints
- **Ownership**: Frontend and UX team

---

## 4. Test Files

### tests/
- **Purpose**: Unit, integration, and regression tests
- **Test Structure**:
  - `test_api_smoke.py`: Basic endpoint health checks
  - `test_api_runtime_readiness.py`: Full runtime readiness (dependencies, credentials, config)
  - `test_chat_regression.py`: Chat endpoint correctness regression
  - `test_governance_basics.py`: Governance guardrail functionality
  - `test_cli_helpers.py`: CLI utility tests
- **Test Data**: `sample_data/` directory with mock policies, documents, case studies

### tests/test_api_smoke.py
- **Purpose**: Quick smoke tests for all endpoints
- **Tests**:
  - `test_health_endpoint()`: GET /health returns 200
  - `test_chat_endpoint()`: POST /chat with valid input returns response
  - `test_search_endpoint()`: POST /search retrieves documents
  - `test_media_endpoints()`: POST /media/* return job IDs
  - `test_governance_endpoint()`: GET /governance/status returns status
- **Run**: `pytest tests/test_api_smoke.py`

### tests/test_api_runtime_readiness.py
- **Purpose**: Validate all external dependencies are available before deployment
- **Tests**:
  - `test_azure_credentials()`: Can authenticate with Azure (DefaultAzureCredential)
  - `test_google_credentials()`: Can authenticate with Google Cloud (ADC)
  - `test_postgres_connection()`: PostgreSQL database is reachable
  - `test_redis_connection()`: Redis cache is reachable
  - `test_cosmos_connection()`: Cosmos DB is reachable
  - `test_blob_storage_access()`: Blob Storage is readable/writable
  - `test_search_index()`: AI Search index is healthy
  - `test_openai_api()`: Azure OpenAI API is available
  - `test_config_complete()`: All required env vars are set
- **Run**: `pytest tests/test_api_runtime_readiness.py`

### tests/test_chat_regression.py
- **Purpose**: Regression tests for chat endpoint
- **Tests**:
  - `test_simple_question()`: Single-turn chat works
  - `test_multi_turn_conversation()`: Multi-turn conversation preserves context
  - `test_reasoning_trace_recorded()`: ReAct trace is included in response
  - `test_citations_included()`: RAG citations are formatted correctly
- **Run**: `pytest tests/test_chat_regression.py`

### tests/test_governance_basics.py
- **Purpose**: Test governance guardrails
- **Tests**:
  - `test_pii_masking()`: PII is masked before LLM
  - `test_content_safety_check()`: Harmful content is blocked
  - `test_audit_logging()`: All decisions are logged
  - `test_gdpr_deletion_request()`: User deletion works end-to-end
  - `test_data_access_export()`: GDPR data access export includes all user data
- **Run**: `pytest tests/test_governance_basics.py`

### tests/test_cli_helpers.py
- **Purpose**: CLI command tests
- **Tests**:
  - `test_skill_validate()`: Skill YAML is valid
  - `test_index_reset()`: Search index rebuild completes
  - `test_audit_export()`: Audit trail export is valid JSON
- **Run**: `pytest tests/test_cli_helpers.py -v`

---

## 5. Sample Data and Fixtures

### sample_data/
- **Purpose**: Test data and example inputs
- **Structure**:
  - `policies/`: Mock compliance policies (GDPR, HIPAA, SOC2)
  - `documents/`: Sample policy documents for RAG ingestion
  - `case-studies/`: Example customer scenarios
  - `technical/`: Technical specifications and architecture docs

---

## 6. Documentation

### docs/
- **Purpose**: User and developer documentation
- **Files**:
  - `ARCHITECTURE.md`: System architecture and service map
  - `ARCHITECTURE-DEEP-DIVE.md`: Request lifecycle, orchestration internals
  - `PRODUCTION-ARCHITECTURE.md`: Production topology, deployment checklist
  - `DEMO_RUNBOOK_ZH.md`: Demo script and talking points (Chinese)
  - `PROJECT_OVERVIEW_ZH.md`: Project overview and learning path (Chinese)
  - `DISCOVERY_TEMPLATE.md`: Customer discovery framework
  - `CLEANUP.md`: Maintenance and cleanup procedures
  - `FILE-REFERENCE.md`: This document — file-by-file module guide
  - `README.md`: Quick start and links to other docs

---

## 7. Configuration and Deployment

### Configuration Files
- **`.env`** (local development, NOT checked in): `AZURE_*, GOOGLE_*, REDIS_*, DATABASE_*` variables
- **`.env.example`** (template for developers): Shows expected env var format
- **`pyproject.toml`**: Project metadata, dependencies, tool configs (pytest, mypy, black)

### Deployment Files
- **`Dockerfile`**: Containerize FastAPI + dependencies
- **`docker-compose.yml`**: Local dev stack (API + PostgreSQL + Redis + Blob emulator)
- **`deploy.zip`**: Package for Azure Web App deployment (created by CI/CD)
- **`.github/workflows/`**: GitHub Actions CI/CD pipelines
  - `test.yml`: Run unit tests on PR
  - `build-deploy.yml`: Build and deploy to Azure Web App on merge to main

---

## 8. Dependency Graph and Ownership

### Layer: API
- `main.py` (owns FastAPI app bootstrap)
- `routers/*.py` (each router is owned by feature team)
- **Dependencies**: FastAPI, Pydantic, uvicorn, src.agents, src.tools, src.governance
- **Ownership**: Application team

### Layer: Orchestration
- `agents/orchestrator.py` (flat routing)
- `agents/hierarchy.py` (hierarchical planning + delegation)
- `agents/react.py` (reasoning engine)
- **Dependencies**: LLM model, src.agents (specialist agents)
- **Ownership**: Platform architect

### Layer: Agents
- `agents/knowledge.py`, `analysts.py`, `governance_agent.py`, `architect.py`, `media_agent.py`
- **Dependencies**: src.tools, LLM model
- **Ownership**: Individual agent teams (RAG, analytics, governance, media)

### Layer: Tools
- `tools/search.py`, `storage.py`, `cosmos_store.py`, `postgres_store.py`, `redis_cache.py`, `media.py`, `ppt.py`
- **Dependencies**: Azure SDK, Google Cloud SDK, LLM APIs
- **Ownership**: Data, infrastructure, and media teams

### Layer: Governance
- `governance/pii_filter.py`, `content_safety.py`, `audit_logger.py`, `gdpr_controller.py`, `risk_assessor.py`
- **Dependencies**: src.tools.postgres_store, Presidio, Azure Content Safety
- **Ownership**: Security and compliance team

### Layer: Observability
- `observability/logger.py`, `tracing.py`
- **Dependencies**: OpenTelemetry, Azure App Insights, Google Cloud Trace
- **Ownership**: SRE team

### Layer: Metrics
- `metrics/llm_metrics.py`, `quality_metrics.py`, `slo_enforcement.py`, `cost_tracker.py`
- **Dependencies**: src.tools.postgres_store
- **Ownership**: Platform architect, SRE, product team

### Layer: Feedback
- `feedback/friction_detector.py`, `feature_request_generator.py`
- **Dependencies**: src.tools.postgres_store
- **Ownership**: Product and UX team

### Layer: Skills
- `skills/skill_loader.py`, `skill_registry.py`, `skill_validator.py`
- **Dependencies**: Markdown parser
- **Ownership**: Platform architect

### Layer: Web
- `web/customer_home.html`, `admin_dashboard.html`
- **Dependencies**: HTML5, CSS3, vanilla JavaScript, fetch API
- **Ownership**: Frontend and UX team

---

## 9. Common Questions and Answers

**Q: Which file handles the RAG search?**
A: `agents/knowledge.py` orchestrates RAG (calls `tools/search.py` for retrieval, then LLM for answer generation).

**Q: Where is the audit log stored?**
A: PostgreSQL `audit_trails` table (written by `governance/audit_logger.py` and `tools/postgres_store.py`).

**Q: How do we enforce GDPR deletions?**
A: `governance/gdpr_controller.py` triggers deletion across PostgreSQL, Cosmos, Blob Storage, and Redis. See `routers/governance.py` for API entry point.

**Q: Where are media artifacts stored?**
A: Blob Storage, `generated-media` container. Metadata in Cosmos DB, URLs in PostgreSQL telemetry.

**Q: How do we track cost per request?**
A: `metrics/llm_metrics.py` records tokens and model; `tools/postgres_store.py` persists to telemetry_logs; `routers/metrics.py` exposes cost aggregations.

**Q: Which team owns the hierarchical orchestrator?**
A: Platform architect (Platform team). Delegates to specialist agents (owned by respective teams).

**Q: How do we load skills at runtime?**
A: `skills/skill_loader.py` reads from `skills/*/SKILL.md` on startup; `skill_registry.py` manages in-memory registry.

**Q: What triggers feature request generation?**
A: `feedback/friction_detector.py` identifies UX friction (timeouts, errors) from telemetry; `feedback/feature_request_generator.py` converts signals to requests.

---

## 10. Quick Module Lookup

| Need | Module | Function |
|---|---|---|
| Chat endpoint | `routers/chat.py` | `POST /chat` |
| RAG search | `tools/search.py` | `search_hybrid()` |
| User authentication | `auth/azure_auth.py`, `auth/google_auth.py` | `validate_*_token()` |
| Audit logging | `governance/audit_logger.py` | `log_request()`, `log_decision()` |
| Cost tracking | `metrics/llm_metrics.py` | `record_llm_call()`, `calculate_cost()` |
| Media generation | `agents/media_agent.py` | `generate_image()`, `generate_video()`, `generate_ppt()` |
| Skill loading | `skills/skill_loader.py` | `load_all_skills()` |
| GDPR deletion | `governance/gdpr_controller.py` | `process_deletion_request()` |
| Reasoning trace | `agents/react.py` | `run()`, `format_reasoning_trace()` |
| Health check | `routers/architecture.py` | `GET /architecture/status` |
| SLO enforcement | `metrics/slo_enforcement.py` | `check_latency_slo()`, `check_throughput_slo()` |

---

**Document Owner**: Platform Architect  
**Last Updated**: May 2026  
**Audience**: Developers, DevOps, security auditors, interviewers
