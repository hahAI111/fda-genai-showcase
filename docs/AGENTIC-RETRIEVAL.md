# Agentic Retrieval — 使用指南

## 概述

本项目现已实现 **Agentic Retrieval** 系统，支持：

1. **多源知识检索** — 支持 6 种数据源类型（Azure Search、Azure Blob、OneLake、SharePoint、Web、Bing）
2. **LLM 驱动的查询规划** — 自动分解复杂查询为多个子查询
3. **并行执行** — 在多个知识源并发执行子查询（而非串行）
4. **结构化结果** — 返回基础数据、来源引用、执行计划、子查询结果
5. **端到端治理** — 内容安全、PII 过滤、审计日志

## 架构

```
用户查询 (User Query)
    ↓
[Content Safety] → 输入筛查
    ↓
[PII Filter] → 掩码敏感数据
    ↓
[Knowledge Base] → LLM 查询规划 + 并行搜索 + 聚合
    │
    ├─→ [子查询1] → [知识源A、B] (并行)
    ├─→ [子查询2] → [知识源A、B] (并行)
    └─→ [子查询3] → [知识源A、B] (并行)
    ↓
[Content Safety] → 输出筛查
    ↓
[Audit Logger] → 合规性记录
    ↓
结构化响应 (Structured Response)
```

## 核心组件

### 1. Knowledge Source（知识源）

定义在 `src/tools/knowledge_source.py`

**支持的源类型：**

| 类型 | 说明 | 配置 |
|------|------|------|
| `searchIndex` | Azure AI Search 索引 | endpoint, index_name, api_key |
| `azureBlob` | Azure Blob Storage | account_url, container_name, account_key |
| `indexedOneLake` | Fabric Lakehouse（索引） | workspace_id, lakehouse_id, table_name |
| `indexedSharePoint` | SharePoint Online（索引） | site_url, list_id |
| `remoteSharePoint` | SharePoint Online（即时查询） | site_url, list_id |
| `web` | Bing 网络搜索 | （无需配置） |

**示例：**

```python
from src.tools.knowledge_source import KnowledgeSource, KnowledgeSourceType

# 创建 Azure AI Search 源
search_source = KnowledgeSource.from_search_index(
    name="enterprise-knowledge",
    endpoint="https://search111222.search.windows.net",
    index_name="enterprise-knowledge",
    api_key="your-api-key",
)

# 创建 Web 源
web_source = KnowledgeSource.web_source()
```

### 2. Knowledge Base（知识库）

定义在 `src/tools/knowledge_base.py`

**职责：**
- 管理多个知识源的生命周期
- 协调 LLM 查询规划
- 并行执行多源搜索
- 聚合和去重结果

**主要方法：**

```python
from src.tools.knowledge_base import KnowledgeBase

kb = KnowledgeBase()

# 注册知识源
kb.register_source(search_source)
kb.register_source(web_source)

# 执行 Agentic Retrieval
result = await kb.retrieve_and_plan(
    query="如何实现多代理编排？",
    conversation_id="conv-123",
    reasoning_effort="medium",  # "low", "medium", "high"
)

# 获取结果
print(result.grounding_data)      # 基础文件内容
print(result.source_citations)    # 来源引用
print(result.execution_plan)      # 执行计划（子查询、源）
print(result.sub_query_results)   # 每个子查询的执行结果
```

## API 使用

### /retrieve 端点

新增 `POST /retrieve` 端点，用于 Agentic Retrieval 查询。

**请求格式：**

```json
{
    "query": "如何实现 RAG 系统？",
    "conversation_id": "conv-123",  // 可选
    "user_id": "user-123",          // 可选
    "tenant_id": "tenant-123",      // 可选
    "reasoning_effort": "medium"    // "low", "medium", "high"
}
```

**响应格式：**

```json
{
    "query": "如何实现 RAG 系统？",
    "grounding_data": [
        {
            "title": "RAG 架构设计",
            "content": "Retrieval-Augmented Generation 通过...",
            "source": "https://...",
            "score": 0.95,
            "reranker_score": 0.92
        }
    ],
    "source_citations": [
        {
            "index": 1,
            "title": "RAG 架构设计",
            "source_url": "https://...",
            "sources": ["enterprise-knowledge-index"]
        }
    ],
    "execution_plan": {
        "user_query": "如何实现 RAG 系统？",
        "sub_queries": [
            "RAG 基本概念和原理",
            "RAG 实现步骤和最佳实践",
            "RAG 性能优化技巧"
        ],
        "sources": ["enterprise-knowledge-index", "bing-search"],
        "planned_at": "2025-01-15T10:30:00.000Z"
    },
    "sub_query_results": [
        {
            "sub_query": "RAG 基本概念和原理",
            "source_name": "enterprise-knowledge-index",
            "results_count": 3,
            "execution_time_ms": 125.5,
            "top_results": [...]
        }
    ],
    "synthesis": null,  // 可选，LLM 生成的综合回答
    "conversation_id": "conv-123",
    "governance": {
        "input_safety": {
            "level": "safe",
            "flags": []
        },
        "pii": {
            "detected": false,
            "types": [],
            "count": 0
        },
        "output_safety": {
            "level": "mixed",
            "items_screened": 3
        }
    },
    "performance": {
        "total_latency_ms": 250.3,
        "items_retrieved": 3,
        "sub_queries": 3
    },
    "latency_ms": 250.3
}
```

