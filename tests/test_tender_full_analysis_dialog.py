from __future__ import annotations
from dataclasses import replace
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMessageBox
import pytest

from app.core.ai.recheck import (
    AI_RECHECK_DISCLAIMER,
    TenderAiRecheckResult,
    compare_ai_analyses,
)
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiApplicationRequirementsStatus,
    AiAnalysisProvenance,
    AiCompetitionAssessment,
    AiCompetitionCategory,
    AiCompetitionItem,
    AiCompetitionReviewPriority,
    AiCompetitionSourceRef,
    AiCompetitionStatus,
    AiDocument,
    AiDocumentAnalysis,
    AiDocumentationCompletenessAssessment,
    AiDocumentationCompletenessStatus,
    AiDocumentationDocumentSnapshot,
    AiDocumentationIssue,
    AiDocumentationIssueCode,
    AiDocumentationScope,
    AiDraftContractAnalysis,
    AiDraftContractStatus,
    AiFinding,
    AiFindingStatus,
    AiFinancialReviewPriority,
    AiFinancialRiskAssessment,
    AiFinancialRiskCategory,
    AiFinancialRiskItem,
    AiFinancialRiskSourceRef,
    AiFinancialRiskStatus,
    AiLegalReviewPriority,
    AiLegalRiskAssessment,
    AiLegalRiskCategory,
    AiLegalRiskItem,
    AiLegalRiskSourceRef,
    AiLegalRiskStatus,
    AiSourceSnapshot,
    AiTechnicalSpecificationAnalysis,
    AiTechnicalSpecificationStatus,
    TenderRequirements,
)
from app.core.ai.citations import resolve_citation
from app.core.document_classification import DocumentKind
from app.tenders.full_analysis import (
    FullAnalysisProgress,
    FullAnalysisStage,
    FullAnalysisStatus,
    TenderFullAnalysisResult,
)
from app.ui.tender_full_analysis_dialog import (
    TenderFullAnalysisDialog,
    _render_ai_document_analysis,
)


def _current_analysis() -> AiDocumentAnalysis:
    fingerprint = "d" * 64
    checksum = "b" * 64
    document = AiDocument(
        "doc",
        "tender.pdf",
        "local_document_store",
        "pdf",
        "2026-07-14T10:00:00+00:00",
        "verified",
        "exact quote",
        checksum,
        original_character_count=11,
        document_kind=DocumentKind.APPLICATION_REQUIREMENTS.value,
    )
    evidence = resolve_citation(
        document_id="doc",
        quote="exact quote",
        section="Раздел 1",
        page=2,
        confidence=0.8,
        documents=(document,),
        context_fingerprint=fingerprint,
    ).evidence
    assert evidence is not None
    evidence = replace(evidence, section="Раздел 1", page=2)
    source = AiSourceSnapshot(
        document_id="doc",
        display_name="tender.pdf",
        document_type="pdf",
        checksum_sha256=checksum,
        verification_status="verified",
        received_at="2026-07-14T10:00:00+00:00",
        truncated=True,
        included_character_count=11,
        original_character_count=20,
        document_kind=DocumentKind.APPLICATION_REQUIREMENTS.value,
    )
    provenance = AiAnalysisProvenance(
        analysis_id="analysis_123",
        context_fingerprint=fingerprint,
        created_at="2026-07-14T10:01:00+00:00",
        prompt_version="6",
        output_schema_version="4",
        persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
        analyzer_version="11",
        context_version="6",
        citation_resolver_version="1",
        provider_id="openai",
        provider_model="gpt-5",
        provider_response_id="resp_" + "a" * 64,
        sources=(source,),
    )
    verified = AiFinding("risk", "Confirmed", evidence, AiFindingStatus.VERIFIED)
    unverified = AiFinding("risk", "Unconfirmed", None, AiFindingStatus.UNVERIFIED)
    return AiDocumentAnalysis(
        "procurement:test",
        "Safe",
        risks=(verified, unverified),
        status="partial",
        provenance=provenance,
    )


