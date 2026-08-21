import argparse
import json
from pathlib import Path

from app.config import settings
from app.db import init_db
from app.ingest_pipeline import ingest_pdf
from app.retrieve import retrieve
from app.answer import generate_answer


def cmd_ingest(args: argparse.Namespace) -> None:
    settings.ensure_dirs()
    init_db(settings.db_path)
    result = ingest_pdf(Path(args.path), args.filename or Path(args.path).name)
    print(json.dumps(result, indent=2))


def cmd_ask(args: argparse.Namespace) -> None:
    init_db(settings.db_path)
    sources = retrieve(args.question, top_k=settings.top_k)
    if not sources:
        print("No documents ingested yet. Run `campusgpt ingest <pdf>` first.")
        return

    result = generate_answer(args.question, sources)

    if result.refused and result.closest_source:
        cs = result.closest_source
        print("Answer:", result.answer)
        print(f"\nClosest source: {cs.doc_name}, p.{cs.page}")
        print(f'  "{cs.passage}"')
        return

    print("Answer:", result.answer)
    for c in result.citations:
        print(f"  [{c.number}] {c.doc_name}, p.{c.page}")
        print(f'      "{c.passage}"')
    if result.warning:
        print(f"\n⚠️  {result.warning}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="campusgpt")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest a PDF document")
    p_ingest.add_argument("path", help="Path to the PDF file")
    p_ingest.add_argument("--filename", default=None, help="Saved filename (default: original name)")
    p_ingest.set_defaults(func=cmd_ingest)

    p_ask = sub.add_parser("ask", help="Ask a question against ingested documents")
    p_ask.add_argument("question", help="The question to ask")
    p_ask.set_defaults(func=cmd_ask)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
