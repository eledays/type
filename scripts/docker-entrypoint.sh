#!/bin/sh
set -eu

if [ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ]; then
    case "$PROMETHEUS_MULTIPROC_DIR" in
        /tmp/prometheus|/tmp/prometheus-*) ;;
        *)
            echo "PROMETHEUS_MULTIPROC_DIR must be under /tmp/prometheus" >&2
            exit 1
            ;;
    esac
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
    find "$PROMETHEUS_MULTIPROC_DIR" -type f -delete
fi

exec "$@"