def _app():
    return QApplication.instance() or QApplication([])


def test_dialog_emits_cancel_and_updates_progress() -> None:
    app = _app()
    dialog = TenderFullAnalysisDialog("procurement:test")
    requested = []
    dialog.cancel_requested.connect(requested.append)
    dialog.begin()
    dialog.update_progress(
        FullAnalysisProgress(
            stage=FullAnalysisStage.DOWNLOADING,
            message="Скачивание",
            completed_steps=2,
        )
    )
    dialog.cancel_button.click()
    assert requested == ["procurement:test"]
    assert dialog.progress.value() == 22
    app.processEvents()


def test_dialog_has_dedicated_ai_summary_tab() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")

    assert dialog.tabs.count() == 4
    assert dialog.tabs.tabText(2) == "AI summary"
    assert dialog.tabs.tabText(3) == "AI-анализ"


def test_dialog_shows_dedicated_ai_progress_stage() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")

    row = dialog._stage_rows[FullAnalysisStage.RUNNING_AI]
    assert dialog.stages.item(row, 0).text() == "AI-анализ документации"


def test_dialog_renders_technical_specification_status_groups_and_evidence() -> None:
    analysis = _current_analysis()
    verified = analysis.risks[0]
    unverified = analysis.risks[1]
    analysis = replace(
        analysis,
        technical_specification=AiTechnicalSpecificationAnalysis(
            status=AiTechnicalSpecificationStatus.PARTIAL,
            document_ids=("doc",),
            scope=(verified,),
            ambiguities=(unverified,),
            warnings=("Контекст технического задания неполон.",),
        ),
    )

    html = _render_ai_document_analysis(_result(analysis))

    assert "Техническое задание" in html
    assert "Частичный результат" in html
    assert "Confirmed" in html
    assert "Неподтверждённый вывод" in html
    assert "Контекст технического задания неполон" in html


def test_dialog_renders_draft_contract_groups_status_warnings_and_evidence() -> None:
    analysis = _current_analysis()
    verified = analysis.risks[0]
    unverified = analysis.risks[1]
    analysis = replace(
        analysis,
        draft_contract=AiDraftContractAnalysis(
            status=AiDraftContractStatus.PARTIAL,
            document_ids=("doc",),
            included_document_ids=("doc",),
            subject_and_scope=(unverified,),
            payment_terms=(verified,),
            warnings=("Контекст проекта договора/контракта неполон.",),
        ),
    )

    result = _result(analysis)
    html = _render_ai_document_analysis(result)

    assert "Проект договора/контракта" in html
    assert "Частичный результат" in html
    for label in (
        "Предмет и объём обязательств",
        "Сроки, этапы и место исполнения",
        "Цена и изменение цены",
        "Условия оплаты",
        "Приёмка и закрывающие документы",
        "Обеспечение исполнения и гарантий",
        "Гарантия и устранение недостатков",
        "Обязанности и зависимости заказчика",
        "Обязанности исполнителя и субподряд",
        "Ответственность, штрафы и убытки",
        "Изменение, приостановка и расторжение",
        "Форс-мажор и уведомления",
        "Споры, конфиденциальность и права",
        "Неоднозначности",
        "Противоречия",
        "Вопросы для уточнения",
    ):
        assert label in html
    assert "Контекст проекта договора/контракта неполон." in html
    assert "Неподтверждённый вывод — не влияет на рекомендацию." in html
    assert "corteris-citation://open/" in html


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (AiDraftContractStatus.COMPLETE, "Полный результат"),
        (AiDraftContractStatus.PARTIAL, "Частичный результат"),
        (AiDraftContractStatus.NOT_FOUND, "Проект договора/контракта не найден"),
        (AiDraftContractStatus.UNAVAILABLE, "Анализ проекта договора/контракта недоступен"),
    ],
)
def test_dialog_renders_all_draft_contract_statuses(
    status: AiDraftContractStatus,
    expected: str,
) -> None:
    analysis = replace(
        _current_analysis(),
        draft_contract=AiDraftContractAnalysis(status=status),
    )

    html = _render_ai_document_analysis(_result(analysis))

    assert expected in html


