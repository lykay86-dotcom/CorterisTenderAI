"""Repository-free compact projections from RM-149 detail snapshots."""

from app.tenders.detail.contracts import TenderCardProjection, TenderDetailSnapshot


def project_tender_card(snapshot: TenderDetailSnapshot) -> TenderCardProjection:
    facts = {item.stable_id: item for item in snapshot.facts}
    statuses = {item.stable_id: item for item in snapshot.statuses}
    return TenderCardProjection(
        identity=snapshot.identity,
        title=snapshot.title,
        source=snapshot.source,
        lifecycle=statuses["lifecycle"].value if "lifecycle" in statuses else "not_loaded",
        deadline=statuses["deadline"].value if "deadline" in statuses else "not_loaded",
        price=facts["price"].value if "price" in facts else "",
        price_accessible=facts["price"].accessible_value if "price" in facts else "not loaded",
        verification=statuses["verification"].value if "verification" in statuses else "not_loaded",
        freshness=statuses["freshness"].value if "freshness" in statuses else "not_loaded",
        conflicts=statuses["conflicts"].value if "conflicts" in statuses else "not_loaded",
        decision=snapshot.decision.recommendation if snapshot.decision else "not_loaded",
        critical_warning=snapshot.critical_warnings[0].title if snapshot.critical_warnings else "",
        primary_action=snapshot.primary_action,
        snapshot_fingerprint=snapshot.fingerprint,
        accessible_summary=snapshot.accessible_summary,
    )


__all__ = ["project_tender_card"]
