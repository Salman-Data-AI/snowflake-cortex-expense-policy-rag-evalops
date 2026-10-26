"""The RAG app: Cortex Search retrieval + one AI_COMPLETE call.

    from app.ask import RagApp
    rag = RagApp()
    result = rag.ask("Do I need a receipt for a $60 hotel parking charge?")
    result["answer"], result["sources"]

Try it from the repo root:  PYTHONPATH=. python -m app.ask "your question"

TruLens instrumentation:
- retrieve()  -> RETRIEVAL span (query text + retrieved chunk texts, for context relevance)
- generate()  -> GENERATION span
- answer()    -> RECORD_ROOT span via TruApp(main_method=...) (question in, answer string out,
                 for answer relevance, groundedness and correctness).
"""

from __future__ import annotations

import json
import sys
import time

from trulens.core.otel.instrument import instrument
from trulens.otel.semconv.trace import SpanAttributes

from app.settings import REPO_ROOT, get_session, load_config


class RagApp:
    def __init__(self, session=None, cfg: dict | None = None):
        self.cfg = cfg or load_config()
        self.session = session or get_session()
        self.prompt_template = (
            REPO_ROOT / "app" / f"prompt_{self.cfg['prompt_version']}.txt"
        ).read_text(encoding="utf-8")
        db, schema, name = self.cfg["snowflake"]["search_service"].split(".")
        self._search_ref = (db, schema, name)
        self._search_service = None

    # ---------- retrieval ----------

    def _service(self):
        if self._search_service is None:
            from snowflake.core import Root

            db, schema, name = self._search_ref
            self._search_service = (
                Root(self.session).databases[db].schemas[schema].cortex_search_services[name]
            )
        return self._search_service

    def search(self, question: str) -> list[dict]:
        """Top-k chunks with their metadata. Not instrumented; retrieve() wraps it."""
        resp = self._service().search(
            query=question,
            columns=["chunk_text", "chunk_id", "file_name", "page_number", "section"],
            limit=self.cfg["top_k"],
        )
        return json.loads(resp.to_json())["results"]  # VERIFY: response shape

    @instrument(
        span_type=SpanAttributes.SpanType.RETRIEVAL,
        attributes={
            SpanAttributes.RETRIEVAL.QUERY_TEXT: "question",
            SpanAttributes.RETRIEVAL.RETRIEVED_CONTEXTS: "return",
        },
    )
    def retrieve(self, question: str) -> list[str]:
        """Retrieved context as labelled strings; the labels are what the model cites."""
        self._last_hits = self.search(question)
        return [self._label(h) + "\n" + h["chunk_text"] for h in self._last_hits]

    @staticmethod
    def _label(hit: dict) -> str:
        return f"[{hit['file_name']} p.{hit['page_number']}]"

    # ---------- generation ----------

    @instrument(span_type=SpanAttributes.SpanType.GENERATION)
    def generate(self, question: str, contexts: list[str]) -> str:
        prompt = self.prompt_template.format(
            context="\n\n---\n\n".join(contexts), question=question
        )
        row = self.session.sql(
            "SELECT AI_COMPLETE(?, ?) AS answer",  # VERIFY: AI_COMPLETE(model, prompt) + qmark binding
            params=[self.cfg["model"], prompt],
        ).collect()[0]
        return str(row["ANSWER"]).strip()

    # ---------- entry points ----------

    def ask(self, question: str) -> dict:
        """Answer plus sources and timing, for people and for Harbor."""
        t0 = time.perf_counter()
        contexts = self.retrieve(question)
        answer = self.generate(question, contexts)
        return {
            "question": question,
            "answer": answer,
            "sources": [
                {
                    "chunk_id": h["chunk_id"],
                    "file_name": h["file_name"],
                    "page_number": h["page_number"],
                    "section": h.get("section", ""),
                }
                for h in self._last_hits
            ],
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "model": self.cfg["model"],
            "prompt_version": self.cfg["prompt_version"],
            "top_k": self.cfg["top_k"],
        }

    def answer(self, question: str) -> str:
        """What TruLens calls for each test question.

        Not decorated: run_eval.py passes it to TruApp as main_method, which makes it the
        RECORD_ROOT span (trulens 2.15 refuses an explicit RECORD_ROOT span_type and logs
        "Cannot explicitly set 'record_root' span type").
        """
        return self.ask(question)["answer"]


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "When is a receipt required for a travel expense?"
    result = RagApp().ask(q)
    print(result["answer"])
    print()
    for s in result["sources"]:
        print(f"  - {s['file_name']} p.{s['page_number']}  {s['section']}")
    print(f"\n{result['latency_ms']} ms")
