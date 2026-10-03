# Same-origin website gateway

`nginx.conf` is an Nginx **http-context include**, suitable for mounting at
`/etc/nginx/conf.d/default.conf` in an Nginx container. It expects `website:3000`
and `api:8000` to resolve on the same private container network. All paths and
query strings reach the upstream unchanged; no prefix is stripped.

| Browser route | Upstream |
| --- | --- |
| `/`, `/properties`, listing/area pages, `/_next/*`, metadata and Next route handlers | `website:3000` |
| `/assistant/` and `/assistant/assets/*` | `api:8000` |
| `/assistant` | 308 redirect to `/assistant/` |
| `/v1/*`, `/healthz`, `/readyz` | `api:8000` |
| `/v1/voice`, `/v1/telephony/media`, `/ws/*` | `api:8000`, with WebSocket upgrades |

## Local integration

1. Start the API, website, and gateway using
   `VOICE_ENABLED=false docker compose --profile website up --build`. The profile
   publishes only the gateway at `127.0.0.1:8080`; upstream ports stay private.
2. Configure the Vite assistant build with base `/assistant/`. FastAPI must
   serve its HTML at `/assistant/` and assets under `/assistant/assets/`.
   There is intentionally no proxy fallback from these routes to Next.js.
3. Open `http://localhost:8080`. Use relative `/v1/...` URLs and derive WebSocket
   URLs from the current browser origin. Allow the exact gateway origin in
   FastAPI `CORS_ORIGINS` because the voice session endpoint verifies Origin.
4. Set FastAPI `TRUSTED_PROXY_IPS` to the gateway's actual private address or a
   dedicated, isolated network CIDR. Avoid `*`. The gateway overwrites client
   forwarding headers, so arbitrary requests cannot choose an upstream IP or
   scheme. For native local processes, replace upstream hostnames with
   `127.0.0.1` and their existing ports in a local copy of this configuration.

Validate in the configured gateway environment before starting traffic:

```sh
nginx -t
```

Run the command inside the gateway container if that is where Nginx and the
`website`/`api` DNS names exist. A local syntax check cannot resolve container
service names unless configured accordingly.

## Staging and production

TLS terminates at an upstream load balancer or ingress. Keep the gateway port
private and reachable only by that terminator. Add the actual public hostname
to the application `server_name` (unrecognized hosts are rejected), change
`set $awaaz_external_scheme $scheme` to `set $awaaz_external_scheme https`, and
configure the terminator to preserve the original Host header and WebSocket
upgrades. Redirect public HTTP to HTTPS and enable HSTS at the terminator
after validating HTTPS. Do not deploy this HTTP listener as a public endpoint.

For accurate caller IP limits behind another proxy, configure Nginx
`set_real_ip_from` with only the terminator's exact trusted addresses, and
`real_ip_header` for its documented client-IP header. Until that is done,
FastAPI sees the terminator IP; limits may group callers together. Never accept
client-IP headers from all networks. Use HTTPS public origins in FastAPI and
configure Twilio's public base URL to the externally visible origin so its
signature checks use the same URL the caller requested.

The application owns authentication, staff roles, record authorization, CSRF,
rate limits, consent, and private media access. Staff and customer responses
must set private/no-store cache headers. Nginx adds basic transport response
headers, permits same-origin microphone use, and leaves application CSP and
Set-Cookie headers intact. Use an application nonce-based CSP rather than a
global policy that would break Next.js scripts. Public health checks should
use `/healthz`; `/readyz` reports optional provider readiness and can be more
expensive. Restrict detailed readiness at the edge if it exposes operational
information unsuitable for the public deployment.

## Limits and acceptance

- Request bodies are capped at **10,000,000 bytes**, matching the current API
  default. Keep this value and backend `MAX_UPLOAD_BYTES` aligned; include
  multipart overhead if new media routes need it. The edge buffers bounded
  request bodies before forwarding them. API file-type/parser limits are still
  required, and WebSocket frame limits remain FastAPI's responsibility.
- Connect timeout is 5 seconds, ordinary upstream idle timeout is 60 seconds,
  and voice/socket idle timeout is 300 seconds. Socket ping frames or traffic
  must keep sessions active; align terminator timeouts with these values.
- Responses stream without buffering. The gateway has no response cache and
  performs no upstream retry; application idempotency/retry controls remain
  authoritative. Logs omit query strings, cookies, and authorization headers;
  application code should also avoid sensitive data in URL paths.
- Start/reload Nginx after upstreams are reachable. These static upstream names
  are resolved at configuration load, so reload after container IP changes.
- Validate public pages and direct deep links, Next assets, assistant HTML and
  assets, API JSON/errors, cookies/CSRF, unknown-host rejection, a 413 upload,
  forwarded-header spoofing, and WebSocket authentication plus an audible voice
  turn through the gateway. Test behind the actual TLS terminator as well.
- This file has no certificates, DNS, gateway image, Compose service, public
  deployment, or live validation. Those remain integration steps.

References: [Nginx WebSocket proxying](https://nginx.org/en/docs/http/websocket.html),
[proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html),
and [request body limits](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size).
