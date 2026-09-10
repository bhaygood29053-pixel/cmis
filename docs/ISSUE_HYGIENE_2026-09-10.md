# CMIS Issue Hygiene — 2026-09-10

## Resolved stale umbrella

Issue #385 (`Instant X1 Scan freshness proof v1 — current market fact-time`) is closed as superseded by accepted later contracts.

The accepted chain begins with CMIS 1.17 / PR #386, which introduced field-scoped current-market freshness while preserving collection time as distinct from provider fact time. Later accepted current-market and Instant X1 Scan versions extended those semantics rather than reopening #385 as a product blocker.

This hygiene closure does not establish universal provider fact time, source independence, or whole-market freshness. Provider/field-specific questions remain governed by their own later contracts and issues.

`execution_authorized=false`
