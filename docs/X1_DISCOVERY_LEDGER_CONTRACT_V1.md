# CMIS X1 Discovery Ledger Contract v1

Status: proposed foundation contract for CMIS issue #364.

This contract is **foundation-only/internal**. It does not promote a public CMIS
service or Scout-reliance capability.

## Purpose

The Discovery Ledger records the earliest accepted verified observation of an
X1 asset plus later accepted observations so first-observation history can be
replayed without relying on conversational memory, LLM inference, provider
labels, or an assumed token launch date.

Canonical authority remains:

```text
User
  -> Roberta
    -> X1 Scout
      -> CMIS
        -> X1 Provider / verified source
```

CMIS owns the observation semantics. Roberta and X1 Scout may consume a later
explicitly promoted wrapper, but they must not construct first-seen facts
independently.

## Version

```text
contract = x1_discovery_ledger/v1
chain = x1
subject_kind = x1_asset
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

## Canonical subject identity

V1 accepts only an X1 fungible asset whose canonical identity is a verified mint
under the accepted X1 identity contract.

```text
identity_contract = x1_asset_identity/v1
identity_root = mint
identity_verified = true
```

The observation subject id MUST equal the verified mint. Symbol and name are
descriptors and MUST NOT merge distinct mints.

Wallet, protocol, pool, bridge, validator, and other entity kinds are outside v1
and require a separately reviewed contract extension.

## Observation record

An accepted v1 observation preserves:

- contract version;
- chain;
- subject kind;
- canonical subject id;
- verified mint;
- identity contract and verification state;
- observation kind;
- normalized observation/fact time when available;
- whether fact time is verified;
- CMIS recorded/ingestion time separately;
- exact source id;
- source role;
- exact source-scope identifier;
- verification state;
- optional Evidence Receipt id;
- optional Proof Score id;
- limitations;
- warnings;
- deterministic content id;
- `execution_authorized=false`.

No risk field exists in the v1 ledger record. Proof metadata is preserved without
being converted into risk.

## Time semantics

### Fact time

`fact_time_unix` is the normalized Unix-second fact time that the accepted
source/evidence contract supports for the observation.

The ledger MUST NOT substitute CMIS ingestion time, collection time, provider
listing time, token creation time, block time from an unrelated fact, or model
inference for missing fact time.

A fact time may be stored with `fact_time_verified=false`; such a record does
not establish first-observation order.

### Recorded time

`recorded_at_unix` is when CMIS accepted the record into this foundation. It is
operational provenance only and MUST NOT establish or displace first verified
observation.

Both time values use integer Unix seconds in v1 and MUST be in the inclusive
range `0..9007199254740991` (`2**53 - 1`). This bound keeps canonical JSON
timestamp values exactly representable across Python and JavaScript/JSON
implementations used to reproduce content and state hashes. Booleans, floats,
strings, negative values, values above this bound, NaN, and infinities are
rejected.

## First verified observation

For a canonical tuple:

```text
(chain, subject_kind, subject_id, observation_kind)
```

`first_verified_observed_at` is the minimum `fact_time_unix` among accepted
records where **all** of the following are true:

```text
verification_state = verified
identity_verified = true
fact_time_verified = true
fact_time_unix is present
```

It means only:

> earliest verified fact time currently accepted by this CMIS Discovery Ledger
> for this exact subject and observation semantics.

It does NOT mean:

- token creation time;
- token launch time;
- first-ever X1 appearance;
- first provider listing;
- complete asset lifetime start;
- first observation by any external system.

If no accepted record has verified fact time, first verified observation is
unknown.

A later-arriving record with an earlier verified fact time may become the new
first verified observation. No prior record is mutated or deleted.

## Same-time tie

When multiple accepted records have the same earliest verified fact time, the
record with the lexicographically smallest deterministic content id is selected
as the stable tie representative.

The tie-break establishes deterministic replay only; it does not imply one
source observed the fact earlier than another.

## Content identity

Content identity is SHA-256 over canonical JSON of the exact immutable object
below, excluding the content id itself:

```json
{
  "contract_version": "x1_discovery_ledger/v1",
  "chain": "x1",
  "subject_kind": "x1_asset",
  "subject_id": "<canonical mint>",
  "mint": "<canonical mint>",
  "identity_contract": "x1_asset_identity/v1",
  "identity_verified": true,
  "observation_kind": "<non-empty text>",
  "fact_time_unix": "<integer Unix seconds or null>",
  "fact_time_verified": "<boolean>",
  "recorded_at_unix": "<integer Unix seconds>",
  "source_id": "<non-empty text>",
  "source_role": "<non-empty text>",
  "source_scope": "<non-empty text>",
  "verification_state": "<verified|partial|unavailable|conflict>",
  "evidence_receipt_id": "<non-empty text or null>",
  "proof_score_id": "<non-empty text or null>",
  "limitations": ["<normalized text>", "..."],
  "warnings": ["<normalized text>", "..."],
  "execution_authorized": false
}
```

```text
discovery_observation_id = do_<64 lowercase hex>
```

Canonicalization is exact:

- encode as UTF-8;
- serialize every object member shown above, including optional evidence/proof
  fields as JSON `null` when absent;
- sort JSON object keys lexicographically;
- use compact separators `,` and `:` with no insignificant whitespace;
- escape quotation mark as `\"` and reverse solidus as `\\`; escape backspace,
  form feed, line feed, carriage return, and tab as `\b`, `\f`, `\n`, `\r`,
  and `\t`, respectively;
