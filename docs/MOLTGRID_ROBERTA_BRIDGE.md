# MoltGrid → Roberta bridge

This integration preserves the existing MoltGrid/Signal transport implemented in the CMIS repository's compatibility `liquidity_scout` namespace while making **Roberta the sole normal conversational/orchestration front door**.

The historical Liquidity Scout name may still appear in compatibility module paths, service-unit names, and legacy-router code. Those names describe retained runtime compatibility, not a second current user-facing product.

Recommended production flow:

```text
MoltGrid / Signal
       ↓
CMIS-repository transport/admission/duplicate protection
       ↓
optional simple-only channel gate
       ↓
Roberta
       ↓
Chain Scout
       ↓
CMIS
       ↓
Chain Provider
```

CMIS remains the deterministic market/risk/evidence authority. Roberta remains the conversational/coordinating authority. The transport does not recompute CMIS facts.

## Recommended all-questions mode

Enable:

```text
ROBERTA_MOLTGRID_ALL_QUESTIONS_ENABLED=1
```

When enabled, every message admitted by the existing Signal intake is owned by the Roberta-first bridge before the historical legacy question router can answer it.

The legacy router remains for deliberate diagnostics/rollback only. It is **not** an automatic user-facing fallback. If Roberta cannot return a valid bridge response, the user receives only:

> Roberta is temporarily unavailable. Please try your request again shortly.

The existing reply-link confirmation remains authoritative so a failed/ambiguous post cannot create a second visible reply.

## MoltGrid simple-only policy

For the current MoltGrid surface, enable the conservative presentation policy with:

```text
ROBERTA_MOLTGRID_SIMPLE_ONLY_ENABLED=1
```

This is a **channel/presentation policy**, not a limitation on Roberta's underlying capabilities.

Concise requests may continue to Roberta, including general conversation, simple explanations, single current market facts, short token questions, and simple status questions.

Long/structured requests may be declined at the channel boundary, including multi-asset comparisons, rankings, long historical reports, detailed pre-trade/risk analysis, raw evidence/diagnostics, tables, JSON/CSV/code, or prompts too large for the current interface.

The fixed interface response is:

> Thank you for your question. This request requires more detailed analysis or formatting than MoltGrid's current messaging interface can reliably support. To preserve accuracy and readability, I'm unable to provide that analysis on this site at this time. I can still help here with general questions and concise information.

Supported replies are rendered as MoltGrid-safe plain text. Presentation conversion must not recalculate or alter answer facts.

## Compatibility routing mode

When all-questions mode is off, the earlier selected-route flags remain available:

```text
ROBERTA_MOLTGRID_PRETRADE_ENABLED=1
ROBERTA_MOLTGRID_CONVERSATION_ENABLED=1
```

These are rollback/compatibility controls. Once a request is handed to Roberta, bridge failure must still return the concise availability message rather than exposing a legacy formatter or raw CMIS output.

## Recommended production service stack

Run CMIS, Roberta, and the MoltGrid listener as managed systemd services.

### 1. CMIS gateway

From the `bhaygood29053-pixel/cmis` repository:

```bash
bash scripts/install_cmis_systemd.sh
```

CMIS listens on `127.0.0.1:8765`.

### 2. Roberta bridge

From `bhaygood29053-pixel/roberta-langgraph`:

```bash
bash scripts/install_roberta_bridge_systemd.sh
```

Roberta listens on `127.0.0.1:8766`.

### 3. MoltGrid listener dependency drop-in

The existing listener unit may retain the historical compatibility name `liquidity-scout.service`. Install its dependency drop-in from the CMIS repository:

```bash
bash scripts/install_moltgrid_service_dependencies.sh
```

The helper declares:

```ini
[Unit]
Wants=roberta-bridge.service cmis-gateway.service
After=roberta-bridge.service cmis-gateway.service
```

It also adds health gates for:

```text
http://127.0.0.1:8766/healthz
http://127.0.0.1:8765/healthz
```

Each dependency receives a bounded startup-health wait. `Wants=` is intentionally used rather than `Requires=` so a later downstream restart does not automatically tear down the transport.

If a deployment uses a different listener unit name, set `LIQUIDITY_SCOUT_SERVICE_NAME` when running the compatibility helper. That environment-variable name is retained as a compatibility interface.

Expected topology:

```text
cmis-gateway.service       -> 127.0.0.1:8765
roberta-bridge.service     -> 127.0.0.1:8766
            \                 /
             \               /
              v             v
       compatibility listener
                     ↓
              MoltGrid / Signal
                     ↓
                  Roberta
                     ↓
                Chain Scout
                     ↓
                    CMIS
```

## Manual development start order

For local development only:

```bash
python -m liquidity_scout.cmis.http
```

Then, from the Roberta repository:

```bash
roberta-serve
```

Then the compatibility MoltGrid listener:

```bash
ROBERTA_MOLTGRID_ALL_QUESTIONS_ENABLED=1 \
ROBERTA_MOLTGRID_SIMPLE_ONLY_ENABLED=1 \
python -m liquidity_scout.integrations.moltgrid_roberta
```

Do not run a manual listener at the same time as the managed listener service.

Defaults:

```text
ROBERTA_BASE_URL=http://127.0.0.1:8766
ROBERTA_TIMEOUT_SECONDS=60
```

If `ROBERTA_API_KEY` is configured on the Roberta bridge, configure the same value in the listener environment so it can be sent as a Bearer token. Do not store secrets in Git.

## Failure behavior

In Roberta-first all-questions mode, a supported user message is sent to Roberta exactly as admitted. If the bridge is unavailable or returns an invalid service envelope, the listener does not execute the historical legacy router for the user. It posts only the fixed Roberta availability response.

The legacy router can still be invoked deliberately by an operator for diagnostics/rollback; it is not part of the automatic production failure path.

When simple-only mode declines a question, the fixed interface-policy message is returned before any request is sent to Roberta.

## Safety boundary

This bridge adds no transaction construction, signing, broadcasting, wallet custody, trading, autonomous execution, or value movement.

Pre-trade remains analysis-only when available, and Roberta's chain facts continue to flow through the appropriate Chain Scout and deterministic CMIS service boundary.
