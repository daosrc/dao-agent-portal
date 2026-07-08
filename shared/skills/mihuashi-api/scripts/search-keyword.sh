#!/usr/bin/env bash
# Search API paths by keyword in the live Swagger JSON
# Usage: ./search-keyword.sh <keyword> [api-group]
#   api-group: site (default), admin, activity, wc2, wc3

kw="${1:-stall}"
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
kw = '$kw'
for path, methods in sorted(doc.get('paths', {}).items()):
    if kw in path:
        for m, op in methods.items():
            if m in ('get','post','put','patch','delete'):
                print(f'{m.upper():<7} {path}')
                desc = op.get('description','').strip()
                if desc: print(f'        {desc}')
"