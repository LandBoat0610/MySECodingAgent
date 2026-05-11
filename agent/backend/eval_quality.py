"""Ragas 指标 + LLM-as-a-Judge 模糊评分。"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from agent.backend.config import get_effective_model


def _openai_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
    )


def build_contexts_for_ragas(final_state: Dict[str, Any], workspace_dir: str) -> List[str]:
    chunks: List[str] = []
    cc = final_state.get("code_context")
    if cc and str(cc).strip():
        chunks.append(str(cc)[:8000])
    for p in (final_state.get("modified_files") or [])[:6]:
        if not p:
            continue
        try:
            from agent.backend.utils import resolve_workspace_path, safe_trim

            fp = resolve_workspace_path(workspace_dir, str(p))
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                chunks.append(f"[file:{p}]\n" + safe_trim(f.read(), 6000))
        except Exception:
            continue
    if not chunks:
        chunks.append("(无可用的本地上下文)")
    return chunks[:10]


def _evaluation_result_to_dict(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return dict(result)
    if hasattr(result, "scores") and isinstance(getattr(result, "scores"), dict):
        return dict(result.scores)  # type: ignore[arg-type]
    try:
        df = result.to_pandas()
        row = df.iloc[0].to_dict()
        skip = {"user_input", "response", "retrieved_contexts"}
        return {k: v for k, v in row.items() if k not in skip}
    except Exception:
        pass
    return {}


def compute_ragas_scores(question: str, answer: str, contexts: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"answer_relevancy": None, "faithfulness": None, "error": None}
    q = (question or "").strip()[:16000]
    a = (answer or "").strip()[:16000]
    if not q or not a:
        out["error"] = "empty_question_or_answer"
        return out
    ctx_list = [str(c)[:12000] for c in contexts if str(c).strip()]
    if not ctx_list:
        ctx_list = ["(empty context)"]

    if not os.environ.get("OPENAI_API_KEY"):
        out["error"] = "OPENAI_API_KEY missing"
        return out

    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness
        from ragas.llms import llm_factory
        from ragas.embeddings import embedding_factory

        client = _openai_client()
        llm_model = os.environ.get("RAGAS_LLM_MODEL") or get_effective_model()
        embed_model = os.environ.get("RAGAS_EMBED_MODEL", "text-embedding-3-small")

        llm = llm_factory(llm_model, client=client)
        embeddings = embedding_factory("openai", model=embed_model, client=client)

        ds = Dataset.from_dict(
            {
                "user_input": [q],
                "response": [a],
                "retrieved_contexts": [ctx_list],
            }
        )
        result = evaluate(
            ds,
            metrics=[faithfulness, answer_relevancy],
            llm=llm,
            embeddings=embeddings,
            show_progress=False,
            raise_exceptions=False,
        )
        scores = _evaluation_result_to_dict(result)
        for src_key, dst_key in [("answer_relevancy", "answer_relevancy"), ("faithfulness", "faithfulness")]:
            if scores.get(src_key) is not None:
                try:
                    v = float(scores[src_key])
                    out[dst_key] = None if math.isnan(v) else v
                except (TypeError, ValueError):
                    pass
    except Exception as e:
        out["error"] = str(e)[:2000]
    return out


def compute_judge_scores(
    task_description: str,
    agent_answer: str,
    contexts: List[str],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "reasoning_quality": None,
        "hallucination_severity": None,
        "comment": "",
        "error": None,
    }
    if not os.environ.get("OPENAI_API_KEY"):
        out["error"] = "OPENAI_API_KEY missing"
        return out

    judge_model = os.environ.get("JUDGE_MODEL") or get_effective_model()
    ctx_blob = "\n\n---\n\n".join(str(c)[:6000] for c in contexts[:5])

    sys_prompt = (
        "你是严谨的代码评测裁判。根据「任务描述」「上下文片段」「Agent 最终答复」，"
        "仅输出一个 JSON 对象，键：reasoning_quality（1-10 整数，推理质量），"
        "hallucination_severity（1-10 整数，臆测或与上下文矛盾的严重程度，10 最严重），"
        "comment（一句简短中文点评）。不要 Markdown。"
    )
    user_prompt = (
        f"【任务】\n{task_description[:8000]}\n\n"
        f"【上下文】\n{ctx_blob[:20000]}\n\n"
        f"【Agent 答复】\n{(agent_answer or '')[:12000]}"
    )

    try:
        cli = _openai_client()
        resp = cli.chat.completions.create(
            model=judge_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        rq = data.get("reasoning_quality")
        hs = data.get("hallucination_severity")
        if rq is not None:
            out["reasoning_quality"] = max(1, min(10, int(rq)))
        if hs is not None:
            out["hallucination_severity"] = max(1, min(10, int(hs)))
        out["comment"] = str(data.get("comment") or "")[:500]
    except Exception as e:
        out["error"] = str(e)[:1200]
    return out


def build_radar_vector(
    ragas: Dict[str, Any],
    judge: Dict[str, Any],
    runtime_summary: Dict[str, Any],
    security: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    from agent.backend.runtime_metrics import radar_token_efficiency_norm, radar_tool_success_norm

    ar = ragas.get("answer_relevancy")
    ff = ragas.get("faithfulness")
    rq = judge.get("reasoning_quality")
    hs = judge.get("hallucination_severity")
    sec = security if isinstance(security, dict) else {}
    risk = sec.get("risk_score")

    def clamp01(x: float) -> float:
        return max(0.0, min(1.0, x))

    if risk is None:
        security_hygiene = 1.0
    else:
        security_hygiene = clamp01(1.0 - float(risk) / 10.0)

    return {
        "answer_relevancy": clamp01(float(ar)) if ar is not None else 0.0,
        "faithfulness": clamp01(float(ff)) if ff is not None else 0.0,
        "reasoning_quality": (float(rq) / 10.0) if rq is not None else 0.0,
        "anti_hallucination": (1.0 - (float(hs) - 1) / 9.0) if hs is not None else 0.0,
        "tool_success": radar_tool_success_norm(runtime_summary),
        "token_efficiency": radar_token_efficiency_norm(runtime_summary),
        "security_hygiene": security_hygiene,
    }


def mean_radar(
    vectors: List[Dict[str, float]],
    key_order: Optional[List[str]] = None,
) -> Dict[str, float]:
    if not vectors:
        return {}
    if key_order:
        keys = list(key_order)
    else:
        keys = sorted({k for v in vectors for k in v.keys()})
    acc = {k: 0.0 for k in keys}
    cnt = {k: 0 for k in keys}
    for v in vectors:
        for k in keys:
            if k in v:
                acc[k] += float(v[k])
                cnt[k] += 1
    return {k: round(acc[k] / max(1, cnt[k]), 4) for k in keys}
