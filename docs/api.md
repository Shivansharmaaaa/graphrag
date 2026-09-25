# API Documentation

Reference for the `GraphRAG CTI Platform` REST API (v1.0.0), FastAPI backend.
Interactive Swagger UI: `GET /docs`. Raw OpenAPI spec: `GET /openapi.json` (also checked in at `docs/openapi.json`).

## Authentication

Most endpoints require a JWT bearer token obtained from `POST /api/auth/login`. Pass it as `Authorization: Bearer <token>`.
Enforcement endpoints (`/api/enforce/*`) instead require an API key header: `X-API-Key: edr-consumer-key`.

## Demo accounts

| user | password | role | TLP clearance |
|---|---|---|---|
| analyst | analyst123 | analyst | AMBER |
| junior | junior123 | analyst | GREEN |
| lead | lead123 | lead | RED (+ publish/ingest) |
| admin | admin123 | admin | RED (+ seed/reindex/delete) |

## Quick-start examples

```bash
# 1) login, capture the token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"analyst","password":"analyst123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# 2) system health (all four stores + LLM)
curl -s http://localhost:8000/api/health | python3 -m json.tool

# 3) graph traversal — shared C2 infrastructure
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/graph/shared-infrastructure/apt28"

# 4) semantic search
curl -s -X POST http://localhost:8000/api/search/semantic \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"spearphishing against government organisations","top_k":5}'

# 5) GraphRAG question with grounded citations
curl -s -X POST http://localhost:8000/api/graphrag/ask \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"question":"Which actors share command-and-control infrastructure, and what malware was hosted there?"}'

# 6) enforcement-plane lookup (API key, not JWT — Redis only, fail-closed)
curl -s -H "X-API-Key: edr-consumer-key" \
  "http://localhost:8000/api/enforce/check?type=ip&value=185.86.77.12"
```

---

## Endpoints

### admin

#### `GET /api/admin/integrity`
Admin Integrity
_Requires authentication._

**Responses:** 200

#### `POST /api/admin/reindex`
Admin Reindex
_Requires authentication._

**Responses:** 200

#### `POST /api/admin/seed`
Admin Seed
_Requires authentication._

**Responses:** 200


### audit

#### `GET /api/audit`
Audit List
_Requires authentication._

**Responses:** 200

#### `GET /api/audit/{audit_id}`
Audit Get
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `audit_id` | path | True | string |  |

**Responses:** 200, 422

#### `POST /api/audit/{audit_id}/replay`
Audit Replay
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `audit_id` | path | True | string |  |

**Responses:** 200, 422


### auth

#### `POST /api/auth/login`
Login

**Request body** (`application/json`): `LoginIn`

**Responses:** 200, 422

#### `GET /api/auth/me`
Me
_Requires authentication._

**Responses:** 200


### blocklist

#### `GET /api/blocklist`
Blocklist List
_Requires authentication._

**Responses:** 200

#### `POST /api/blocklist`
Blocklist Publish
_Requires authentication._

**Request body** (`application/json`): `PublishIn`

**Responses:** 200, 422

#### `GET /api/blocklist/{ioc_type}/{value}`
Blocklist Get
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `ioc_type` | path | True | string |  |
| `value` | path | True | string |  |

**Responses:** 200, 422

#### `DELETE /api/blocklist/{ioc_type}/{value}`
Blocklist Revoke
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `ioc_type` | path | True | string |  |
| `value` | path | True | string |  |

**Responses:** 200, 422


### enforce

#### `GET /api/enforce/check`
Enforce Check

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `type` | query | True | string |  |
| `value` | query | True | string |  |
| `x-api-key` | header | False |  |  |

**Responses:** 200, 422

#### `GET /api/enforce/export`
Enforce Export

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `format` | query | False | string |  |
| `x-api-key` | header | False |  |  |

**Responses:** 200, 422


### graph

#### `GET /api/graph/common-victims`
Q Common Victims
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `actor` | query | False |  |  |

**Responses:** 200, 422

#### `GET /api/graph/indicator/{value}`
UC4: historical HAS_IOC / OBSERVED_AS presence + citing documents, regardless of TTL.
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `value` | path | True | string |  |

**Responses:** 200, 422

#### `GET /api/graph/node/{node_id}`
Graph Node
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `node_id` | path | True | string |  |
| `hops` | query | False | integer |  |

**Responses:** 200, 422

#### `GET /api/graph/overview`
Graph Overview
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `limit` | query | False | integer |  |
| `include_reports` | query | False | boolean |  |

**Responses:** 200, 422

#### `GET /api/graph/path`
Q Path
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `src` | query | True | string |  |
| `dst` | query | True | string |  |
| `max_len` | query | False | integer |  |

**Responses:** 200, 422

#### `GET /api/graph/search`
Graph Search
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `q` | query | False | string |  |
| `label` | query | False |  |  |
| `limit` | query | False | integer |  |

**Responses:** 200, 422

#### `GET /api/graph/shared-infrastructure`
Q Shared Infra
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `actor` | query | False |  |  |

**Responses:** 200, 422

#### `GET /api/graph/shared-tooling`
Q Shared Tooling
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `malware` | query | False |  |  |
| `actor` | query | False |  |  |

**Responses:** 200, 422

#### `GET /api/graph/tool-users/{malware_id}`
Q Tool Users
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `malware_id` | path | True | string |  |

**Responses:** 200, 422


### graphrag

#### `POST /api/graphrag/ask`
Ask
_Requires authentication._

**Request body** (`application/json`): `AskIn`

**Responses:** 200, 422


### health

#### `GET /api/health`
Health

**Responses:** 200


### ingest

#### `GET /api/ingest/jobs`
Ingest Jobs
_Requires authentication._

**Responses:** 200

#### `POST /api/ingest/jobs/{job_id}/retry`
Ingest Retry
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `job_id` | path | True | string |  |

**Responses:** 200, 422

#### `POST /api/ingest/report`
Ingest Report
_Requires authentication._

**Request body** (`application/json`): `ReportIn`

**Responses:** 200, 422

#### `POST /api/ingest/stix`
Ingest Stix
_Requires authentication._

**Request body** (`application/json`): `StixIn`

**Responses:** 200, 422

#### `POST /api/ingest/stix/upload`
Ingest Stix File
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `publish_iocs` | query | False | boolean |  |

**Request body** (`multipart/form-data`): `Body_ingest_stix_file_api_ingest_stix_upload_post`

**Responses:** 200, 422


### meta

#### `GET /api/meta`
Meta
_Requires authentication._

**Responses:** 200


### reports

#### `GET /api/reports`
Reports
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `actor` | query | False |  |  |
| `tlp` | query | False |  |  |
| `q` | query | False |  |  |

**Responses:** 200, 422

#### `GET /api/reports/{report_id}`
Report
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `report_id` | path | True | string |  |

**Responses:** 200, 422

#### `DELETE /api/reports/{report_id}`
Delete Report
_Requires authentication._

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `report_id` | path | True | string |  |

**Responses:** 200, 422


### search

#### `POST /api/search/semantic`
Semantic
_Requires authentication._

**Request body** (`application/json`): `SearchIn`

**Responses:** 200, 422

