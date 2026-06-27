#!/bin/bash
set -euo pipefail

PRIMARY_HOST="${POSTGRES_PRIMARY_HOST:-postgres-primary}"
PRIMARY_PORT="${POSTGRES_PRIMARY_PORT:-5432}"
REPLICATION_USER="${POSTGRES_REPLICATION_USER:-replicator}"
REPLICATION_PASSWORD="${POSTGRES_PASSWORD}"

until pg_isready -h "$PRIMARY_HOST" -p "$PRIMARY_PORT" -U "$POSTGRES_USER"; do
  echo "Waiting for primary database..."
  sleep 2
done

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "Initialising replica from primary..."
  rm -rf "$PGDATA"/*
  PGPASSWORD="$REPLICATION_PASSWORD" pg_basebackup \
    -h "$PRIMARY_HOST" \
    -p "$PRIMARY_PORT" \
    -U "$REPLICATION_USER" \
    -D "$PGDATA" \
    -Fp \
    -Xs \
    -P \
    -R
fi

exec docker-entrypoint.sh postgres
