# RM-155 cross-stage regression gate

| Stage | Preserved invariant | Primary gate |
|---|---|---|
| RM-142 | one typed registry, aliases, history/context/back/deep links | navigation suites |
| RM-143 | tokens/icons/style matrix, no literal colors | design-system guard |
| RM-144 | canonical page, one workflow owner, bounded shutdown | composition/lifecycle suites |
| RM-145 | KPI definitions/evidence/drill-down owner | Dashboard KPI suites |
| RM-146 | chart API/data/accessibility/export/frozen | chart + frozen suites |
| RM-147 | deterministic analytics/filter/provenance/drill-down/export | analytics suites |
| RM-148 | Decimal/currency/rounding/migration/parity | financial suites |
| RM-149 | registry vs legacy identity, critical precedence, stale action | detail suites |
| RM-150 | table identity/selection/action/export/accessibility | table suites |
| RM-151 | safe operation episodes/redaction/notification adapter | operations guard/suites |
| RM-152 | focus/keyboard/contrast evidence and truthful exceptions | strict accessibility validator |
| RM-153 | timing/resource guards and theme epochs | performance/resource suites |
| RM-154 | strict canonical 14-case visual comparison and privacy | CI visual gate |

Every gate also preserves RM-107 score/recommendation/critical stop-factor priority. Any changed
decision payload, duplicate owner, unexpected network/keyring access, schema/dependency change,
new warning, visual baseline rewrite or untruthful native status stops publication.
