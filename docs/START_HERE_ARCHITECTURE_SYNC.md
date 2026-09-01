# Start Here — Roberta ↔ CMIS Architecture Sync

Last reconciled: 2026-09-01 (America/New_York)

For current cross-project architecture and status, read in this order:

1. `ROBERTA_INTEGRATION_CONTRACT.md`
2. `ROBERTA_CMIS_ACCEPTED_BASELINE.md`
3. `ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md`
4. `docs/CMIS_PRODUCT_ROADMAP.md`
5. `docs/ROADMAP_RECONCILIATION_2026-09-01.md`
6. `docs/PROJECT_STATUS_2026-09-01.md`

The controlling authority model is `User -> Roberta -> Chain Scout -> CMIS -> Chain Provider`. CMIS remains the deterministic freshness-sensitive truth/evidence/risk layer beneath Chain Scouts. Roberta's accepted Learning Plane remains separate from that live-fact authority path and cannot promote learning state into CMIS/provider truth or execution authority.

Dated status/sync files through 2026-08-30 are historical snapshots. They must not override the living roadmap, the mirrored 2026-09-01 source-sync baseline, or the 2026-09-01 roadmap/status reconciliation.

Controlled Execution remains locked/not started and unauthorized.
