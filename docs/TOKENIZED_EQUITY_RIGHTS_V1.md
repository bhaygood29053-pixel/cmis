# Tokenized Equity Rights v1

`tokenized_equity_rights/v1` is the bounded CMIS contract for answering the rights side of the question:

> What exactly am I buying, and what rights does the token holder actually have?

It sits above accepted `tokenized_equity_provenance/v1`. Provenance establishes exact token/security structural identity; it does not itself establish legal rights.

## Required dimensions

Every record contains all nine dimensions:

1. underlying ownership / exposure type
2. voting rights
3. dividend or economic-distribution treatment
4. redemption / conversion rights
5. backing / collateral representation
6. issuer and material counterparty identities
7. jurisdiction / governing-document scope
8. transfer restrictions / eligibility constraints
9. custody structure / dependency

## State model

Each dimension uses exactly one state:

- `VERIFIED`
- `DENIED`
- `CONDITIONAL`
- `UNKNOWN`
- `NOT_APPLICABLE`

`UNKNOWN` is the fail-closed state when decisive evidence is unavailable.

A non-`UNKNOWN` state requires at least one source from an accepted authoritative class. `CONDITIONAL` also requires explicit conditions. `DENIED` and `NOT_APPLICABLE` are factual claims too, so they cannot be asserted without authoritative evidence.

## Evidence requirements

Every bound evidence item carries:

- evidence id
- source authority class
- absolute HTTPS source URL
- document id
- section
- source fact time
- retrieval time
- SHA-256 content identity

The contract recognizes authoritative classes such as governing documents, offering documents/prospectuses, regulatory filings, custody/depositary/trust agreements, official terms, corporate-action notices, statutes/rules, and court/regulator orders.

Marketing material, blogs, news, secondary research, social media, and community material may be retained as context but cannot independently create a decisive rights state.

## Meaning of VERIFIED

Within this contract, `VERIFIED` means the bounded claim is structurally bound to at least one accepted authoritative source class. It does **not** mean CMIS has issued a legal opinion, independently adjudicated enforceability, established regulatory compliance, or proven that the source's substantive statement is legally correct.

That distinction is intentionally exposed as:

`state_semantics = evidence_bound_claim_status_not_legal_adjudication`

## Hard boundaries

The contract does not infer any of the following:

- provenance = beneficial/shareholder ownership
- token name/ticker = legal or economic equivalence
- wrapper token = underlying share
- token transfer = securities ownership transfer
- backing description = backing sufficiency
- custody description = custody safety
- issuer marketing = enforceable holder right
- tokenized-equity structure = live X1 deployment
- Robinhood Chain discovery = live Robinhood→X1 route
- evidence-bound state = legal advice or compliance conclusion
- any rights result = automatic risk or trade recommendation

## Promotion state

This is a structural/evidence-binding foundation only:

- `read_only=true`
- `public_service_promoted=false`
- `scout_reliance_promoted=false`
- `execution_authorized=false`

Public service promotion, protected materialization, source-content verification, freshness policy, and ROBERTA/X1 Scout reliance require separate acceptance steps.

Parent workstream: CMIS #660
Implementation issue: CMIS #668
