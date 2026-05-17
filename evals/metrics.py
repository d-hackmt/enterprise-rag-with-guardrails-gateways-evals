"""
Phase 2 — RAGAS + Tool Correctness metrics.

Key design decisions:
  - Judge LLM  : Groq llama-3.1-8b-instant via JUDGE_GROQ key (never touches prod key)
  - Embeddings : Vertex AI text-embedding-004 — same model as production, no PyTorch needed
  - Rate limits: GENERAL_BATCH_SIZE=1 + COOLDOWN_MINI between samples keeps each 60s window
                 well under Groq's 6,000 TPM on_demand ceiling.
  - Resilience : exponential backoff retry (up to 8 attempts, max 5 min wait) on any 429.
                 The pipeline will always complete — it just waits longer if rate-limited.
"""

import os
import asyncio
import logfire
import pandas as pd
from openai import AsyncOpenAI


from ragas.llms import llm_factory
from ragas import SingleTurnSample
from ragas.metrics.collections import (
    Faithfulness,
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    AnswerCorrectness,
)

GROQ_BASE_URL  = "https://api.groq.com/openai/v1"
JUDGE_MODEL    = "llama-3.1-8b-instant"

COOLDOWN_STANDARD  = 62    # seconds between experiments
COOLDOWN_MINI      = 40    # seconds between individual samples within an experiment
GENERAL_BATCH_SIZE = 1     # one sample at a time — prevents concurrent bursts

CONTEXT_LIMIT      = 2     # max context chunks passed to RAGAS per sample
CONTEXT_TRUNCATE   = 600   # chars per chunk (increased from 300 — summarized answers are richer)

# Retry config for 429 / rate-limit resilience
MAX_RETRIES       = 8
RETRY_BASE_DELAY  = 60.0   # seconds — doubles each attempt: 60, 120, 240, 300, 300...
MAX_RETRY_WAIT    = 300.0  # 5-minute cap per retry


def _build_judge():
    """
    Builds the RAGAS judge LLM (Groq) and embedding model (Vertex AI).
    Uses ragas.embeddings.GoogleEmbeddings with use_vertex=True —
    the modern RAGAS interface required by collection metrics (AnswerRelevancy, AnswerCorrectness).
    """
    api_key = os.getenv("JUDGE_GROQ") or os.getenv("GROQ_API_KEY")
    client  = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
    llm     = llm_factory(JUDGE_MODEL, provider="openai", client=client)

    import vertexai
    from vertexai.language_models import TextEmbeddingModel
    from ragas.embeddings import GoogleEmbeddings

    project  = os.getenv("PROJECT_ID", "dmtxpresss")
    location = os.getenv("LOCATION", "us-central1")
    vertexai.init(project=project, location=location)
    vertex_client = TextEmbeddingModel.from_pretrained("text-embedding-004")

    embeddings = GoogleEmbeddings(
        client=vertex_client,
        model="text-embedding-004",
        use_vertex=True,
        project_id=project,
        location=location,
    )
    return llm, embeddings


