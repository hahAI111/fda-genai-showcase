# GDPR Compliance Policy for Enterprise AI Systems

## 1. Overview
This policy ensures all AI systems comply with the General Data Protection Regulation (EU 2016/679).
It applies to any processing of personal data by AI/ML models, RAG pipelines, and automated agents.

## 2. Lawful Basis for Processing
| Activity | Lawful Basis | Justification |
|----------|-------------|---------------|
| Knowledge search (RAG) | Legitimate interest | Enterprise productivity tool |
| Chat with AI agent | Legitimate interest | Internal business tool |
| Content generation (media) | Legitimate interest | Marketing asset creation |
| Quality evaluation | Legitimate interest | Service quality improvement |
| Audit logging | Legal obligation | SOC 2 / compliance requirement |

## 3. Data Subject Rights Implementation

### 3.1 Right of Access (Article 15)
- **Endpoint**: `POST /gdpr/user-data` with `user_id`
- **Response time**: Within 30 days (automated: instant)
- **Scope**: Audit logs, chat records, media generation history
- **Format**: Machine-readable JSON export

### 3.2 Right to Erasure (Article 17)
- **Endpoint**: `DELETE /gdpr/user-data` with `user_id`
- **Response time**: Within 30 days (automated: scheduled)
- **Scope**: All personal data across Cosmos DB, PostgreSQL, audit logs
- **Exceptions**: Data required for legal compliance is retained with justification

### 3.3 Right to Data Portability (Article 20)
- All data exportable in standard JSON format
- Chat history, media assets, and audit trail included
- API-accessible for automated data portability requests

### 3.4 Right to Rectification (Article 16)
- Users can update their profile and preferences
- Incorrect records can be flagged for correction

## 4. Data Protection Measures

### 4.1 PII Protection (Pre-LLM)
- All user inputs screened for PII before reaching any LLM
- Detected PII types: email, phone, SSN, credit card, IP address, date of birth
- Masking applied automatically: `john@email.com` → `[EMAIL_REDACTED]`
- Original PII never stored in LLM context or logs

### 4.2 Content Safety Pipeline
```
User Input → Content Safety (injection detection) → PII Masking → LLM → Output Safety → Audit
```
- Prompt injection detection (6+ regex patterns)
- Azure AI Content Safety integration (Hate, Violence, SelfHarm, Sexual categories)
- Output screening for system prompt leakage
- All blocked inputs logged to audit trail

### 4.3 Data Minimization
- Only necessary data collected for each operation
- Chat context limited to current conversation (no cross-session tracking)
- Media generation prompts stored for audit only, not for training
- Embeddings generated from enterprise documents only, never from user PII

## 5. Data Retention

| Data Type | Retention Period | After Expiry |
|-----------|-----------------|--------------|
| Audit logs | 90 days (configurable) | Archived to cold storage |
| Chat records | 90 days | Auto-deleted |
| Media assets | 90 days | Auto-deleted from Cosmos DB |
| Search logs | 90 days | Auto-deleted from PostgreSQL |
| Error logs | 30 days | Auto-deleted |

## 6. Data Processing Agreements
- Azure OpenAI: Microsoft DPA covers GDPR requirements
- Azure AI Search: Data stays within configured Azure region
- Azure Cosmos DB: Encryption at rest with Microsoft-managed keys
- All data processing within EU/US regions as configured

## 7. Breach Notification
- Automated monitoring for unusual access patterns
- Data breach notification within 72 hours (GDPR Article 33)
- Structured audit trail enables rapid impact assessment
- Affected users notified without undue delay (Article 34)

## 8. Privacy by Design
This platform implements privacy by design (Article 25):
1. **Default masking**: PII masked before any model sees it
2. **Minimal data collection**: Only what's needed for the task
3. **Audit by default**: Every interaction logged
4. **Identity-based auth**: No API keys, Azure AD/Entra ID only
5. **Content safety**: Automated screening on both input and output
