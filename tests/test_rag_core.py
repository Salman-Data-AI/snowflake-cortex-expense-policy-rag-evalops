"""ask() with a fake retriever and a fake LLM. Needs neither TruLens nor Snowflake (CI has neither)."""

import ast
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

from app.citations import label
from app.rag_core import RagCore
from app.settings import load_config

ROOT = Path(__file__).resolve().parent.parent
QUESTION = "Do I need a receipt for a $60 hotel parking charge?"
HITS = [
    {"chunk_id": "g28.pdf#p12#0", "file_name": "g28_travel_regulations.pdf", "page_number": 12,
     "section": "Receipts", "chunk_text": "Receipts are required for lodging."},
    {"chunk_id": "bus79.pdf#p3#4", "file_name": "bus79_business_meetings_entertainment.pdf",
     "page_number": 3, "section": "", "chunk_text": "Entertainment needs a business purpose."},
    {"chunk_id": "g28.pdf#p2#1", "file_name": "g28_travel_regulations.pdf", "page_number": 2,
     "section": "Parking", "chunk_text": "Parking over $75 needs a receipt."},
]


class FakeRetriever:
    def __init__(self, hits):
        self.hits, self.calls = hits, []

    def __call__(self, question, top_k):
        self.calls.append((question, top_k))
        return [dict(h) for h in self.hits]


class FakeLLM:
    def __init__(self, answer="Canned answer [g28_travel_regulations.pdf p.12]"):
        self.answer, self.calls = answer, []

    def __call__(self, model, prompt):
        self.calls.append((model, prompt))
        return self.answer


@pytest.fixture
def cfg():
    return load_config()


def _run(cfg, hits):
    search, llm = FakeRetriever(hits), FakeLLM()
    result = RagCore(cfg, search=search, complete=llm).ask(QUESTION)
    return result, search, llm


def _template(cfg):
    return (ROOT / "app" / f"prompt_{cfg['prompt_version']}.txt").read_text(encoding="utf-8")


def test_retriever_gets_question_and_top_k_from_config(cfg):
    _, search, _ = _run(cfg, HITS)
    assert search.calls == [(QUESTION, cfg["top_k"])]


def test_prompt_built_from_prompt_version_file(cfg):
    _, _, llm = _run(cfg, HITS)
    assert len(llm.calls) == 1
    model, prompt = llm.calls[0]
    contexts = [label(h) + "\n" + h["chunk_text"] for h in HITS]
    assert prompt == _template(cfg).format(context="\n\n---\n\n".join(contexts), question=QUESTION)
    assert QUESTION in prompt
    for h in HITS:
        assert h["chunk_text"] in prompt
        assert label(h) + "\n" + h["chunk_text"] in prompt
    assert "[g28_travel_regulations.pdf p.12]\nReceipts are required" in prompt  # literal label format


def test_model_from_config_reaches_llm(cfg):
    result, _, llm = _run(cfg, HITS)
    assert llm.calls[0][0] == cfg["model"]
    assert result["model"] == cfg["model"]


def test_result_sources_match_hits_in_order(cfg):
    result, _, llm = _run(cfg, HITS)
    assert result["answer"] == llm.answer
    assert result["question"] == QUESTION
    assert result["sources"] == [
        {k: h[k] for k in ("chunk_id", "file_name", "page_number", "section")} for h in HITS
    ]
    assert [label(s) for s in result["sources"]] == [label(h) for h in HITS]
    assert (result["top_k"], result["prompt_version"]) == (cfg["top_k"], cfg["prompt_version"])
    assert isinstance(result["latency_ms"], int)


def test_empty_retrieval_still_calls_llm(cfg):
    """Current behaviour: no hits -> the LLM is still called once with an empty excerpts section."""
    result, search, llm = _run(cfg, [])
    assert search.calls == [(QUESTION, cfg["top_k"])]
    assert len(llm.calls) == 1
    assert llm.calls[0][1] == _template(cfg).format(context="", question=QUESTION)
    assert "Policy excerpts:\n\n\nQuestion:" in llm.calls[0][1]
    assert result["sources"] == []
    assert result["answer"] == llm.answer


