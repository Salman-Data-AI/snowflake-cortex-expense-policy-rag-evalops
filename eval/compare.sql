-- Compare evaluation runs. Every row in EVAL_RESULTS carries its settings and commit,
-- so any score can be traced back to exactly what produced it.
-- Set the two runs to compare (RUN_ID values from query 1):
SET run_a = 'REPLACE_WITH_OLDER_RUN_ID';
SET run_b = 'REPLACE_WITH_NEWER_RUN_ID';

-- 1. Average score per metric per run, newest first.
SELECT
    run_id,
    app_version,
    top_k,
    chunk_size,
    overlap,
    model,
    prompt_version,
    metric,
    ROUND(AVG(score), 3) AS avg_score,
    COUNT(*) AS n_questions,
    MIN(recorded_at) AS recorded_at
FROM RAG_STARTER.EVAL.EVAL_RESULTS
GROUP BY ALL
ORDER BY recorded_at DESC, metric ASC;

-- 2. Best run per metric.
SELECT
    metric,
    run_id,
    app_version,
    avg_score
FROM (
    SELECT
        metric,
        run_id,
        app_version,
        AVG(score) AS avg_score
    FROM RAG_STARTER.EVAL.EVAL_RESULTS
    GROUP BY ALL
) AS per_run
QUALIFY ROW_NUMBER() OVER (PARTITION BY metric ORDER BY avg_score DESC) = 1
ORDER BY metric;

-- 3. Two runs side by side, per metric.
SELECT
    metric,
    ROUND(AVG(IFF(run_id = $run_a, score, NULL)), 3) AS run_a,
    ROUND(AVG(IFF(run_id = $run_b, score, NULL)), 3) AS run_b,
    ROUND(run_b - run_a, 3) AS change
FROM RAG_STARTER.EVAL.EVAL_RESULTS
WHERE run_id IN ($run_a, $run_b)
GROUP BY metric
ORDER BY metric;

-- 4. Questions whose score dropped from run A to run B.
SELECT
    a.question_id,
    q.question,
    a.metric,
    a.score AS score_a,
    b.score AS score_b,
    ROUND(b.score - a.score, 3) AS change,
    b.answer AS answer_b
FROM RAG_STARTER.EVAL.EVAL_RESULTS AS a
INNER JOIN RAG_STARTER.EVAL.EVAL_RESULTS AS b
    ON a.question_id = b.question_id AND a.metric = b.metric
LEFT JOIN RAG_STARTER.EVAL.EVAL_QUESTIONS AS q
    ON a.question_id = q.question_id
WHERE
    a.run_id = $run_a
    AND b.run_id = $run_b
    AND b.score < a.score
ORDER BY change ASC;
