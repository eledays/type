#!/bin/sh
set -eu

flask --app app db upgrade

exec "$@"
