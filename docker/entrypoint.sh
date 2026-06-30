#!/bin/sh
set -eu

is_enabled() {
    value="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
    [ "$value" = "1" ] || [ "$value" = "true" ] || [ "$value" = "yes" ] || [ "$value" = "on" ]
}

if is_enabled "${RUN_MIGRATIONS:-true}"; then
    attempt=1
    max_attempts="${DATABASE_WAIT_ATTEMPTS:-30}"
    until python manage.py migrate --noinput; do
        if [ "$attempt" -ge "$max_attempts" ]; then
            echo "Database migration failed after ${max_attempts} attempts." >&2
            exit 1
        fi
        echo "Database unavailable; retrying migration (${attempt}/${max_attempts})..." >&2
        attempt=$((attempt + 1))
        sleep 2
    done
fi

if is_enabled "${COLLECT_STATIC:-true}"; then
    python manage.py collectstatic --noinput --clear
fi

exec "$@"
