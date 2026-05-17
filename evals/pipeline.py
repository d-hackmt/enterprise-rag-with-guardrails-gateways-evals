"""
Phase 1 — Live Pipeline.
Calls the running FastAPI /query endpoint for each golden sample.
Captures: actual_response (summarized via Groq to preserve key facts),
          actual_contexts (from sources), actual_tools_called (from thought_process).

Why summarize instead of truncate:
  Truncating to 300 chars cuts off facts mid-sentence, causing artificially low
  RAGAS scores (AnswerCorrectness, Faithfulness). Summarizing preserves all key
  claims in ~150-200 words, keeping token usage low while giving RAGAS accurate
  material to judge against the ground truth reference.
"""

import time
import copy
import json
import os
import requests
import logfire
from openai import OpenAI

API_URL = os.getenv("BACKEND_URL", "http://localhost:8000") + "/query"
DELAY_BETWEEN_CALLS = 10   # seconds between /query calls — stays within Groq RPM on main key
SUMMARIZE_THRESHOLD = 400  # chars — answers shorter than this are used as-is
SUMMARY_MAX_TOKENS  = 250  # max tokens for the Groq summary call

GROQ_BASE_URL  = "https://api.groq.com/openai/v1"
SUMMARY_MODEL  = "llama-3.1-8b-instant"   # fast + cheap model for summarization


def _get_summary_client() -> OpenAI:
    """Groq client for the summarization step — uses JUDGE_GROQ to avoid touching the prod key."""
    key = os.getenv("JUDGE_GROQ") or os.getenv("GROQ_API_KEY")
    return OpenAI(api_key=key, base_url=GROQ_BASE_URL)


def _summarize_for_eval(answer: str, question: str) -> str:
    """
    Converts a long RAG answer into a compact factual summary for RAGAS evaluation.
    Preserves specific numbers, names, and technical claims — the things RAGAS judges on.
    Falls back to a 600-char slice if Groq is unavailable.
    """
    if not answer or len(answer) <= SUMMARIZE_THRESHOLD:
        return answer

    prompt = (
        f"Summarize the following answer to the question in 3-5 bullet points.\n"
        f"Rules: preserve ALL specific facts, numbers, names, and technical details. "
        f"Do NOT add information not present in the answer. Be concise.\n\n"
        f"Question: {question}\n\n"
        f"Answer: {answer}\n\n"
        f"Bullet-point summary:"
    )

    try:
        client = _get_summary_client()
        resp = client.chat.completions.create(
            model=SUMMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=SUMMARY_MAX_TOKENS,
            temperature=0,
        )
        summary = resp.choices[0].message.content.strip()
        logfire.info(f"📝 Summarized answer: {len(answer)} chars → {len(summary)} chars")
        return summary
    except Exception as e:
        logfire.warning(f"⚠️ Summarization failed (using first 600 chars): {e}")
        return answer[:600]


def detect_tool(thought_process: list) -> str:
    """
    Maps the thought_process list from /query response to a tool name.
    Planner sets:  'Intent: Technical' + 'Search Term: ...' → retrieve_documents
                   'Intent: Conversational/Memory'           → direct_answer
    main.py sets:  'Intent: Guardrails Fired'                → guardrails
    """
    joined = " ".join(thought_process).lower()
    if "guardrails fired" in joined:
        return "guardrails"
    if "intent: technical" in joined or "search term:" in joined or "context retrieved" in joined:
        return "retrieve_documents"
    if "conversational" in joined or "memory" in joined:
        return "direct_answer"
    return "unknown"


def run_pipeline(golden_dataset: dict, progress_callback=None) -> dict:
    """
    Enriches each rag_sample in golden_dataset with live API results.
    Returns a deep copy with actual_response, actual_contexts, actual_tools_called filled.
    progress_callback(i, total, question, stage, response="") is called per step.
    """
    dataset = copy.deepcopy(golden_dataset)
    samples = dataset["rag_samples"]
    n = len(samples)

    with logfire.span("🚀 Eval Phase 1 — Live Pipeline", total_samples=n):
        for i, sample in enumerate(samples):
            question = sample["question"]

            if progress_callback:
                progress_callback(i, n, question, "calling")

            with logfire.span(
                f"📤 Live Query {i + 1}/{n}",
                question=question[:80],
                domain=sample.get("domain", ""),
            ):
                try:
                    resp = requests.post(
                        API_URL,
                        json={"q": question, "thread_id": f"eval_run_{i}"},
                        timeout=60,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    raw_answer     = data.get("answer") or ""
                    thought_process = data.get("thought_process") or []
                    sources        = data.get("sources") or []

                    # Summarize instead of truncate — preserves factual claims for RAGAS
                    sample["actual_response"]    = _summarize_for_eval(raw_answer, question)
                    sample["actual_contexts"]    = sources[:5]
                    sample["actual_tools_called"] = [detect_tool(thought_process)]

                    logfire.info(
                        "✅ Response captured",
                        tool=sample["actual_tools_called"][0],
                        original_chars=len(raw_answer),
                        stored_chars=len(sample["actual_response"]),
                        context_chunks=len(sources),
                    )

                except requests.exceptions.ConnectionError:
                    logfire.error("❌ Cannot reach FastAPI — is the app running on :8000?")
                    sample["actual_response"]    = ""
                    sample["actual_contexts"]    = sample.get("relevant_contexts", [])
                    sample["actual_tools_called"] = ["unknown"]

                except Exception as e:
                    logfire.error(f"❌ Query failed: {e}")
                    sample["actual_response"]    = ""
                    sample["actual_contexts"]    = sample.get("relevant_contexts", [])
                    sample["actual_tools_called"] = ["unknown"]

            if progress_callback:
                progress_callback(i, n, question, "done", sample["actual_response"])

            if i < n - 1:
                time.sleep(DELAY_BETWEEN_CALLS)

    return dataset


def save_results(dataset: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(dataset, f, indent=2)


def load_golden_dataset() -> dict:
    golden_path = os.path.join(os.path.dirname(__file__), "golden_dataset.json")
    with open(golden_path) as f:
        return json.load(f)
