#!/usr/bin/env python3
"""
Generic JSON pretty-print and field extraction tool.
Avoids shell parsing issues.

Usage:
  python3 scripts/json_tool.py <file> [--field <path>] [--pretty]

Examples:
  python3 scripts/json_tool.py quote.json --pretty
  python3 scripts/json_tool.py quote.json --field data.toAmount
  python3 scripts/json_tool.py quote.json --field data.tokenInfo.1.price
"""

import json
import sys
import argparse

def get_nested_field(data, path):
    """Get nested field; supports data.tokenInfo.1.price style paths"""
    fields = path.split('.')
    result = data
    for field in fields:
        if field.isdigit():
            result = result[int(field)]
        else:
            result = result[field]
    return result

def main():
    parser = argparse.ArgumentParser(description='JSON tool - pretty-print and field extraction')
    parser.add_argument('file', help='JSON file path')
    parser.add_argument('--field', '-f', help='Extract field (nested, e.g. data.toAmount)')
    parser.add_argument('--pretty', '-p', action='store_true', help='Pretty-print output')

    args = parser.parse_args()

    try:
        with open(args.file, 'r') as f:
            data = json.load(f)

        if args.field:
            result = get_nested_field(data, args.field)
            if isinstance(result, (dict, list)):
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(result)
        elif args.pretty:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(data, ensure_ascii=False))

    except FileNotFoundError:
        print(f"Error: file '{args.file}' not found", file=sys.stderr)
        sys.exit(1)
    except KeyError as e:
        print(f"Error: field {e} not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: JSON parse failed - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
