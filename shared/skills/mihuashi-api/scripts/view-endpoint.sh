#!/usr/bin/env bash
# View full parameter structure of a specific API endpoint
# Usage: ./view-endpoint.sh <path> [api-group]
#   path: e.g. /api/v1/projects
#   api-group: site (default), admin, activity, wc2, wc3

path="${1:-/api/v1/projects}"
group="${2:-site}"

case "$group" in
  site)     url="https://test.mihuashi.com/api/v1/swagger_doc" ;;
  admin)    url="https://test.mihuashi.com/api/admin/v1/swagger_doc" ;;
  activity) url="https://test.mihuashi.com/api/activity/v1/swagger_doc" ;;
  wc2)      url="https://test.mihuashi.com/api/wc2/v1/swagger_doc" ;;
  wc3)      url="https://test.mihuashi.com/api/wc3/v1/swagger_doc" ;;
  *)        echo "Unknown group: $group"; exit 1 ;;
esac

curl -s "$url" | python3 -c "
import json, sys
doc = json.load(sys.stdin)
path = '$path'
if path in doc.get('paths', {}):
    print(json.dumps(doc['paths'][path], indent=2, ensure_ascii=False))
else:
    print(f'Path not found: {path}')
"