"""Classify saved Home Appliances product files without network or DB access."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import os
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.home_appliances_files import InputError, SOURCE_FORMATS, classify_input, csv_bytes, load_inputs


def main(argv=None):
    parser = argparse.ArgumentParser(description="保存済みHome Appliancesを候補分類し、BOM付きCSVへ出力します。")
    parser.add_argument("--input", type=Path, nargs="+", required=True, help="保存済みJSON／JSONL（複数指定可）")
    parser.add_argument("--source-format", choices=SOURCE_FORMATS, required=True)
    parser.add_argument("--output", type=Path, required=True, help="新しい出力CSVの名前（上書き不可）")
    args = parser.parse_args(argv)
    try:
        if args.output.resolve() in {p.resolve() for p in args.input}:
            raise InputError("OUTPUT_IS_INPUT")
        if args.output.suffix.lower() != ".csv":
            raise InputError("OUTPUT_MUST_BE_CSV")
        if args.output.exists():
            raise InputError("OUTPUT_ALREADY_EXISTS")
        items = load_inputs(args.input, source_format=args.source_format)
        encoded = csv_bytes(items)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=args.output.parent, prefix=".home-appliances-", delete=False) as output:
                temporary = Path(output.name)
                output.write(encoded)
            # Atomically publish complete bytes; hard-link creation refuses any
            # existing destination, including a concurrent writer's output.
            os.link(temporary, args.output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except (InputError, OSError) as exc:
        code = str(exc) if isinstance(exc, InputError) else "FILE_OPERATION_FAILED"
        print(f"分類を停止しました: {code}。入力形式と新しい出力先を確認してください。", file=sys.stderr)
        return 2
    counts = Counter(classify_input(item).letter for item in items)
    print(f"CSV出力完了: {len(items)}商品 / A={counts['A']} B={counts['B']} C={counts['C']}。候補分類であり出品許可ではありません。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
