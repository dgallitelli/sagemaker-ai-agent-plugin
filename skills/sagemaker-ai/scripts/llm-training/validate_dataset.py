#!/usr/bin/env python3
"""Validate common SFT/DPO/CPT jsonl dataset schemas (local file).

Usage:
  python scripts/llm-training/validate_dataset.py dataset.jsonl --schema sft
  python scripts/llm-training/validate_dataset.py dataset.jsonl --schema dpo
  python scripts/llm-training/validate_dataset.py dataset.jsonl --schema cpt
"""
import argparse, json
from pathlib import Path

SCHEMAS = {
    "sft": {
        "conversational": {"messages"},  # Recommended: [{"role": "...", "content": "..."}]
        "simple": {"prompt", "completion"},
    },
    "dpo": {
        "required": {"prompt", "chosen", "rejected"},
    },
    "cpt": {
        "required": {"text"},
    },
}

def validate_sft_record(obj):
    """Returns (valid, format_type) for SFT records."""
    if "messages" in obj:
        msgs = obj["messages"]
        if isinstance(msgs, list) and len(msgs) > 0:
            if all(isinstance(m, dict) and "role" in m and "content" in m for m in msgs):
                return True, "conversational"
        return False, "invalid_messages"
    elif "prompt" in obj and "completion" in obj:
        return True, "prompt_completion"
    return False, "missing_keys"

def validate_dpo_record(obj):
    """Returns (valid, issue) for DPO records."""
    required = {"prompt", "chosen", "rejected"}
    if required.issubset(obj.keys()):
        return True, None
    return False, f"missing: {required - set(obj.keys())}"

def validate_cpt_record(obj):
    """Returns (valid, issue) for CPT records."""
    if "text" in obj:
        return True, None
    return False, "missing: text"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("path", help="Path to JSONL file")
    p.add_argument("--schema", choices=["sft", "dpo", "cpt"], default="sft")
    p.add_argument("--max", type=int, default=2000, help="Max records to scan")
    args = p.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}")
        return 1

    validators = {
        "sft": validate_sft_record,
        "dpo": validate_dpo_record,
        "cpt": validate_cpt_record,
    }
    validate = validators[args.schema]

    n = 0
    valid = 0
    invalid = 0
    formats = {}  # Track format distribution for SFT

    for line in path.open("r", encoding="utf-8", errors="ignore"):
        if n >= args.max:
            break
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON on line {n+1}: {e}")
            return 2

        if args.schema == "sft":
            is_valid, fmt = validate(obj)
            if is_valid:
                valid += 1
                formats[fmt] = formats.get(fmt, 0) + 1
            else:
                invalid += 1
                if invalid <= 3:
                    print(f"  Record {n+1}: {fmt}")
        else:
            is_valid, issue = validate(obj)
            if is_valid:
                valid += 1
            else:
                invalid += 1
                if invalid <= 3:
                    print(f"  Record {n+1}: {issue}")
        n += 1

    print(f"\nSchema: {args.schema.upper()}")
    print(f"Scanned: {n} records")
    print(f"Valid: {valid}")
    print(f"Invalid: {invalid}")

    if args.schema == "sft" and formats:
        print(f"\nFormat distribution:")
        for fmt, count in sorted(formats.items()):
            print(f"  {fmt}: {count}")

    if invalid > 0:
        print("\n⚠️  Some records have issues. Fix before training.")
        return 1
    else:
        print("\n✓ All records valid!")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
