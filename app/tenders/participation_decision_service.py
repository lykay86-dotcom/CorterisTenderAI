"""RM-107.3 conservative assembly service for participation decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.tenders.collector.verification import TenderVerificationStatus
from app.tenders.commercial_estimator import CommercialEstimateStatus
from app.tenders.participation_decision import (
    ParticipationDecision,
    ParticipationDecisionEvidence,
    ParticipationDecisionInput,
    ParticipationDecisionRecommendation,
)
from app.tenders.participation_decision_policy import ParticipationDecisionPolicy
from app.core.ai.schemas import AiDocumentAnalysis, AiFinding


class ParticipationDecisionService:
    """Assemble existing evidence; RM-107.4 will own detailed policy rules."""

    def __init__(
        self,
        score_service: object,
        state_repository: object,
        commercial_estimate_repository: object,
        *,
        policy: ParticipationDecisionPolicy | None = None,
    ) -> None:
        self.score_service = score_service
        self.state_repository = state_repository
        self.commercial_estimate_repository = commercial_estimate_repository
        self.policy = policy or ParticipationDecisionPolicy()

    def evaluate(
        self,
        registry_key: str,
        *,
        ai_document_analysis: AiDocumentAnalysis | None = None,
    ) -> ParticipationDecision:
        key = registry_key.strip()
        if not key:
            raise ValueError("registry_key must not be empty")
        score = self.score_service.latest(key)
        stop = self.state_repository.get_latest_stop_factor_assessment(key)
        verification = self.state_repository.get_verification_state(key)
        latest_estimate = self.commercial_estimate_repository.latest(key)
        estimate = latest_estimate[1] if latest_estimate is not None else None
        ai_analysis = ai_document_analysis
        decision_input = ParticipationDecisionInput(
            registry_key=key,
            score=score,
            stop_factor_assessment=stop,
            commercial_estimate=estimate,
            verification=verification,
            ai_document_analysis=ai_analysis,
        )
        verified_ai_findings = _current_verified_ai_findings(ai_analysis)
        recommendation, summary, evidence = self._decide(
            decision_input,
            verified_ai_findings,
        )
        missing = _missing_data(decision_input)
        actions = _action_plan(decision_input, missing, verified_ai_findings)
        confidence = _decision_confidence(evidence, missing)
        stop_factors = tuple(item.title for item in (stop.factors if stop is not None else ()))
        decision = ParticipationDecision(
            decision_id=uuid4().hex,
            registry_key=key,
            recommendation=recommendation,
            confidence=confidence,
            summary=summary,
            evidence=tuple(evidence),
            input=decision_input,
            decided_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            policy_version=self.policy.policy_version,
            score=score.total_score if score is not None else 0,
            stop_factors=stop_factors,
            missing=missing,
            actions=actions,
        )
        save = getattr(self.state_repository, "save_participation_decision", None)
        if callable(save):
            save(decision)
        return decision

    def _decide(
        self,
        decision_input: ParticipationDecisionInput,
        verified_ai_findings: tuple[AiFinding, ...],
    ) -> tuple[
        ParticipationDecisionRecommendation,
        str,
        list[ParticipationDecisionEvidence],
    ]:
        evidence: list[ParticipationDecisionEvidence] = []
        stop = decision_input.stop_factor_assessment
        if stop is not None:
            stop_recommendation = self.policy.recommendation_for_stop_factor(stop.status)
            if stop_recommendation == ParticipationDecisionRecommendation.DO_NOT_PARTICIPATE:
                return (
                    ParticipationDecisionRecommendation.DO_NOT_PARTICIPATE,
                    "Участие заблокировано обязательным требованием.",
                    [
                        _evidence(
                            "blocked_requirement",
                            "Стоп-фактор",
                            "Обнаружено обязательное требование, которое не выполнено.",
                            "stop_factor",
                            1.0,
                            -100,
                        )
                    ],
                )
            if stop_recommendation == ParticipationDecisionRecommendation.DATA_INSUFFICIENT:
                evidence.append(
                    _evidence(
                        "stop_data_insufficient",
                        "Стоп-факторы",
                        "Недостаточно подтверждённых данных для снятия стоп-факторов.",
                        "stop_factor",
                        0.4,
                        -25,
                    )
                )
            elif (
                stop_recommendation == ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW
            ):
                evidence.append(
                    _evidence(
                        "conditional_stop_factor",
                        "Стоп-факторы",
                        "Участие возможно только после выполнения условий.",
                        "stop_factor",
                        0.7,
                        -15,
                    )
                )

        if decision_input.score is None:
            evidence.append(
                _evidence(
                    "score_missing",
                    "Рейтинг",
                    "Предварительный рейтинг ещё не рассчитан.",
                    "participation_score",
                    0.0,
                    -30,
                )
            )
        else:
            components = tuple(getattr(decision_input.score, "components", ()))
            if components:
                for component in components:
                    evidence.append(
                        _evidence(
                            f"score_{component.key}",
                            component.title,
                            component.explanation,
                            "participation_score",
                            0.75,
                            component.score,
                        )
                    )
            else:
                evidence.append(
                    _evidence(
                        "score_available",
                        "Рейтинг",
                        f"Предварительный балл: {decision_input.score.total_score}/100.",
                        "participation_score",
                        0.75,
                        decision_input.score.total_score,
                    )
                )

        estimate = decision_input.commercial_estimate
        if estimate is None or estimate.status != CommercialEstimateStatus.COMPLETE:
            evidence.append(
                _evidence(
                    "estimate_incomplete",
                    "Коммерческий расчёт",
                    "Полный коммерческий расчёт отсутствует или содержит незаполненные данные.",
                    "commercial_estimator",
                    0.0,
                    -15,
                )
            )
        else:
            impact = 0
            margin = getattr(estimate, "margin_percent", None)
            if margin is not None:
                impact = 12 if margin >= 15 else (5 if margin >= 0 else -15)
            evidence.append(
                _evidence(
                    "estimate_complete",
                    "Коммерческий расчёт",
                    "Коммерческий расчёт заполнен.",
                    "commercial_estimator",
                    0.9,
                    impact,
                )
            )

        verification = decision_input.verification
        unverified = {
            TenderVerificationStatus.MISSING,
            TenderVerificationStatus.UNVERIFIED,
            TenderVerificationStatus.AGGREGATOR_ONLY,
            TenderVerificationStatus.INCOMPLETE,
            TenderVerificationStatus.CONFLICT,
        }
        if verification is None or verification.status in unverified:
            evidence.append(
                _evidence(
                    "verification_incomplete",
                    "Достоверность данных",
                    "Критичные поля не подтверждены официальным источником.",
                    "verification",
                    0.0,
                    -20,
                )
            )
        else:
            evidence.append(
                _evidence(
                    "verification_available",
                    "Достоверность данных",
                    "Данные подтверждены доступным источником.",
                    "verification",
                    verification.minimum_confidence,
                )
            )

        for item in verified_ai_findings:
            evidence.append(
                _evidence(
                    "ai_document_risk",
                    "AI-анализ документации",
                    item.statement,
                    "ai_document_analysis",
                    item.evidence.confidence,
                    -8,
                )
            )

        if any(item.confidence == 0.0 for item in evidence):
            return (
                ParticipationDecisionRecommendation.DATA_INSUFFICIENT,
                "Недостаточно данных для решения об участии.",
                evidence,
            )
        if (
            stop is not None
            and self.policy.recommendation_for_stop_factor(stop.status)
            == ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW
        ):
            return (
                ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW,
                "Участие возможно после ручной проверки условий.",
                evidence,
            )
        if verified_ai_findings:
            return (
                ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW,
                "AI-анализ выявил подтверждённые документами условия, требующие ручной проверки.",
                evidence,
            )
        score = decision_input.score
        assert score is not None
        recommendation = self.policy.recommendation_for_score(score.total_score)
        return (recommendation, score.recommendation_text, evidence)


def _evidence(
    code: str,
    title: str,
    detail: str,
    source: str,
    confidence: float,
    impact: int = 0,
) -> ParticipationDecisionEvidence:
    return ParticipationDecisionEvidence(code, title, detail, confidence, source, impact)


def _missing_data(decision_input: ParticipationDecisionInput) -> tuple[str, ...]:
    missing: list[str] = []
    score = decision_input.score
    if score is None:
        missing.append("Итоговый рейтинг")
    else:
        missing.extend(str(item) for item in getattr(score, "missing_documents", ()))
    estimate = decision_input.commercial_estimate
    if estimate is None or estimate.status != CommercialEstimateStatus.COMPLETE:
        missing.append("Смета и коммерческий расчёт")
    verification = decision_input.verification
    if verification is None:
        missing.append("Проверка критичных данных")
    else:
        missing.extend(str(item) for item in getattr(verification, "missing_fields", ()))
    ai_analysis = decision_input.ai_document_analysis
    if ai_analysis is not None:
        missing.extend(ai_analysis.missing_documents)
    return tuple(dict.fromkeys(item for item in missing if item.strip()))


def _action_plan(
    decision_input: ParticipationDecisionInput,
    missing: tuple[str, ...],
    verified_ai_findings: tuple[AiFinding, ...],
) -> tuple[str, ...]:
    actions = [f"Получить или уточнить: {item}" for item in missing]
    stop = decision_input.stop_factor_assessment
    if stop is not None:
        actions.extend(
            item.evidence.remediation for item in stop.factors if item.evidence.remediation.strip()
        )
    if verified_ai_findings:
        actions.append("Провести ручную проверку условий, отмеченных AI-анализом")
    if not missing and not actions:
        actions.extend(("Подготовить коммерческое предложение", "Проверить сроки подачи заявки"))
    return tuple(dict.fromkeys(actions))


def _current_verified_ai_findings(
    ai_analysis: AiDocumentAnalysis | None,
) -> tuple[AiFinding, ...]:
    if ai_analysis is None:
        return ()
    return tuple(
        item
        for item in (
            *ai_analysis.risks,
            *ai_analysis.suspicious_conditions,
            *ai_analysis.contradictions,
        )
        if ai_analysis.is_current_verified(item)
    )


def _decision_confidence(
    evidence: list[ParticipationDecisionEvidence],
    missing: tuple[str, ...],
) -> float:
    positive = [item.confidence for item in evidence if item.confidence > 0]
    base = min(positive) if positive else 0.0
    zero_penalty = min(0.5, sum(item.confidence == 0 for item in evidence) * 0.25)
    missing_penalty = min(0.35, len(missing) * 0.05)
    return round(max(0.0, min(1.0, base - zero_penalty - missing_penalty)), 2)


__all__ = ["ParticipationDecisionService"]
