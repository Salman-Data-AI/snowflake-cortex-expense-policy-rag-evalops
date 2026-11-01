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

from trulens.core.otel.instrument import instrument
from trulens.otel.semconv.trace import SpanAttributes

from app.rag_core import RagCore
from app.settings import get_session, load_config


class RagApp(RagCore):
    """RagCore with the Snowflake clients and TruLens spans (D-018).

    Every @instrument method here overrides a RagCore method of the same name and signature and
    delegates to super(); tests/test_rag_core.py checks this without importing TruLens.
    """

    def __init__(self, session=None, cfg: dict | None = None):
        cfg = cfg or load_config()
        self.session = session or get_session()
        db, schema, name = cfg["snowflake"]["search_service"].split(".")
        self._search_ref = (db, schema, name)
        self._search_service = None
        super().__init__(cfg, search=self.search, complete=self._complete)

    # ---------- Snowflake clients ----------

    def _service(self):
        if self._search_service is None:
            from snowflake.core import Root

            db, schema, name = self._search_ref
            self._search_service = (
                Root(self.session).databases[db].schemas[schema].cortex_search_services[name]
            )
        return self._search_service

    def search(self, question: str, top_k: int) -> list[dict]:
        """Top-k chunks with their metadata. Not instrumented; retrieve() wraps it."""
        resp = self._service().search(
            query=question,
            columns=["chunk_text", "chunk_id", "file_name", "page_number", "section"],
            limit=top_k,
        )
        return json.loads(resp.to_json())["results"]  # VERIFY: response shape

    def _complete(self, model: str, prompt: str) -> str:
        row = self.session.sql(
            "SELECT AI_COMPLETE(?, ?) AS answer",  # VERIFY: AI_COMPLETE(model, prompt) + qmark binding
            params=[model, prompt],
        ).collect()[0]
        return str(row["ANSWER"]).strip()

    # ---------- instrumented steps (logic in RagCore) ----------
    # VERIFY: TruLens still emits the RETRIEVAL/GENERATION spans when the instrumented override
    #         delegates to super() and RagCore.ask() calls it through self.

    @instrument(
        span_type=SpanAttributes.SpanType.RETRIEVAL,
        attributes={
            SpanAttributes.RETRIEVAL.QUERY_TEXT: "question",
            SpanAttributes.RETRIEVAL.RETRIEVED_CONTEXTS: "return",
        },
    )
    def retrieve(self, question: str) -> list[str]:
        """Retrieved context as labelled strings; the labels are what the model cites."""
        return super().retrieve(question)

    @instrument(span_type=SpanAttributes.SpanType.GENERATION)
    def generate(self, question: str, contexts: list[str]) -> str:
        return super().generate(question, contexts)

    # ---------- entry points ----------
    # ask() is inherited from RagCore: it is not instrumented.

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
