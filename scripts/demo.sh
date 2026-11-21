#!/bin/bash
# Record docs/images/demo.gif with VHS in a container.
# Usage: scripts/demo.sh SERVER ME FRIEND
# SERVER has the url (and tmdb_key). ME and FRIEND have the token of two Plex users.
# scripts/demo.tape changes the tracks of these users on the server. See the demo-gif skill.

set -e

if [ $# -ne 3 ]; then
    echo "Usage: $0 SERVER ME FRIEND" >&2
    exit 2
fi
for f in "$@"; do
    [ -f "$f" ] || { echo "$f: file not found" >&2; exit 2; }
done

# Git Bash: do not change the container paths into Windows paths
export MSYS_NO_PATHCONV=1

abs() { (cd "$(dirname "$1")" && echo "$(pwd -W 2>/dev/null || pwd)/$(basename "$1")"); }
repo=$(pwd -W 2>/dev/null || pwd)
engine=$(command -v podman || command -v docker)
# Podman on WSL: crun fails with "controller `pids` is not available". The demo needs no cgroup limits.
run_args=()
if [[ "$engine" == *podman* ]]; then run_args=(--cgroups=disabled); fi

"$engine" build -q -t localhost/plexy:latest .
"$engine" build -q -t localhost/plexy-vhs -f scripts/demo.Dockerfile .
"$engine" run --rm "${run_args[@]}" \
    -v "$(abs "$1"):/root/.config/plexy/config.yml:ro" \
    -v "$(abs "$2"):/demo/me.yml:ro" \
    -v "$(abs "$3"):/demo/friend.yml:ro" \
    -v "$repo:/repo" -w /repo \
    localhost/plexy-vhs scripts/demo.tape
