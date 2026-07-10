# Архитектурная схема

```mermaid
flowchart LR
 UI[PySide6 UI] --> APP[Application Services]
 APP --> IMPORT[Import Service]
 APP --> ANALYSIS[Analysis Engine]
 APP --> EST[Estimate Engine]
 APP --> DOCS[Document Generator]
 IMPORT --> PARSERS[PDF/DOCX/XLSX Parsers]
 ANALYSIS --> RULES[Legal / Competition / Technical Rules]
 APP --> REPO[Repositories]
 REPO --> DB[(SQLite / PostgreSQL)]
 APP --> AI[AI Provider Adapter]
 APP --> CONN[Platform Connectors]
 AI --> OPENAI[OpenAI-compatible / Ollama]
 CONN --> SOURCES[Official APIs / Manual Import]
```

## База данных
Tender 1—N Document; Tender 1—N Analysis. Следующие сущности: Company, User, Role, Equipment, Supplier, Estimate, EstimateItem, GeneratedDocument, Task, Notification, AuditLog.
