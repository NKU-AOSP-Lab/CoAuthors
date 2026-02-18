# Operations

## Deployment Patterns

1. Standalone: CoAuthors + bundled `DblpService`
2. Shared backend: multiple frontends against one DblpService

## Upgrade Steps

1. Upgrade DblpService and verify `/api/health`
2. Upgrade CoAuthors frontend
3. Validate query flow, cache writes, and telemetry

## Backup Guidance

- Back up `runtime.sqlite` regularly
- Treat runtime DB as cache/telemetry storage, not source-of-truth business data

## Monitoring Checklist

- Frontend availability (`GET /`)
- Backend connectivity (`GET /api/health`)
- Query error rate (`query_events` where `success=0`)
