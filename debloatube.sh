#!/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/debloatube/bin/activate"
exec python3 "$SCRIPT_DIR/main.py"