def test_dialog_renders_scoped_application_requirements_groups_and_evidence() -> None:
    analysis = _current_analysis()
    requirements = TenderRequirements(
        status=AiApplicationRequirementsStatus.PARTIAL,
        document_ids=("doc", "missing"),
        included_document_ids=("doc",),
        documents=(analysis.risks[0],),
        ambiguities=(analysis.risks[1],),
        warnings=("Контекст требований к заявке неполон.",),
    )

    html = _render_ai_document_analysis(_result(replace(analysis, requirements=requirements)))

    assert "Требования к заявке" in html
    assert "Частичный результат" in html
    assert "найдено 2" in html
    assert "включено 1" in html
    for label in (
        "Состав заявки",
        "Требования к участнику",
        "Декларации и согласия",
        "Оборудование и ресурсы",
        "Сертификаты и качество",
        "Лицензии, допуски и СРО",
        "Специалисты и квалификация",
        "Подтверждающие документы",
        "Опыт исполнения",
        "Сроки подачи и действия заявки",
        "Гарантийные обязательства",
        "Обеспечение заявки",
        "Обеспечение исполнения контракта",
        "Банковская или независимая гарантия",
        "Формат и подписание",
        "Национальный режим и происхождение",
        "Ценовое предложение и смета",
        "Основания отклонения",
        "Неоднозначности",
        "Противоречия",
        "Вопросы для уточнения",
    ):
        assert label in html
    assert "Контекст требований к заявке неполон." in html
    assert "Неподтверждённый вывод — не влияет на рекомендацию." in html
    assert "corteris-citation://open/" in html


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (AiApplicationRequirementsStatus.COMPLETE, "Полный результат"),
        (AiApplicationRequirementsStatus.PARTIAL, "Частичный результат"),
        (AiApplicationRequirementsStatus.NOT_FOUND, "Требования к заявке не найдены"),
        (AiApplicationRequirementsStatus.UNAVAILABLE, "Анализ требований к заявке недоступен"),
    ),
)
def test_dialog_renders_all_application_requirement_statuses(
    status: AiApplicationRequirementsStatus,
    expected: str,
) -> None:
    analysis = replace(
        _current_analysis(),
        requirements=TenderRequirements(status=status),
    )

    assert expected in _render_ai_document_analysis(_result(analysis))


def _result(analysis: AiDocumentAnalysis) -> TenderFullAnalysisResult:
    return TenderFullAnalysisResult(
        registry_key="procurement:test",
        procurement_number="test",
        status=FullAnalysisStatus.PARTIAL,
        started_at="2026-07-13T00:00:00+03:00",
        completed_at="2026-07-13T00:01:00+03:00",
        download=None,
        archives=None,
        text=None,
        requirements=None,
        score=None,
        legacy=None,
        ai_document_analysis=analysis,
    )


@pytest.mark.parametrize(
    ("status", "label"),
    [
        ("complete", "Завершён"),
        ("partial", "Частичный результат"),
        ("no_documents", "Нет документов для анализа"),
        ("provider_disabled", "AI-провайдер отключён"),
        ("provider_error", "AI-провайдер недоступен"),
        ("invalid_response", "Ответ AI отклонён"),
        ("cache_incompatible", "Кеш несовместим"),
    ],
)
def test_ai_tab_has_safe_human_readable_status(status: str, label: str) -> None:
    html = _render_ai_document_analysis(
        _result(AiDocumentAnalysis("procurement:test", "Safe", status=status))
    )

    assert label in html


