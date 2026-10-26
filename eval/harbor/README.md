# Harbor (Phase 4)

Empty on purpose. Phase 4 adds a small adapter here that calls `RagApp().ask(question)` and one
Harbor task per row of `eval/questions.csv`, so Harbor and TruLens score the same app on the same questions.

Before starting: confirm with the team which Harbor they use. The public Harbor framework
(https://mintlify.com/harbor-framework/harbor) is the working assumption.

Planned files:
- `adapter.py`: wraps `app.ask.RagApp.ask` in whatever interface Harbor's agent expects.
- `make_tasks.py`: writes one task per question from `eval/questions.csv`.
- `compare.md`: Harbor's result for the current best settings next to `EVAL_RESULTS`.