## 使用示例

### Python 客户端

```python
import httpx
import asyncio

async def retrieve_with_agentic_rag():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/retrieve",
            json={
                "query": "企业 GenAI 平台的多代理架构是什么？",
                "conversation_id": "demo-001",
                "reasoning_effort": "medium",
            }
        )
        result = response.json()
        
        # 处理结果
        print("基础数据：")
        for item in result["grounding_data"]:
            print(f"  - {item['title']}")
        
        print("\n执行计划：")
        print(f"  子查询: {result['execution_plan']['sub_queries']}")
        print(f"  来源: {result['execution_plan']['sources']}")
        
        print(f"\n总延迟: {result['latency_ms']:.2f} ms")

asyncio.run(retrieve_with_agentic_rag())
```

### cURL 示例

```bash
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "如何在 FastAPI 中集成 Azure AI？",
    "reasoning_effort": "high"
  }'
```

## 与现有 /chat 端点的区别

| 特性 | /chat（Agent）| /retrieve（Agentic RAG）|
|------|---------------|------------------------|
| 目的 | 多代理编排 | 结构化知识检索 |
| 输出 | 自然语言回答 | 基础数据 + 引用 |
| 查询规划 | 代理决定 | LLM 分解为子查询 |
| 并行执行 | 限制（代理顺序） | 完全并行 |
| 结果聚合 | 代理负责 | 系统自动去重 |
| 治理 | 完整（安全、审计） | 完整（安全、审计） |

## 扩展指南

### 添加新的知识源

1. 在 `KnowledgeSourceType` 中定义新类型

```python
class KnowledgeSourceType(str, Enum):
    # ... 现有类型
    MY_CUSTOM_SOURCE = "myCustomSource"
```

2. 在 `KnowledgeBase._search_index()` 中添加搜索逻辑

```python
async def _search_index(...):
    # ... 现有代码
    elif source.source_type.value == "myCustomSource":
        source_results = await self._search_custom_source(sub_query, source)
```

3. 在 main.py 中初始化时注册

```python
custom_source = KnowledgeSource(
    name="my-source",
    source_type=KnowledgeSourceType.MY_CUSTOM_SOURCE,
    # ... 配置
)
knowledge_base.register_source(custom_source)
```

### 增强查询规划

修改 `KnowledgeBase._plan_queries()` 以使用更智能的 LLM 查询分解：

```python
async def _plan_queries(self, user_query: str) -> list[str]:
    # 调用 Azure OpenAI 的 gpt-4.1-mini
    planning_prompt = f"""
    用户查询: {user_query}
    
    请分解为 2-4 个具体的子查询...
    """
    # 使用 Azure OpenAI API 调用
    response = await self._call_azure_openai(planning_prompt)
    return response["sub_queries"]
```

## 监控和调试

### 审计日志

所有 /retrieve 请求都会记录在审计日志中，包括：
- 输入和输出安全筛查结果
- PII 检测结果
- 执行计划和子查询
- 延迟和性能指标

### 性能指标

response 中的 `performance` 字段包含：
- `total_latency_ms` — 总耗时
- `items_retrieved` — 检索的文件数
- `sub_queries` — 分解的子查询数

### 本地调试

```python
# 在 src/tools/knowledge_base.py 中启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 或使用 structlog 的上下文
with logger.context(debug=True):
    result = await kb.retrieve_and_plan(query)
```

## 限制和注意事项

1. **查询规划** — 目前使用启发式规则，不调用 LLM（可在扩展中改进）
2. **源认证** — 依赖配置中的 API 密钥或身份凭证
3. **结果大小** — 每个源最多返回 3 个结果，可调整 `top_k` 参数
4. **超时** — 并行搜索的总超时为 30 秒，可在配置中调整

## 相关文档

- [Architecture.md](ARCHITECTURE.md) — 完整的系统架构
- [README.md](../../README.md) — 项目概述
- [src/tools/knowledge_base.py](../../src/tools/knowledge_base.py) — 实现细节
- [src/tools/knowledge_source.py](../../src/tools/knowledge_source.py) — 源定义