- escape all other U+0000 through U+001F characters as `\u00xx` with lowercase
  hexadecimal digits; do not escape solidus (`/`), DEL (U+007F), or any other
  Unicode scalar value, including non-ASCII text, U+2028/U+2029, and emoji;
- encode those unescaped scalar values directly as UTF-8, with no BOM, no
  trailing newline, and no Unicode normalization; reject surrogate code points
  (U+D800 through U+DFFF) before creating an observation;
- preserve integer/boolean/null scalar types exactly;
- require `fact_time_unix` and `recorded_at_unix` integers to remain within
  `0..9007199254740991` so canonical hashes are portable across compliant
  Python and JavaScript implementations;
- require actual strings for every text scalar and text-array member before
  trimming; numbers, booleans, mappings, and lists must never be coerced to text;
- optional Evidence Receipt and Proof Score ids accept `null` or non-empty
  strings only; limitations/warnings are arrays (empty when omitted), not `null`;
- normalize each `limitations` / `warnings` entry by trimming surrounding
  whitespace and rejecting empty/non-text entries;
- sort each limitations/warnings array lexicographically and remove exact
  duplicates before serialization;
- do not include `content_id` in the hashed object.

For the accepted scalar domain, these serialization rules are equivalent to
Python `json.dumps(payload, sort_keys=True, separators=(",", ":"),
ensure_ascii=False).encode("utf-8")`. The same string-escaping rules apply to
ledger-state hashing. Input JSON escape spelling does not change identity:
literal `café` and decoded `caf\u00e9` represent the same string; canonically
distinct Unicode sequences are not silently normalized into one another.

An exact duplicate is idempotent. The same supplied content id with a different
canonical payload is a tamper/conflict and fails closed.

## Append and replay

The v1 foundation is append-only.

- existing accepted records are never rewritten;
- exact duplicates do not create a second record;
- later accepted records append;
- replaying the same accepted record sequence produces the same state;
- first-observation selection is recomputed deterministically from immutable
  records;
- serialization preserves all accepted records and their content ids.

This first slice defines deterministic state/replay semantics. Durable database
binding may be added behind this contract after the in-memory/reference behavior
is accepted.

## Failure semantics

Fail closed on:

- chain other than `x1`;
- subject kind other than `x1_asset`;
- missing/empty mint;
- subject id different from mint;
- identity contract other than `x1_asset_identity/v1`;
- `identity_verified != true`;
- empty observation kind;
- empty source id/role/scope;
- unsupported verification state;
- invalid fact or recorded time, including any value above
  `9007199254740991`;
- verified fact-time flag without a fact time;
- supplied content id that does not exactly match canonical content;
- duplicate content id with a different payload;
- `execution_authorized != false`.

Missing optional evidence ids remain missing. They are never invented.

## Verification state

The initial accepted values are:

```text
verified
partial
unavailable
conflict
```

Only a record with `verification_state=verified`,
`identity_verified=true`, and `fact_time_verified=true` may establish
`first_verified_observed_at`.

Partial/unavailable/conflict observations may be retained for provenance/replay
but cannot establish first verified observation.

## Evidence / Proof Score / risk boundary

The ledger may preserve existing Evidence Receipt and Proof Score identifiers
from accepted CMIS evidence. It does not generate a replacement evidence system.

- Proof Score remains separate from risk.
- Discovery observation frequency is not risk.
- Earlier observation is not safety or legitimacy.
- Missing proof is not zero proof.
- No record authorizes behavioral, ownership, whale, insider, bot, manipulation,
  fraud, scam, intent, or future-performance labels.

## Public/service posture

For this issue and v1 foundation implementation:

```text
public_service_promoted = false
scout_reliance_promoted = false
read_only = true
execution_authorized = false
```

No new runtime service is added to `PUBLIC_RUNTIME_SERVICES`.

A later separately reviewed issue may define a narrow public wrapper such as:

```text
x1_discovery_history/v1
```

Only after ledger identity, replay, persistence, evidence, and failure semantics
are accepted.

## Deterministic acceptance cases

The implementation must cover at least:

1. first accepted verified fact-time observation;
2. later arrival with an earlier verified fact time;
3. record with missing/unverified fact time retained but not first;
4. exact duplicate idempotency;
5. supplied-id/payload tamper rejection;
6. same-time deterministic content-id tie;
7. unverified alias/identity rejection;
8. cross-chain rejection;
9. partial/conflict record retained but not first;
10. Proof Score preservation without risk synthesis;
11. serialization/replay equivalence;
12. `execution_authorized=false` enforcement;
13. non-string scalar/array-member rejection through factory, constructor, and
    serialized replay, including optional evidence/proof ids;
14. pinned Unicode/control-character canonical bytes and content/state hashes;
15. invalid surrogate rejection before hashing and preservation of distinct
    Unicode sequences without normalization;
16. timestamp boundary acceptance at `2**53 - 1` and rejection above it across
    factory, direct-constructor, and serialized-replay entry points.

## Non-goals

V1 does not:

- infer launch or creation time;
- claim complete asset-lifetime coverage;
- discover wallets/owners;
- classify popularity or legitimacy;
- calculate trend, alpha, risk, or future performance;
- deliver alerts;
- promote a public service;
- authorize Scout reliance;
- call providers directly from Roberta;
- prepare, sign, broadcast, or execute transactions.

**Discovery records what CMIS can prove it observed; it does not invent when an
asset began to exist.**