# ---------- instrumentation guard (reads app/ask.py's source; never imports TruLens) ----------


def _class(path: str, name: str) -> ast.ClassDef:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)


def _methods(cls: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}


def _is_instrument(dec: ast.expr) -> bool:
    target = dec.func if isinstance(dec, ast.Call) else dec
    return (isinstance(target, ast.Name) and target.id == "instrument") or (
        isinstance(target, ast.Attribute) and target.attr == "instrument"
    )


def _self_calls(func: ast.FunctionDef, receiver: str) -> set[str]:
    """Method names called as self.<name>(...) (receiver 'self') or super().<name>(...) ('super')."""
    names = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            obj = node.func.value
            if receiver == "self" and isinstance(obj, ast.Name) and obj.id == "self":
                names.add(node.func.attr)
            if (receiver == "super" and isinstance(obj, ast.Call)
                    and isinstance(obj.func, ast.Name) and obj.func.id == "super"):
                names.add(node.func.attr)
    return names


def test_instrumented_methods_are_overridden_and_called_from_ask():
    rag_app = _class("app/ask.py", "RagApp")
    assert [b.id for b in rag_app.bases if isinstance(b, ast.Name)] == ["RagCore"]
    app_methods = _methods(rag_app)
    decorated = {name for name, f in app_methods.items() if any(map(_is_instrument, f.decorator_list))}
    # The spans in place before the RagCore split (D-018); losing one silently drops a TruLens metric input.
    assert decorated >= {"retrieve", "generate"}, f"@instrument missing; found {sorted(decorated)}"
    # Every module-level or other-class use of @instrument must be on RagApp too.
    all_decorated = {
        n.name for n in ast.walk(ast.parse((ROOT / "app/ask.py").read_text(encoding="utf-8")))
        if isinstance(n, ast.FunctionDef) and any(map(_is_instrument, n.decorator_list))
    }
    assert all_decorated == decorated

    called_from_ask = _self_calls(_methods(_class("app/rag_core.py", "RagCore"))["ask"], "self")
    for name in sorted(decorated):
        func = app_methods[name]  # defined in RagApp's own body: overridden, not inherited
        core = getattr(RagCore, name, None)
        assert callable(core), f"RagApp.{name} is instrumented but RagCore has no {name}()"
        assert [a.arg for a in func.args.args] == list(inspect.signature(core).parameters), name
        assert name == "ask" or name in called_from_ask, f"RagCore.ask() never calls self.{name}()"
        assert name in _self_calls(func, "super"), f"RagApp.{name} does not delegate to super().{name}()"


def test_rag_app_passes_its_snowflake_clients_to_rag_core():
    """RagApp.__init__ wires search=self.search, complete=self._complete (only exercised on Snowflake)."""
    init = _methods(_class("app/ask.py", "RagApp"))["__init__"]
    call = next(
        n for n in ast.walk(init)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "__init__"
    )
    wired = {k.arg: ast.unparse(k.value) for k in call.keywords}
    assert wired == {"search": "self.search", "complete": "self._complete"}
    assert list(inspect.signature(RagCore.__init__).parameters) == ["self", "cfg", "search", "complete"]


def test_pure_modules_import_no_trulens_snowflake_or_pandas():
    # Compare with the modules loaded at startup: snowflake-snowpark's -nspkg.pth pre-creates an empty
    # "snowflake" namespace module in venvs where it is installed.
    code = (
        "import sys\n"
        "before = set(sys.modules)\n"
        "import app.citations, app.rag_core, pipeline.parsed_doc\n"
        "new = set(sys.modules) - before\n"
        "bad = sorted(m for m in new if m.split('.')[0] in ('trulens', 'snowflake', 'pandas'))\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)
