"""The RAG logic without TruLens or Snowflake: retrieve, build the prompt, generate.

RagCore takes its search and LLM clients as callables, so tests can pass fakes. app/ask.py's RagApp
subclasses it, supplies the Cortex Search and AI_COMPLETE clients, and adds TruLens instrumentation
by overriding retrieve() and generate() (D-018). ask() calls self.retrieve / self.generate, so on a
RagApp those calls go through the instrumented overrides.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from app.citations import label
from app.settings import REPO_ROOT, load_config

SearchFn = Callable[[str, int], list[dict]]  # (question, top_k) -> hits
CompleteFn = Callable[[str, str], str]  # (model, prompt) -> answer text


class RagCore:
    def __init__(self, cfg: dict | None, search: SearchFn, complete: CompleteFn):
        self.cfg = cfg or load_config()
        self._search_fn = search
        self._complete_fn = complete
        self.prompt_template = (
            REPO_ROOT / "app" / f"prompt_{self.cfg['prompt_version']}.txt"
        ).read_text(encoding="utf-8")

    def retrieve(self, question: str) -> list[str]:
        """Retrieved context as labelled strings; the labels are what the model cites."""
        self._last_hits = self._search_fn(question, self.cfg["top_k"])
        return [label(h) + "\n" + h["chunk_text"] for h in self._last_hits]

    def generate(self, question: str, contexts: list[str]) -> str:
        prompt = self.prompt_template.format(
            context="\n\n---\n\n".join(contexts), question=question
        )
        return self._complete_fn(self.cfg["model"], prompt)

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
