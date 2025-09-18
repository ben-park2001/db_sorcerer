# text_chunker.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Protocol, runtime_checkable
import json
import re


# =========================
# Public types & interface
# =========================

@runtime_checkable
class LLMClient(Protocol):
    def complete(self, prompt: str, **kwargs) -> str: ...


@dataclass
class ChunkMeta:
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    word_start: int
    word_end: int


@dataclass
class ChunkingResult:
    chunks: List[ChunkMeta]
    llm_raw: Optional[str] = None
    mapping_info: Optional[Dict[str, Any]] = None


__all__ = [
    "LLMClient", "ChunkMeta", "ChunkingResult", "llm_guided_sentence_chunk",
    "split_sentences_ko_en", "build_sentence_char_spans",
]


# =========================
# Main API
# =========================

def llm_guided_sentence_chunk(
        text: str, llm: LLMClient, max_sentences_per_chunk: int = 20,
        system_hint: Optional[str] = None, *, debug: bool = True,
        retry_on_fail: bool = True, fallback_on_fail: bool = True,
) -> ChunkingResult:
    if not text or not text.strip():
        return ChunkingResult(chunks=[], llm_raw=None, mapping_info={"reason": "empty_text"})

    sents = split_sentences_ko_en(text)
    if not sents:
        single = _make_chunk(0, text, 0, len(text), 0, len(text.split()))
        return ChunkingResult(chunks=[single], mapping_info={"reason": "no_sentence_detected"})
    sent_spans = build_sentence_char_spans(text, sents)

    prompt = _build_chunk_prompt_for_completion(sents, system_hint)
    llm_raw_first = llm.complete(prompt)

    if debug: print(f"=== RAW LLM OUTPUT (first try) ===\n{_shorten(llm_raw_first, 1200)}")

    plan = _safe_parse_json(llm_raw_first)
    indices_plan = _map_plan_to_indices(plan, sents, debug=debug)
    chunks = _indices_to_chunks(indices_plan, text, sent_spans)
    used_strategy, llm_raw_all = "llm_completion_final", llm_raw_first or ""

    if not chunks and retry_on_fail:
        reprompt = _build_repair_prompt_for_completion(llm_raw_first)
        llm_raw_retry = llm.complete(reprompt)
        if debug: print(f"=== RAW LLM OUTPUT (retry) ===\n{_shorten(llm_raw_retry, 1200)}")
        plan_retry = _safe_parse_json(llm_raw_retry)
        indices_plan_retry = _map_plan_to_indices(plan_retry, sents, debug=debug)
        chunks = _indices_to_chunks(indices_plan_retry, text, sent_spans)
        llm_raw_all += f"\n\n=== RETRY ===\n{llm_raw_retry or ''}"
        used_strategy = "llm_completion_retry_final" if chunks else used_strategy

    if not chunks and fallback_on_fail:
        if debug: print("⚠️ LLM 응답 처리 실패 → 룰기반 분할로 fallback 합니다.")
        chunks = _fallback_rule_based_chunks(text, sents, sent_spans)
        used_strategy = "fallback_rule"

    return ChunkingResult(chunks=chunks, llm_raw=llm_raw_all,
                          mapping_info={"num_sentences": len(sents), "used_strategy": used_strategy})


# =========================
# Core Logic: Prompts & Parsers
# =========================

def _build_chunk_prompt_for_completion(sents: List[str], system_hint: Optional[str]) -> str:
    guideline = system_hint or "당신은 텍스트 분석 전문가입니다. 당신의 유일한 임무는 주어진 문장들을 논리적 단위로 묶고, 그 결과를 지정된 JSON 형식으로 출력하는 것입니다."
    numbered_sentences = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sents))

    return f"""{guideline}

### 분석할 문장 목록:
---
{numbered_sentences}
---

### 작업 지시:
위 문장 목록을 주제에 따라 의미가 연결되는 여러 개의 청크(chunk)로 나누세요.
각 청크의 `first_sentence`와 `last_sentence`는 위 목록의 문장을 **그대로 복사**하여 사용해야 합니다.

### 출력 규칙:
- **오직 JSON 객체 하나만 출력해야 합니다.**
- 당신의 응답은 반드시 `{{` 로 시작하고 `}}` 로 끝나야 합니다.
- 설명, 인사, 태그 등 다른 텍스트를 절대로 포함해서는 안 됩니다.

### 이제 위 규칙에 따라 JSON 출력을 시작하세요:"""


