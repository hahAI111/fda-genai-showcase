# Prompt Engineering Best Practices for Enterprise AI

## Overview
This guide covers prompt engineering patterns specifically for enterprise
AI deployments where reliability, consistency, and auditability matter
more than creativity.

## System Prompt Design

### Structure
Every enterprise system prompt should include:
1. **Role definition**: Who the AI is and what it does
2. **Constraints**: What it must NOT do
3. **Output format**: Expected structure of responses
4. **Grounding rules**: How to handle uncertainty
5. **Tool instructions**: When and how to use tools

### Example: Knowledge Agent
```
You are an enterprise knowledge assistant. You answer questions ONLY based on
the retrieved documents provided to you via the search_knowledge tool.

Rules:
1. ALWAYS use the search_knowledge tool before answering
2. Only use information from the retrieved documents
3. Cite sources using [Source: <title>] format after each claim
4. If the retrieved documents don't contain the answer, say so clearly
5. Never fabricate information — grounding is non-negotiable
```

## Anti-Patterns

### 1. Vague Instructions
❌ "Be helpful and answer questions"
✅ "Answer questions ONLY using information from the retrieved documents. Cite every claim."

### 2. Missing Constraints
❌ "Analyze the data and provide insights"
✅ "Analyze the data. Present findings in this format: Summary → Findings → Recommendations → Risks"

### 3. No Grounding Rules
❌ "Tell the user about our policy"
✅ "Search the knowledge base first. If no relevant documents are found, say 'I don't have information about this topic in the knowledge base.'"

## Temperature Settings

| Use Case | Temperature | Why |
|----------|------------|-----|
| Factual Q&A (RAG) | 0.0 - 0.1 | Reproducibility, accuracy |
| Analysis/Summary | 0.2 - 0.4 | Some creativity in synthesis |
| Creative Writing | 0.7 - 0.9 | Diversity in output |
| Code Generation | 0.0 - 0.2 | Correctness over variety |
| Intent Classification | 0.0 | Deterministic routing |

## Token Management

### Context Window Budget
For a 128K context window model:
| Component | Token Budget | Notes |
|-----------|-------------|-------|
| System prompt | 500-1500 | Keep concise |
| Retrieved context | 4000-8000 | 5 chunks × 1000 tokens |
| Conversation history | 2000-4000 | Last 3-5 turns |
| Tool schemas | 500-1000 | Per registered tool |
| Response buffer | 2000-4000 | Max generation length |
| **Total** | **~15000** | Well within limits |

### Optimization Strategies
1. **Chunk filtering**: Only include chunks with relevance score > 0.7
2. **History compression**: Summarize older turns instead of full text
3. **Dynamic tool selection**: Only include tools relevant to the detected intent
4. **Streaming**: Use SSE for long responses to reduce perceived latency

## Evaluation-Driven Prompt Engineering
1. Start with a baseline prompt
2. Run evaluation suite (relevance, groundedness, coherence, safety)
3. Identify the weakest metric
4. Refine the prompt targeting that metric
5. Re-evaluate — ensure other metrics didn't degrade
6. Document the change and reasoning (ADR format)
7. Repeat until all metrics pass thresholds

## Common Prompt Injection Defenses
1. **Input sanitization**: Strip known injection patterns before LLM
2. **System prompt isolation**: Use delimiters between system and user content
3. **Output validation**: Check response against expected format
4. **Rate limiting**: Throttle requests from suspicious patterns
5. **Canary tokens**: Include markers in system prompt; alert if they appear in output