@pytest.mark.parametrize(
    ("status", "label"),
    [
        ("complete", "Локально известный комплект готов для текущего анализа"),
        ("partial", "Комплект обработан частично; требуется устранить проблемы"),
        ("no_documents", "Документы для проверки не найдены"),
        ("unavailable", "Оценка полноты документации недоступна"),
    ],
)
def test_ai_tab_renders_all_documentation_statuses(status: str, label: str) -> None:
    analysis = replace(
        _current_analysis(),
        documentation_completeness_assessment=AiDocumentationCompletenessAssessment(
            status=AiDocumentationCompletenessStatus(status)
        ),
    )

    html = _render_ai_document_analysis(_result(analysis))

    assert "Полнота документации" in html
    assert label in html
    assert html.index("Полнота документации") < html.index("Техническое задание")


def test_ai_tab_escapes_documentation_details_and_separates_provider_claims() -> None:
    snapshot = AiDocumentationDocumentSnapshot(
        "ts",
        r"C:\Users\SecretUser\<script>specification</script>.pdf",
        DocumentKind.TECHNICAL_SPECIFICATION,
        "catalog",
        "failed",
        "not_recorded",
        "",
        False,
        False,
        False,
        False,
    )
    issue = AiDocumentationIssue(
        "documentation_" + "b" * 32,
        AiDocumentationIssueCode.DOWNLOAD_FAILED,
        AiDocumentationScope.TECHNICAL_SPECIFICATION,
        ("ts",),
        "<script>local issue</script>",
        "<img src=x onerror=alert(1)>",
    )
    analysis = replace(
        _current_analysis(),
        missing_documents=("<script>provider claim</script>",),
        documentation_inventory=(snapshot,),
        documentation_completeness_assessment=AiDocumentationCompletenessAssessment(
            status=AiDocumentationCompletenessStatus.PARTIAL,
            known_document_count=1,
            issues=(issue,),
        ),
    )

    html = _render_ai_document_analysis(_result(analysis))

    assert "<script>specification</script>.pdf" not in html
    assert "unknown" in html
    assert "&lt;script&gt;local issue&lt;/script&gt;" in html
    assert "&lt;script&gt;provider claim&lt;/script&gt;" in html
    assert "Возможные отсутствующие документы по ответу AI — не подтверждено" in html
    assert r"C:\Users\SecretUser" not in html
    assert "<script>" not in html


def test_ai_tab_distinguishes_verified_and_unverified_findings() -> None:
    html = _render_ai_document_analysis(_result(_current_analysis()))

    assert "exact quote" in html
    assert "Неподтверждённый вывод" in html


def test_ai_tab_renders_safe_current_citation_details() -> None:
    analysis = _current_analysis()
    evidence = analysis.risks[0].evidence
    assert evidence is not None

    html = _render_ai_document_analysis(_result(analysis))

    assert "tender.pdf" in html
    assert "страница 2" in html
    assert "раздел Раздел 1" in html
    assert "Цитата: exact quote" in html
    assert "уверенность AI 80%" in html
    assert f"{evidence.citation_id[:12]}…" in html
    assert "контекст источника сокращён" in html
    assert f"corteris-citation://open/{evidence.citation_id}" in html


def test_ai_tab_renders_legal_registry_disclaimer_priority_action_and_citation() -> None:
    base = _current_analysis()
    finding = base.risks[0]
    assert finding.evidence is not None
    legal = AiLegalRiskAssessment(
        status=AiLegalRiskStatus.COMPLETE,
        policy_version="1",
        items=(
            AiLegalRiskItem(
                risk_id="legal_" + "a" * 32,
                category=AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS,
                review_priority=AiLegalReviewPriority.ELEVATED,
                title="Проверка разрешений и допуска",
                source_refs=(
                    AiLegalRiskSourceRef(
                        "requirements",
                        "licenses",
                        finding.evidence.citation_id,
                    ),
                ),
                recommended_action="Проверить применимость требования к участнику.",
            ),
        ),
        warnings=(),
    )
    analysis = replace(
        base,
        risks=(),
        requirements=TenderRequirements(
            status=AiApplicationRequirementsStatus.COMPLETE,
            document_ids=("doc",),
            included_document_ids=("doc",),
            licenses=(finding,),
        ),
        legal_risk_assessment=legal,
    )

    html = _render_ai_document_analysis(_result(analysis))

    assert "Юридические риски" in html
    assert "Информационная оценка; не является юридическим заключением" in html
    assert "Проверка разрешений и допуска" in html
    assert "Повышенный" in html
    assert "Проверить применимость требования к участнику." in html
    assert "Confirmed" in html
    assert f"corteris-citation://open/{finding.evidence.citation_id}" in html


