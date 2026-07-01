#!/usr/bin/env python3
"""
Bundle the compiled tree.json into the browser data file the static explorer
loads (packages/web/static/tree-data.js), as `window.FINTREE_DATA = <json>;`.

This exists because the wrapping step used to be a manual shell command, and on
Windows that command read the UTF-8 tree.json as cp1252 and re-saved it — baking
mojibake (em-dashes → "â€”", minus signs → "âˆ’") into the shipped data. Doing it
here with explicit UTF-8 makes the step reproducible and encoding-safe.

Run `compile_tree.py` first to regenerate tree.json, then run this.
"""
import io
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # packages/data
TREE_JSON = BASE / "tree.json"
OUT = BASE.parent / "web" / "static" / "tree-data.js"

HEADER = "// Auto-generated from tree.json by build_web_data.py — do not edit by hand.\n"


def main() -> None:
    # Read as UTF-8 explicitly; never rely on the platform default (cp1252 on Windows).
    with io.open(TREE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEADER)
        f.write("window.FINTREE_DATA = ")
        f.write(payload)
        f.write(";\n")

    print(f"Wrote {OUT} ({len(payload):,} bytes of JSON, {len(data.get('nodes', []))} nodes)")


if __name__ == "__main__":
    main()
