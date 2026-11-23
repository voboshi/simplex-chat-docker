#!/bin/sh
set -eu
umask 077
# The upstream WebSocket server writes command payloads directly to stdout.
# Discard both streams before the process starts; exit status remains available.
exec /usr/local/bin/simplex-chat "$@" >/dev/null 2>&1
