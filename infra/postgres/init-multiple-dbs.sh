#!/bin/bash
set -e
set -u

function create_database() {
    local database=$1
    echo "Creating database '$database' if not exists..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        SELECT 'CREATE DATABASE $database'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$database')\gexec
        GRANT ALL PRIVILEGES ON DATABASE $database TO $POSTGRES_USER;
EOSQL
}

if [ -n "${ADDITIONAL_POSTGRES_DBS:-}" ]; then
    echo "Multiple databases requested: $ADDITIONAL_POSTGRES_DBS"
    for db in $(echo $ADDITIONAL_POSTGRES_DBS | tr ',' ' '); do
        create_database $db
    done
    echo "Additional databases created successfully."
fi

