#!/usr/bin/env bash
# Re-create the Neo4j Docker container on the EC2 host WITH the GDS plugin.
# Run this INSIDE an SSM shell on the Neo4j instance (data volume is preserved).
#
# From your laptop:
#   aws sso login --profile sandbox
#   aws ssm start-session --profile sandbox --region eu-west-2 \
#     --target i-035096cd4a6feac5a
#
# On the EC2 instance, paste the docker block below (set NEO4J_PASSWORD first).

set -euo pipefail

: "${NEO4J_PASSWORD:?Set NEO4J_PASSWORD to the value from terraform.tfvars}"

HEAP="${NEO4J_HEAP_SIZE:-4g}"
PAGECACHE="${NEO4J_PAGECACHE_SIZE:-9g}"
IMAGE="${NEO4J_IMAGE:-neo4j:5}"

docker stop neo4j 2>/dev/null || true
docker rm neo4j 2>/dev/null || true

docker run -d --name neo4j --restart unless-stopped \
  -p 7687:7687 -p 7474:7474 \
  -v /mnt/neo4j/data:/data \
  -v /mnt/neo4j/logs:/logs \
  -e "NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}" \
  -e 'NEO4J_PLUGINS=["graph-data-science"]' \
  -e "NEO4J_server_memory_heap_initial__size=${HEAP}" \
  -e "NEO4J_server_memory_heap_max__size=${HEAP}" \
  -e "NEO4J_server_memory_pagecache_size=${PAGECACHE}" \
  -e 'NEO4J_server_default__listen__address=0.0.0.0' \
  "${IMAGE}"

echo "Waiting for Neo4j to start..."
for _ in $(seq 1 60); do
  if docker exec neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
    "RETURN gds.version() AS v" 2>/dev/null | grep -q gds; then
    echo "GDS is available."
    docker exec neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
      "RETURN gds.version() AS v"
    exit 0
  fi
  sleep 5
done

echo "Neo4j started but GDS check timed out — inspect: docker logs neo4j" >&2
exit 1