def test_ai_tab_renders_financial_registry_disclaimer_action_and_citation() -> None:
    base = _current_analysis()
    finding = base.risks[0]
    assert finding.evidence is not None
    financial = AiFinancialRiskAssessment(
        status=AiFinancialRiskStatus.COMPLETE,
        policy_version="1",
        items=(
            AiFinancialRiskItem(
                risk_id="financial_" + "a" * 32,
                category=AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS,
                review_priority=AiFinancialReviewPriority.ELEVATED,
                title="Обеспечение и стоимость гарантий",
                source_refs=(
                    AiFinancialRiskSourceRef(
                        "requirements",
                        "bid_security",
                        finding.evidence.citation_id,
                    ),
                ),
                recommended_action="Проверить размер и стоимость обеспечения.",
            ),
        ),
        warnings=(),
    )
    analysis = replace(
        base,
        risks=(),
        requirements=TenderRequirements(
            status=AiApplicationRequirementsStatus.COMPLETE,
            document_ids=("doc",),
            included_document_ids=("doc",),
            bid_security=(finding,),
        ),
        financial_risk_assessment=financial,
    )

    html = _render_ai_document_analysis(_result(analysis))

    assert "Финансовые условия" in html
    assert (
        "Информационная оценка условий документации; не является финансовым прогнозом, "
        "расчётом убытка или рекомендацией об участии."
    ) in html
    assert "Обеспечение и стоимость гарантий" in html
    assert "Повышенный" in html
    assert "Проверить размер и стоимость обеспечения." in html
    assert "Confirmed" in html
    assert f"corteris-citation://open/{finding.evidence.citation_id}" in html


def test_ai_tab_renders_competition_registry_disclaimer_action_and_citation() -> None:
    base = _current_analysis()
    finding = base.risks[0]
    assert finding.evidence is not None
    competition = AiCompetitionAssessment(
        status=AiCompetitionStatus.COMPLETE,
        policy_version="1",
        items=(
            AiCompetitionItem(
                condition_id="competition_" + "a" * 32,
                category=AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
                review_priority=AiCompetitionReviewPriority.ELEVATED,
                title="Обеспечение и финансовый порог участия",
                source_refs=(
                    AiCompetitionSourceRef(
                        "requirements",
                        "bid_security",
                        finding.evidence.citation_id,
                    ),
                ),
                recommended_action="Проверить условия обеспечения вручную.",
            ),
        ),
        warnings=(),
    )
    analysis = replace(
        base,
        risks=(),
        requirements=TenderRequirements(
            status=AiApplicationRequirementsStatus.COMPLETE,
            document_ids=("doc",),
            included_document_ids=("doc",),
            bid_security=(finding,),
        ),
        competition_assessment=competition,
    )

    html = _render_ai_document_analysis(_result(analysis))

    assert "Анализ конкуренции" in html
    assert (
        "Информационная оценка документально подтверждённых условий участия. Не является "
        "оценкой числа конкурентов, вероятности победы, законности условий закупки или "
        "рекомендацией об участии."
    ) in html
    assert "Обеспечение и финансовый порог участия" in html
    assert "Повышенный" in html
    assert "Проверить условия обеспечения вручную." in html
    assert "Confirmed" in html
    assert f"corteris-citation://open/{finding.evidence.citation_id}" in html


