#!/bin/sh
set -eu
runtime="simplex-chat:test"
peer="simplex-chat:smoke"
if [ "$#" -gt 0 ]; then runtime="$1"; fi
if [ "$#" -gt 1 ]; then peer="$2"; fi
suffix="$(date +%s)-$$"
name="simplex-test-$suffix"
network="simplex-test-net-$suffix"
volume="simplex-test-data-$suffix"
cleanup() {
    docker rm -f "$name" >/dev/null 2>&1 || :
    docker volume rm "$volume" >/dev/null 2>&1 || :
    docker network rm "$network" >/dev/null 2>&1 || :
}
trap cleanup EXIT HUP INT TERM
docker network create "$network" >/dev/null
docker volume create "$volume" >/dev/null
start() {
    docker run -d --name "$name" --network "$network" --network-alias simplex-test \
      --read-only --cap-drop ALL --security-opt no-new-privileges \
      --pids-limit 128 --log-driver none \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777 \
      --mount "type=volume,source=$volume,target=/data" "$runtime" >/dev/null
    test "$(docker inspect -f '{{.Config.User}}' "$name")" = "10001:10001"
    test "$(docker inspect -f '{{len .HostConfig.PortBindings}}' "$name")" = 0
    test "$(docker inspect -f '{{.HostConfig.LogConfig.Type}}' "$name")" = none
    test -z "$(docker inspect -f '{{.LogPath}}' "$name")"
}
check() {
    docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges \
      --network "container:$name" "$peer" "$1"
}
start
check write
docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges \
  --network "$network" "$peer" unreachable simplex-test
docker stop --time 30 "$name" >/dev/null
docker rm "$name" >/dev/null
start
check read
test "$(docker exec "$name" id -u)" = 10001
printf '%s\n' 'Boot, loopback boundary, separate peer, persistence and runtime restrictions passed.'
