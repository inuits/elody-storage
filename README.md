<p align="center">
  <a href="https://elody.eu"><img src="https://elody.eu/images/logo.svg" alt="Elody" width="96" /></a>
</p>

<p align="center">Part of <a href="https://elody.eu">Elody</a> — the open semantic data platform.</p>

# Inuits DAMS Storage API

Flask service that fronts an S3-compatible object store (MinIO in local dev, any S3 provider in prod) and hands out signed URLs / tickets to the PWA and other Elody services. Handles single-shot uploads, resumable chunked streams, ticket-scoped downloads, transcode outputs, and dedup lookups by MD5.

## Endpoints

### Uploads

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/upload` | Upload a file; server assigns the key. |
| `POST` | `/upload/<key>` | Upload a file to a caller-chosen key. |
| `POST` | `/upload-with-ticket` | Upload authenticated via a short-lived ticket (no full session). |
| `POST` | `/upload-with-ticket/<key>` | Ticketed upload to a specific key. |
| `POST` | `/upload/transcode` | Store output produced by the transcode service. |

### Streamed / resumable uploads

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/upload/init-stream` | Start a multi-part upload; returns a stream id. |
| `POST` | `/upload/sign-chunk` | Get a signed URL for the next chunk. |
| `GET`  | `/upload/stream-status` | Poll progress / part list. |
| `POST` | `/upload/complete-stream` | Finalize the multi-part upload. |
| `POST` | `/upload/abort-stream` | Discard a partial upload. |

### Downloads

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/download/<key>` | Session-authenticated download. |
| `GET` | `/download-with-ticket/<key>` | Ticket-authenticated download (used for pre-signed frontend links). |

### Utility

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/unique/<md5sum>` | Check whether a file with the given MD5 already exists — enables dedup on upload. |
| `DELETE` | `/delete/<key>` | Delete a single object. |
| `DELETE` | `/delete` | Delete multiple objects in one call. |
| `GET` | `/spec/dams-storage-api.json` | OpenAPI spec. |
| `GET` | `/spec/dams-csv-importer-events.html` | AsyncAPI spec for the RabbitMQ events. |
| `GET` | `/health` | Liveness probe. |

Full interactive docs when running locally: <http://storage-api.dams.localhost:8100/api/docs>.

## Layout

- `api/app.py` — Flask + Flask-RESTful bootstrap and route registration.
- `api/resources/` — resource classes matching the endpoints above (`upload.py`, `streamed_upload.py`, `download.py`, `delete.py`, `unique.py`, `spec.py`).
- `api/storage/` — S3 backend adapters.
  - `s3store.py` / `storagemanager.py` — standard single-shot S3 client.
  - `streamed_s3store.py` / `streamed_storagemanager.py` — multi-part / resumable upload client.
- `api/rabbit.py` — AMQP publisher for storage events (used by the CSV importer and others).
- `api/apps/app_list.json` — per-tenant app configuration.
- `docker/` — container build.
- `scripts/` — operational helpers.

## Local setup

The [elody-common](https://gitlab.inuits.io/rnd/inuits/elody/elody-common) repository ships the shared docker-compose stack that runs storage-api alongside MinIO, collection-api, cantaloupe, and the PWA. See its README for the full setup.

## Dependencies

Python 3, Flask, Flask-RESTful, `boto3` (S3), `pika` (RabbitMQ), Elody client library. Full pin list in `requirements.txt`.
