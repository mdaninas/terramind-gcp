"""Package only reviewed synthetic documents; catch drift before an image is built."""

import argparse
from pathlib import Path

from pydantic import TypeAdapter

from terramind.rag.contracts import Document
from terramind.rag.corpus import load_corpus


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path("src/terramind/events/assets/corpus.json")
    content = (
        TypeAdapter(tuple[Document, ...])
        .dump_json(
            load_corpus(Path("knowledge-base")),
            indent=2,
        )
        .decode()
        + "\n"
    )
    if args.check:
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            print("Packaged Eventarc corpus differs; run scripts/export_event_corpus.py")
            return 1
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