def test_dialog_emits_only_known_strict_citation_links() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")
    analysis = _current_analysis()
    evidence = analysis.risks[0].evidence
    assert evidence is not None
    requests: list[tuple[str, str]] = []
    dialog.citation_requested.connect(
        lambda registry, document: requests.append((registry, document))
    )
    dialog.set_result(_result(analysis))

    invalid_urls = (
        "file:///C:/secret.pdf",
        "http://open/cit_" + "a" * 32,
        "https://open/cit_" + "a" * 32,
        "data:text/plain,secret",
        "javascript:alert(1)",
        r"\\server\share\secret.pdf",
        "corteris-citation://open/cit_" + "0" * 32,
        f"corteris-citation://open/{evidence.citation_id}?document=secret",
        f"corteris-citation://open/{evidence.citation_id}#secret",
        f"corteris-citation://user@open/{evidence.citation_id}",
    )
    for value in invalid_urls:
        dialog.ai_analysis.anchorClicked.emit(QUrl(value))

    assert requests == []

    dialog.ai_analysis.anchorClicked.emit(QUrl(f"corteris-citation://open/{evidence.citation_id}"))
    assert requests == [("procurement:test", "doc")]


def test_ai_tab_displays_truncated_context_warning_without_traceback() -> None:
    html = _render_ai_document_analysis(
        _result(
            AiDocumentAnalysis(
                "procurement:test",
                "Safe",
                status="partial",
                warnings=("Контекст сокращён.",),
                context_document_count=2,
                context_character_count=100,
                context_truncated=True,
            )
        )
    )

    assert "2 документов" in html
    assert "контекст сокращён" in html.casefold()
    assert "Traceback" not in html


def test_dialog_can_render_successful_retry_after_error() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")
    dialog.set_error("temporary failure")

    dialog.set_result(
        _result(AiDocumentAnalysis("procurement:test", "Recovered", status="complete"))
    )

    assert "Recovered" in dialog.ai_analysis.toPlainText()
    assert dialog.export_ai_button.isEnabled()


def test_ai_recheck_button_requires_valid_current_provenance_and_emits_after_confirmation(
    monkeypatch,
) -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")
    requested: list[str] = []
    dialog.ai_recheck_requested.connect(requested.append)

    assert dialog.ai_recheck_button.text() == "Повторно проверить AI"
    assert dialog.ai_recheck_button.isEnabled() is False

    dialog.set_result(_result(_current_analysis()))
    assert dialog.ai_recheck_button.isEnabled() is True
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )

    dialog.ai_recheck_button.click()

    assert requested == ["procurement:test"]
    assert dialog.tabs.count() == 4


def test_ai_recheck_running_state_blocks_double_click_and_renders_result() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")
    baseline = _current_analysis()
    current = replace(
        baseline,
        summary="Changed safely <script>SECRET</script>",
        provenance=replace(
            baseline.provenance,
            analysis_id="analysis_current",
            created_at="2026-07-15T11:00:00+00:00",
            provider_response_id="resp_" + "f" * 64,
        ),
    )
    dialog.set_result(_result(baseline))

    dialog.begin_ai_recheck()

    assert dialog.ai_recheck_button.isEnabled() is False
    assert dialog.message_label.text() == "Повторная проверка AI…"

    result = TenderAiRecheckResult(
        registry_key="procurement:test",
        current_analysis=current,
        assessment=compare_ai_analyses(baseline, current),
        started_at="2026-07-15T11:00:00+00:00",
        completed_at="2026-07-15T11:00:01+00:00",
        warnings=(),
    )
    dialog.set_ai_recheck_result(result)
    html = dialog.ai_analysis.toHtml()

    assert dialog.ai_recheck_button.isEnabled() is True
    assert "Повторная проверка AI" in dialog.ai_analysis.toPlainText()
    assert AI_RECHECK_DISCLAIMER in dialog.ai_analysis.toPlainText()
    assert "Изменён" in dialog.ai_analysis.toPlainText()
    assert "<script>" not in html


@pytest.mark.parametrize("status", ["provider_error", "no_documents", "invalid_response"])
def test_ai_recheck_button_stays_disabled_for_non_comparable_current_status(status: str) -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")
    dialog.set_result(_result(replace(_current_analysis(), status=status)))

    assert dialog.ai_recheck_button.isEnabled() is False
