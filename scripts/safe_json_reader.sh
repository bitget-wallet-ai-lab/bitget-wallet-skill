#!/bin/bash
# Helper script to safely read JSON files
# Usage: ./safe_json_reader.sh <json_file> <field_path>
# Example: ./safe_json_reader.sh quote.json "data.toAmount"

json_file=$1
field_path=$2

python3 << 'EOF'
import json
import sys

json_file = sys.argv[1] if len(sys.argv) > 1 else "quote.json"
field_path = sys.argv[2] if len(sys.argv) > 2 else "data"

try:
    with open(json_file, 'r') as f:
        data = json.load(f)

    # Supports nested field access, e.g. "data.toAmount"
    fields = field_path.split('.')
    result = data
    for field in fields:
        result = result[field]

    print(result)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