def _build_repair_prompt_for_completion(previous_output: str) -> str:
    prev = _shorten(_strip_code_fences(previous_output or ""), 800)
    return f"""이전 출력이 규칙을 위반했습니다.
규칙을 다시 확인하고, **설명 없이 오직 JSON 객체 하나만** 출력하세요.
당신의 응답은 반드시 `{{` 로 시작해야 합니다.

### 이전의 잘못된 출력:
{prev}

### 올바른 JSON 출력을 시작하세요:"""


def _safe_parse_json(s: Any) -> Any:
    if not isinstance(s, str): return {}
    try:
        clean_s = _strip_code_fences(s.strip())
        if clean_s.startswith("{"):
            return json.loads(clean_s)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", s)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _map_plan_to_indices(plan: Any, sents: List[str], debug: bool) -> List[Tuple[int, int]]:
    if not isinstance(plan, dict) or "chunks" not in plan or not isinstance(plan["chunks"], list):
        if debug and plan: print(f"[DBG] Plan is not a valid dict with a 'chunks' list. Plan: {plan}")
        return []
    indices_plan, cursor = [], 0
    for i, chunk_plan in enumerate(plan["chunks"]):
        if not isinstance(chunk_plan, dict): continue
        first_s, last_s = chunk_plan.get("first_sentence"), chunk_plan.get("last_sentence")
        if not all(isinstance(s, str) for s in [first_s, last_s]): continue
        try:
            start_idx = sents.index(first_s.strip(), cursor)
            end_idx = sents.index(last_s.strip(), start_idx)
            indices_plan.append((start_idx, end_idx))
            cursor = end_idx + 1
        except ValueError:
            if debug: print(f"[WARN] Failed to find sentence from plan chunk #{i}.")
    return indices_plan


def _indices_to_chunks(indices_plan: List[Tuple[int, int]], text: str, sent_spans: List[Tuple[int, int]]) -> List[
    ChunkMeta]:
    chunks = []
    for i, (start_idx, end_idx) in enumerate(indices_plan):
        if end_idx < start_idx: continue
        cs, ce = sent_spans[start_idx][0], sent_spans[end_idx][1]
        chunk_text = text[cs:ce]
        if not chunk_text.strip(): continue
        ws = len(text[:cs].split())
        we = ws + len(chunk_text.split()) - 1 if chunk_text.split() else ws
        chunks.append(_make_chunk(i, chunk_text, cs, ce, ws, we))
    return chunks


# =========================
# Helper Functions
# =========================

def split_sentences_ko_en(text: str) -> List[str]:
    if not text.strip(): return []
    lines = re.split(r"\n+", text)
    sents = [p.strip() for line in lines if line.strip() for p in re.split(r"(?<=[\.!\?])\s+", line.strip()) if
             p.strip()]
    return sents


def build_sentence_char_spans(text: str, sentences: List[str]) -> List[Tuple[int, int]]:
    spans, cursor = [], 0
    for s in sentences:
        try:
            start = text.index(s, cursor)
            end = start + len(s)
            spans.append((start, end))
            cursor = end
        except ValueError:
            spans.append((cursor, cursor))
    return spans


def _fallback_rule_based_chunks(text: str, sents: List[str], sent_spans: List[Tuple[int, int]], max_sents: int = 8) -> \
List[ChunkMeta]:
    if not sents: return []
    step = max(3, min(10, max_sents))
    chunks = []
    for i in range(0, len(sents), step):
        s_idx, e_idx = i, min(i + step - 1, len(sents) - 1)
        cs, ce = sent_spans[s_idx][0], sent_spans[e_idx][1]
        chunk_text = text[cs:ce]
        if not chunk_text.strip(): continue
        ws = len(text[:cs].split())
        we = ws + len(chunk_text.split()) - 1 if chunk_text.split() else ws
        chunks.append(_make_chunk(len(chunks), chunk_text, cs, ce, ws, we))
    return chunks


def _strip_code_fences(s: str) -> str:
    return re.sub(r"^```json|^```|```$", "", s, flags=re.MULTILINE).strip()


def _shorten(s: Optional[str], n: int) -> str:
    return s if not s or len(s) <= n else s[:n] + " …(truncated)"


def _make_chunk(idx: int, text: str, cs: int, ce: int, ws: int, we: int) -> ChunkMeta:
    return ChunkMeta(chunk_index=idx, text=text, char_start=cs, char_end=ce, word_start=ws, word_end=we)