async def _cooldown(seconds: int, label: str, status_cb=None):
    msg = f"⏳ {seconds}s cooldown after {label} (Groq TPM buffer)..."
    if status_cb:
        status_cb(msg)
    for _ in range(seconds // 10):
        await asyncio.sleep(10)
    if status_cb:
        status_cb("✅ Ready — starting next experiment.")


def _prep_samples(golden_dataset: dict) -> list:
    """
    Returns only samples with actual_response populated.
    Contexts are trimmed to CONTEXT_TRUNCATE chars and CONTEXT_LIMIT chunks
    to keep each RAGAS LLM call within the 6,000 TPM ceiling.
    """
    valid = []
    for s in golden_dataset["rag_samples"]:
        response = s.get("actual_response", "").strip()
        if not response:
            continue
        raw_contexts = s.get("actual_contexts") or s.get("relevant_contexts") or []
        contexts = [c[:CONTEXT_TRUNCATE] for c in raw_contexts[:CONTEXT_LIMIT]]
        valid.append({**s, "actual_contexts": contexts})
    return valid


def _score_df(metric_key: str, samples: list, scores) -> pd.DataFrame:
    return pd.DataFrame([
        {"question": s["question"][:65], metric_key: round(float(r.value), 3)}
        for s, r in zip(samples, scores)
    ])


async def _batched_score(
    metric,
    inputs: list,
    samples: list,
    status_cb=None,
    label: str = "",
) -> list:
    """
    Scores in chunks of GENERAL_BATCH_SIZE with cooldowns between chunks.
    Each individual call is retried with exponential backoff on 429 / rate-limit errors.
    The pipeline will always finish — it just waits when Groq needs breathing room.
    """
    all_scores = []
    batches = [inputs[i: i + GENERAL_BATCH_SIZE] for i in range(0, len(inputs), GENERAL_BATCH_SIZE)]

    for b_idx, batch in enumerate(batches):
        if b_idx > 0:
            await _cooldown(COOLDOWN_MINI, f"{label} sample {b_idx}", status_cb)

        # --- Retry loop ---
        for attempt in range(MAX_RETRIES):
            try:
                scores = await metric.abatch_score(batch)
                all_scores.extend(scores)
                break  # success — move to next batch
            except Exception as e:
                is_rate_limit = "429" in str(e) or "rate" in str(e).lower() or "limit" in str(e).lower()

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    wait = min(RETRY_BASE_DELAY * (2 ** attempt), MAX_RETRY_WAIT)
                    msg = (
                        f"⚠️ Rate limit on [{label}] sample {b_idx + 1} "
                        f"(attempt {attempt + 1}/{MAX_RETRIES}) — waiting {wait:.0f}s..."
                    )
                    logfire.warning(msg)
                    if status_cb:
                        status_cb(msg)
                    await asyncio.sleep(wait)
                else:
                    logfire.error(f"❌ Non-retryable error on [{label}]: {e}")
                    raise

    return all_scores


async def run_all_metrics(golden_dataset: dict, status_cb=None) -> dict:
    """
    Runs all 6 experiments. Returns dict keyed by metric name → DataFrame.
    status_cb(message: str) is called for live UI updates.
    """
    judge_llm, ragas_embeddings = _build_judge()
    samples = _prep_samples(golden_dataset)

    if not samples:
        raise ValueError("No samples with actual_response found. Run Phase 1 first.")

    results = {}

    with logfire.span("🧪 Eval Phase 2 — All Metrics", total_samples=len(samples)):

        # ── Exp 1: Faithfulness ───────────────────────────────────────────────
        if status_cb:
            status_cb(f"🧪 Exp 1/6 — Faithfulness ({len(samples)} samples)...")
        with logfire.span("🧪 Exp 1 — Faithfulness"):
            inputs = [
                {
                    "user_input": s["question"],
                    "response": s["actual_response"],
                    "retrieved_contexts": s["actual_contexts"],
                }
                for s in samples
            ]
            scores = await _batched_score(
                Faithfulness(llm=judge_llm), inputs, samples, status_cb, "Faithfulness"
            )
            df = _score_df("faithfulness", samples, scores)
            results["faithfulness"] = df
            logfire.info("🧪 Faithfulness done", avg=round(df["faithfulness"].mean(), 3))

        await _cooldown(COOLDOWN_STANDARD, "Faithfulness", status_cb)

        # ── Exp 2: Answer Relevancy ───────────────────────────────────────────
        if status_cb:
            status_cb(f"🧪 Exp 2/6 — Answer Relevancy ({len(samples)} samples)...")
        with logfire.span("🧪 Exp 2 — Answer Relevancy"):
            inputs = [
                {"user_input": s["question"], "response": s["actual_response"]}
                for s in samples
            ]
            scores = await _batched_score(
                AnswerRelevancy(llm=judge_llm, embeddings=ragas_embeddings),
                inputs, samples, status_cb, "Answer Relevancy",
            )
            df = _score_df("answer_relevancy", samples, scores)
            results["answer_relevancy"] = df
            logfire.info("🧪 Answer Relevancy done", avg=round(df["answer_relevancy"].mean(), 3))

        await _cooldown(COOLDOWN_STANDARD, "Answer Relevancy", status_cb)

        # ── Exp 3: Context Precision ──────────────────────────────────────────
        if status_cb:
            status_cb(f"🧪 Exp 3/6 — Context Precision ({len(samples)} samples)...")
        with logfire.span("🧪 Exp 3 — Context Precision"):
            inputs = [
                {
                    "user_input": s["question"],
                    "reference": s["reference"],
                    "retrieved_contexts": s["actual_contexts"],
                }
                for s in samples
            ]
            scores = await _batched_score(
                ContextPrecision(llm=judge_llm), inputs, samples, status_cb, "Context Precision"
            )
            df = _score_df("context_precision", samples, scores)
            results["context_precision"] = df
            logfire.info("🧪 Context Precision done", avg=round(df["context_precision"].mean(), 3))

        await _cooldown(COOLDOWN_STANDARD, "Context Precision", status_cb)

        # ── Exp 4: Context Recall ─────────────────────────────────────────────
        if status_cb:
            status_cb(f"🧪 Exp 4/6 — Context Recall ({len(samples)} samples)...")
        with logfire.span("🧪 Exp 4 — Context Recall"):
            inputs = [
                {
                    "user_input": s["question"],
                    "reference": s["reference"],
                    "retrieved_contexts": s["actual_contexts"],
                }
                for s in samples
            ]
            scores = await _batched_score(
                ContextRecall(llm=judge_llm), inputs, samples, status_cb, "Context Recall"
            )
            df = _score_df("context_recall", samples, scores)
            results["context_recall"] = df
            logfire.info("🧪 Context Recall done", avg=round(df["context_recall"].mean(), 3))

        await _cooldown(COOLDOWN_STANDARD, "Context Recall", status_cb)

        # ── Exp 5: Answer Correctness ─────────────────────────────────────────
        if status_cb:
            status_cb(f"🧪 Exp 5/6 — Answer Correctness ({len(samples)} samples)...")
        with logfire.span("🧪 Exp 5 — Answer Correctness"):
            inputs = [
                {
                    "user_input": s["question"],
                    "response": s["actual_response"],
                    "reference": s["reference"],
                }
                for s in samples
            ]
            scores = await _batched_score(
                AnswerCorrectness(llm=judge_llm, embeddings=ragas_embeddings),
                inputs, samples, status_cb, "Answer Correctness",
            )
            df = _score_df("answer_correctness", samples, scores)
            results["answer_correctness"] = df
            logfire.info("🧪 Answer Correctness done", avg=round(df["answer_correctness"].mean(), 3))

        await _cooldown(COOLDOWN_STANDARD, "Answer Correctness", status_cb)

        # ── Exp 6: Tool Correctness (no LLM — pure Jaccard) ──────────────────
        if status_cb:
            status_cb("⚡ Exp 6/6 — Tool Correctness (zero LLM calls)...")
        with logfire.span("🧪 Exp 6 — Tool Correctness"):
            tool_rows = []
            for s in samples:
                called   = set(s.get("actual_tools_called") or [])
                expected = set(s.get("expected_tools") or [])
                union    = len(called | expected)
                score    = len(called & expected) / union if union > 0 else 0.0
                tool_rows.append({"question": s["question"][:65], "tool_correctness": round(score, 3)})
            df = pd.DataFrame(tool_rows)
            results["tool_correctness"] = df
            logfire.info("🧪 Tool Correctness done", avg=round(df["tool_correctness"].mean(), 3))

        if status_cb:
            status_cb("✅ All 6 experiments complete!")

    return results
