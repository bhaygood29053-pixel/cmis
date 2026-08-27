# Public HTTPS CMIS Deployment for Roberta Readiness

CMIS is designed to run as a private Python service behind an HTTPS reverse
proxy. Do **not** expose the Python HTTP server directly to the Internet.

## Target topology

```text
GitHub Actions / Roberta deployment
          |
          | HTTPS :443
          v
   public TLS reverse proxy
          |
          | loopback only
          v
  127.0.0.1:8765 CMIS
          |
          v
 X1 / XDEX / X1 RPC providers
```

CMIS remains read-only. This deployment profile does not add transaction
construction, signing, broadcasting, custody, trading, bridging, or value
movement.

## 1. Prerequisites

Use a Linux host with:

- a public IP address;
- a DNS name such as `cmis.example.com` pointing to that host;
- Python/CMIS installed under a normal non-root user;
- Caddy installed as the TLS reverse proxy;
- inbound TCP 80 and 443 permitted;
- port 8765 **not** publicly opened.

The repository-local `.env` must include at minimum:

```dotenv
X1_NINJA_API_KEY=<provider credential>
CMIS_HOST=127.0.0.1
CMIS_PORT=8765
CMIS_API_KEY=<long random bearer token>
```

Never commit the real values.

Generate a CMIS bearer token locally, for example:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Store it only in deployment secrets.

## 2. Run CMIS on loopback

Install the existing managed service:

```bash
bash scripts/install_cmis_systemd.sh
```

Confirm that it is healthy only on loopback:

```bash
curl -fsS http://127.0.0.1:8765/healthz
ss -ltn | grep 8765
```

Expected listener:

```text
127.0.0.1:8765
```

Do not change the managed CMIS process to `0.0.0.0` for this deployment
profile.

## 3. Install the HTTPS reverse proxy

Copy the example:

```bash
sudo cp deployment/Caddyfile.cmis.example /etc/caddy/Caddyfile
sudo editor /etc/caddy/Caddyfile
```

Replace `cmis.example.com` with the real DNS name.

Validate and reload:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
```

Caddy terminates TLS and forwards the original `Authorization` header to the
loopback CMIS process. CMIS remains the authoritative Bearer-token validator for
`/v1/cmis` and `/v1/cmis/capabilities`.

The example exposes only:

- `/healthz`
- `/v1/cmis/capabilities`
- `/v1/cmis`

All other paths receive 404 from the edge.

## 4. Verify the public deployment before Roberta uses it

From a machine outside the CMIS host:

```bash
export CMIS_BASE_URL=https://cmis.example.com
export CMIS_API_KEY='<same bearer token configured on CMIS>'
python scripts/check_cmis_public_readiness.py
```

The preflight fails closed unless all of these are true:

1. the public origin uses HTTPS and is not loopback;
2. `/healthz` identifies a healthy CMIS gateway;
3. unauthenticated `/v1/cmis/capabilities` returns HTTP 401;
4. the supplied Bearer token can read capabilities;
5. the deployed CMIS contract is at least 1.11.0;
6. X1 `asset_lookup` advertises `x1_asset_identity/v1`;
7. exact-mint normalization remains mint-rooted;
8. Metaplex/XDEX reconciliation is advertised;
9. required identity limitations remain present, including the distinction
   between XDEX outage and proven mint absence.

A current CMIS 1.12.x deployment satisfies the version requirement because the
normalized-identity contract was introduced in 1.11.0 and remains part of the
accepted surface.

## 5. Configure Roberta GitHub Actions

In the **Roberta** repository, configure:

Repository variable:

```text
CMIS_BASE_URL=https://cmis.example.com
```

Repository secrets:

```text
CMIS_API_KEY=<same CMIS bearer token>
DEEPSEEK_API_KEY=<Roberta readiness model credential>
```

`CMIS_API_KEY` is required when the public CMIS deployment uses the accepted
Bearer-authenticated profile. `DEEPSEEK_API_KEY` is independently required by
Roberta's controlled replay and configured readiness corpora.

Do not put either secret into repository variables, workflow YAML, issue
comments, or committed `.env` files.

## 6. Run Roberta readiness

After the deployment preflight passes and the GitHub configuration exists,
rerun the Roberta **read-only readiness** workflow.

Required jobs:

```text
deterministic-tests                              -> success
controlled degraded-evidence + freshness replay -> success
configured Scout -> CMIS live readiness          -> success
```

The configured live lane is the deployment proof that matters for issue #234.
A local `127.0.0.1:8765` process cannot satisfy that GitHub-hosted lane because
the runner is on a different machine.

## 7. Operational checks

Useful host-side commands:

```bash
systemctl status cmis-gateway.service --no-pager
journalctl -u cmis-gateway.service -n 100 --no-pager
systemctl status caddy --no-pager
curl -fsS http://127.0.0.1:8765/healthz
```

Useful external checks:

```bash
curl -fsS https://cmis.example.com/healthz
curl -i https://cmis.example.com/v1/cmis/capabilities
curl -fsS \
  -H "Authorization: Bearer $CMIS_API_KEY" \
  https://cmis.example.com/v1/cmis/capabilities
```

The second command should return HTTP 401 without a token.

## Security boundary

This profile intentionally uses two layers:

```text
TLS/network boundary -> Caddy
service authorization -> CMIS Bearer validation
```

The reverse proxy does not replace CMIS authorization. If the public preflight
detects that capabilities are reachable without Bearer auth, deployment
acceptance fails.

Provider credentials stay on the CMIS host. Roberta receives only the CMIS URL
and its dedicated service Bearer token.
