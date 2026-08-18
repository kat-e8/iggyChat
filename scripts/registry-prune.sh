#!/usr/bin/env bash
# Prunes old iggychat-* image tags from the shared clubuntu registry.
#
# Scope is deliberately narrow: this script only ever touches repositories
# named iggychat-gateway, iggychat-chat-bridge, iggychat-frontend. The
# registry is shared with ~20 unrelated repositories from a different
# stack -- this must never enumerate or delete anything outside that
# fixed list.
#
# Keeps: the ":main" floating tag, the SHA of whatever's currently
# deployed (read from the running containers), and the last KEEP_COMMITS
# commits on main (from a dedicated bare clone kept in sync here, not the
# runner's own workspace, so a concurrent build/deploy job is never
# disturbed).
set -euo pipefail

REGISTRY=clubuntu.dala-cirius.ts.net:5000
SERVICES=(chat-bridge frontend)
KEEP_COMMITS=5
REPO_CLONE=~/.config/iggychat/repo-history/iggyChat.git

git --git-dir="$REPO_CLONE" fetch --quiet origin main:main
KEEP_SHAS=$(git --git-dir="$REPO_CLONE" log --format=%H -n "$KEEP_COMMITS" main)

for service in "${SERVICES[@]}"; do
  repo="iggychat-${service}"
  deployed_sha=""
  if docker inspect "iggychat-${service}" >/dev/null 2>&1; then
    deployed_sha=$(docker inspect "iggychat-${service}" \
      --format '{{.Config.Image}}' | sed -E 's/.*:([0-9a-f]{40})$/\1/')
  fi

  tags=$(curl -s "http://${REGISTRY}/v2/${repo}/tags/list" | \
    python3 -c 'import sys,json; print("\n".join(json.load(sys.stdin).get("tags") or []))')

  for tag in $tags; do
    # Only ever consider full 40-char git-sha tags for deletion -- never
    # "main" or anything else that doesn't look like one.
    if [[ ! "$tag" =~ ^[0-9a-f]{40}$ ]]; then
      continue
    fi
    if [[ "$tag" == "$deployed_sha" ]]; then
      continue
    fi
    if grep -q "^${tag}$" <<< "$KEEP_SHAS"; then
      continue
    fi

    digest=$(curl -sI \
      -H 'Accept: application/vnd.docker.distribution.manifest.v2+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.index.v1+json' \
      "http://${REGISTRY}/v2/${repo}/manifests/${tag}" | \
      grep -i '^docker-content-digest:' | tr -d '\r' | awk '{print $2}')

    if [[ -n "$digest" ]]; then
      echo "Deleting ${repo}:${tag} (${digest})"
      curl -s -X DELETE "http://${REGISTRY}/v2/${repo}/manifests/${digest}" -o /dev/null -w '  -> %{http_code}\n'
    fi
  done
done

echo "Running garbage-collect to reclaim disk space..."
docker exec registry bin/registry garbage-collect /etc/docker/registry/config.yml
