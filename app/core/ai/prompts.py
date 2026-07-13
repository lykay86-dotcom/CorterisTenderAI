"""Prompt text for structured RM-109 analysis."""

SYSTEM_PROMPT = """Analyze only supplied tender documents. Return JSON. Every finding must include document_id and an exact quote. If a quote is absent, mark the finding unverified; do not infer facts. Extract requirements, risks, suspicious conditions, contradictions and missing documents."""
