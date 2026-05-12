# 企业级 GenAI 平台演示手册（技术版）

## 1. 演示目标

本手册用于 15-20 分钟技术演示，目标是同时证明：
1. 架构是生产级，不是简单包装
2. 服务、功能、安全、GDPR 是默认路径
3. 技术细节可解释、可复现、可审计

## 2. 演示前准备

```powershell
Set-Location C:\Users\jingwang1\projects\fda-genai-showcase
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

可选云认证（按环境）：
```powershell
gcloud auth application-default login
az account show --output table
```

## 3. 演示主线（建议顺序）

### Step A: 先看系统健康

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/health | ConvertTo-Json -Depth 8
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/architecture/status | ConvertTo-Json -Depth 8
```

讲解重点：
- 服务依赖是否在线
- 能力清单是否齐全
- 治理管线是否开启

### Step B: 内部资料 RAG 查询

在 UI 中：
1. Search Scope 选 `Internal Knowledge (RAG)`
2. Category 先留空（避免误过滤）
3. 输入内部资料相关问题（不要用天气类问题）
4. 点击 Search

讲解重点：
- 检索结果（chunk）
- RAG 答案
- citation 来源
- rerank 分数

### Step C: 治理与安全展示

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/governance/status | ConvertTo-Json -Depth 8
```

讲解重点：
- 输入输出安全筛查
- PII 脱敏
- 审计日志
- GDPR 能力状态

### Step D: 指标与 SLO

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/metrics | ConvertTo-Json -Depth 8
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/metrics/slos | ConvertTo-Json -Depth 8
```

讲解重点：
- TTFT、tokens/sec、cost/request
- SLO 是否达标

### Step E: 反馈闭环

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/feedback/friction | ConvertTo-Json -Depth 8
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/feedback/feature-requests | ConvertTo-Json -Depth 8
```

讲解重点：
- 生产摩擦点自动识别
- 自动结构化功能需求

## 4. 演示时常见坑与应对

1. RAG 无结果
- 检查 query 是否真的是内部资料问题
- 清空 category filter
- top_k 提高到 8 或 10

2. 没有 citation
- 确认检索结果有 source 字段
- 确认 UI 展示 citation 区块

3. 延迟偏高
- 看 TTFT 与 tokens/sec
- 看是否误走复杂编排路径

## 5. 招聘方关注点对应话术

1. Production engineering
- "我们有 ReAct 推理链和层级委派，不是黑盒单轮调用。"

2. Architectural governance
- "治理是中间件默认路径，安全与 GDPR 不靠人工约束。"

3. LLM-native metrics
- "我们看的是 TTFT/tokens/sec/cost，不仅是 HTTP 延迟。"

4. Product feedback loop
- "线上摩擦点自动沉淀为功能需求，形成持续改进闭环。"

5. 可复用能力
- "Skill 模块化 + BMAD 流程化，能跨客户复用和快速交付。"

## 6. 演示结束建议

1. 回到架构总览，复盘服务边界
2. 展示一条完整请求链路（输入 -> 治理 -> 检索 -> 推理 -> 监控）
3. 给出下一步实施计划（按 BMAD 分阶段）
