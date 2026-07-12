from __future__ import annotations

import pytest

from app.tenders.participation_decision import ParticipationDecisionRecommendation
from app.tenders.participation_decision_policy import ParticipationDecisionPolicy


@pytest.mark.parametrize(
    ("score", "expected"),
    (
        (0, ParticipationDecisionRecommendation.DO_NOT_PARTICIPATE),
        (39, ParticipationDecisionRecommendation.DO_NOT_PARTICIPATE),
        (40, ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW),
        (74, ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW),
        (75, ParticipationDecisionRecommendation.PARTICIPATE),
        (90, ParticipationDecisionRecommendation.PARTICIPATE),
    ),
)
def test_policy_uses_approved_rm107_score_bands(score, expected) -> None:
    assert ParticipationDecisionPolicy().recommendation_for_score(score) == expected
