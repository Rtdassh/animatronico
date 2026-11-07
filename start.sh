#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/server_pc"
exec python3 run_server.py "$@"

