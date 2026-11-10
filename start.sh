#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/server_pc"
if [ -f ".venv/bin/python" ]; then
    exec .venv/bin/python run_server.py "$@"
else
    exec python3 run_server.py "$@"
fi


