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
    """
    외부 LLM 어댑터가 만족해야 하는 최소 인터페이스.
    예: adapter.complete(prompt: str, **kwargs) -> str
    """
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
    mapping_info: Optional[Dict[str, Any]] = None  # 디버그/통계용

__all__ = [
    "LLMClient",
    "ChunkMeta",
    "ChunkingResult",
    "llm_guided_sentence_chunk",
    "split_sentences_ko_en",
    "build_sentence_char_spans",
]

# =========================
# Main API
# =========================

def llm_guided_sentence_chunk(
    text: str,
    llm: LLMClient,
    max_sentences_per_chunk: int = 20,
    system_hint: Optional[str] = None,
    *,
    debug: bool = True,
    retry_on_fail: bool = True,
    fallback_on_fail: bool = True,
) -> ChunkingResult:
    """
    1) 문장 분할
    2) LLM에 청크 경계(JSON) 요청
    3) 파싱/검증 실패 시 재프롬프트 → 그래도 실패하면 룰기반 분할 fallback
    """
    if not text or not text.strip():
        return ChunkingResult(chunks=[], llm_raw=None, mapping_info={"reason": "empty_text"})

    # --- 1) 문장 분할 & 스팬 생성 ---
    sents = split_sentences_ko_en(text)
    if not sents:
        # 문장 기준 분할이 전혀 안 되면 전체를 하나의 청크로
        single = _make_chunk(
            chunk_index=0, text=text, char_start=0, char_end=len(text),
            word_start=0,
            word_end=len(text.split()) - 1 if text.split() else 0,
        )
        return ChunkingResult(chunks=[single], mapping_info={"reason": "no_sentence_detected"})

    sent_spans = build_sentence_char_spans(text, sents)

    # --- 2) LLM 프롬프트 구성 & 호출 ---
    prompt = _build_chunk_prompt(
        num_sentences=len(sents),
        max_sentences_per_chunk=max_sentences_per_chunk,
        system_hint=system_hint,
    )

    llm_raw_first = llm.complete(
        prompt,
        temperature=0.0,  # 결정적
        top_p=1.0,
        max_tokens=600,
    )

    if debug:
        print("=== RAW LLM OUTPUT (first try) ===")
        print(_shorten(llm_raw_first, 1200))

    plan_first = _safe_parse_json(llm_raw_first)
    chunks = _chunks_from_plan(
        text=text,
        sents=sents,
        sent_spans=sent_spans,
        plan=plan_first,
        max_sentences_per_chunk=max_sentences_per_chunk,
        debug=debug
    )

    used_strategy = "llm"
    llm_raw_all = llm_raw_first or ""

    # --- 3) 재시도 (옵션) ---
    if not chunks and retry_on_fail:
        reprompt = _build_repair_prompt(
            previous_output=llm_raw_first,
            num_sentences=len(sents),
            max_sentences_per_chunk=max_sentences_per_chunk
        )
        llm_raw_retry = llm.complete(
            reprompt,
            temperature=0.0,
            top_p=1.0,
            max_tokens=600,
        )
        if debug:
            print("=== RAW LLM OUTPUT (retry) ===")
            print(_shorten(llm_raw_retry, 1200))

        plan_retry = _safe_parse_json(llm_raw_retry)
        chunks = _chunks_from_plan(
            text=text,
            sents=sents,
            sent_spans=sent_spans,
            plan=plan_retry,
            max_sentences_per_chunk=max_sentences_per_chunk,
            debug=debug
        )
        llm_raw_all = (llm_raw_first or "") + "\n\n=== RETRY ===\n" + (llm_raw_retry or "")
        used_strategy = "llm_retry" if chunks else used_strategy

    # --- 4) 룰기반 Fallback (옵션) ---
    if not chunks and fallback_on_fail:
        if debug:
            print("⚠️ LLM JSON 파싱/검증 실패 → 룰기반 분할로 fallback 합니다.")
            print("=== RAW LLM OUTPUT (last) ===")
            print(_shorten(llm_raw_all, 1200))
        chunks = _fallback_rule_based_chunks(
            text=text,
            sents=sents,
            sent_spans=sent_spans,
            # capped to keep chunks moderate & useful
            max_sentences_per_chunk=max(6, min(10, max_sentences_per_chunk)),
        )
        used_strategy = "fallback_rule"

    # --- 5) 최소 한 청크 보장 ---
    if not chunks:
        whole = _make_chunk(
            chunk_index=0, text=text, char_start=0, char_end=len(text),
            word_start=0,
            word_end=len(text.split()) - 1 if text.split() else 0,
        )
        chunks = [whole]
        used_strategy = used_strategy + "_forced_single"

    return ChunkingResult(
        chunks=chunks,
        llm_raw=llm_raw_all,
        mapping_info={
            "num_sentences": len(sents),
            "used_strategy": used_strategy,
            "max_sentences_per_chunk": max_sentences_per_chunk,
        },
    )

# =========================
# Helpers
# =========================

def split_sentences_ko_en(text: str) -> List[str]:
    """
    초경량 문장 분할기(한국어/영문 혼합).
    - 개행 우선 분할 후, 마침표/물음표/느낌표 기준으로 추가 분할
    """
    if not text.strip():
        return []
    lines = re.split(r"\n+", text)
    sents: List[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[\.!\?])\s+", line)
        for p in parts:
            p = p.strip()
            if p:
                sents.append(p)
    return sents

def build_sentence_char_spans(text: str, sentences: List[str]) -> List[Tuple[int, int]]:
    """
    원문 내 각 문장의 (char_start, char_end) 위치를 계산.
    동일 문장 반복 시 앞에서부터 매칭(선형 커서).
    """
    spans: List[Tuple[int, int]] = []
    cursor = 0
    n = len(text)
    for s in sentences:
        s_stripped = s.strip()
        if not s_stripped:
            spans.append((cursor, cursor))
            continue
        m = re.search(re.escape(s_stripped), text[cursor:])
        if not m:
            start = cursor
            end = min(n, start + len(s_stripped))
        else:
            start = cursor + m.start()
            end = cursor + m.end()
        spans.append((start, end))
        cursor = end
    return spans

def _build_chunk_prompt(
    num_sentences: int,
    max_sentences_per_chunk: int,
    system_hint: Optional[str],
) -> str:
    """
    LLM에게 '오직 JSON'만 요구.
    - 문장 텍스트를 보여주지 않음(패턴 복사 방지)
    - 간결한 few-shot 예시로 "숫자 인덱스"를 학습
    - 프롬프트 끝을 'JSON:\\n{' 로 강하게 유도
    """
    guideline = (
        system_hint
        or "You are a JSON-only generator. Output exactly ONE JSON object. No explanations."
    )

    example = (
        'Example:\n'
        'INPUT: 9 sentences\n'
        'OUTPUT (JSON):\n'
        '{"chunks":[{"first_sentence_index":0,"last_sentence_index":3,"title":"intro"},'
        '{"first_sentence_index":4,"last_sentence_index":6,"title":"methods"},'
        '{"first_sentence_index":7,"last_sentence_index":8,"title":"conclusion"}]}\n'
        '---\n'
    )

    return (
        f"{guideline}\n\n"
        f"{example}"
        "Now apply the same format.\n"
        f"INPUT: {num_sentences} sentences\n"
        f"Rule: group ADJACENT sentences into chunks (min 3, max {max_sentences_per_chunk} per chunk). "
        "Use 0-based indices. Ensure first_sentence_index ≤ last_sentence_index.\n"
        "Return ONLY the JSON object.\n"
        "JSON:\n{"
    )

def _build_repair_prompt(
    previous_output: str,
    num_sentences: int,
    max_sentences_per_chunk: int
) -> str:
    """첫 응답이 JSON이 아닐 때 재시도용 프롬프트."""
    prev = (previous_output or "").strip()
    prev = _strip_code_fences(prev)
    prev = _shorten(prev, 800)
    return (
        "The previous response was NOT valid JSON per the schema/pattern.\n"
        "Return ONLY ONE JSON object now. No explanations. Start immediately with '{'.\n"
        'The JSON must match: {"chunks":[{"first_sentence_index":<int>,"last_sentence_index":<int>,"title":"<string>"}...]}\n'
        f"INPUT: {num_sentences} sentences\n"
        f"Constraints: Each chunk has 3~{max_sentences_per_chunk} sentences; indices are 0-based; chunks are adjacent.\n"
        f"Previous output (truncated):\n{prev}\n"
        "JSON:\n{"
    )

def _safe_parse_json(s: Any) -> Any:
    """
    가능한 관용적으로 JSON 파싱.
    - 코드펜스/채팅 프롤로그 제거
    - 여러 JSON 블록이 있으면 '마지막' 객체/배열을 우선
    - 스키마 예시(placeholder: <int>, <string>, ...)는 건너뛴다
    - 채팅 템플릿 누출 토큰({assistant 등) 무시
    """
    if not isinstance(s, str):
        return {}
    raw = _strip_code_fences(s.strip())
    # 자주 누출되는 프롤로그/마커 이후는 잘라낸다
    for fence in ["{assistant", "\n<SENTENCES>", "\nSchema", "\nExample:", "```"]:
        if fence in raw:
            raw = raw.split(fence, 1)[0].rstrip()

    # 1) direct load
    try:
        return json.loads(raw)
    except Exception:
        pass

    # 2) find ALL JSON objects, prefer the last that doesn't contain placeholders
    objs = re.findall(r"\{.*?\}", raw, flags=re.DOTALL)
    for cand in reversed(objs):
        if re.search(r"<int>|<string>|\.\.\.", cand):
            continue
        try:
            return json.loads(cand)
        except Exception:
            continue

    # 3) allow top-level arrays too (prefer last) and skip placeholders
    arrs = re.findall(r"\[.*?\]", raw, flags=re.DOTALL)
    for cand in reversed(arrs):
        if re.search(r"<int>|<string>|\.\.\.", cand):
            continue
        try:
            return json.loads(cand)
        except Exception:
            continue

    return {}

def _chunks_from_plan(
    text: str,
    sents: List[str],
    sent_spans: List[Tuple[int, int]],
    plan: Any,
    max_sentences_per_chunk: int,
    debug: bool = False,
) -> List[ChunkMeta]:
    """
    계획 JSON을 ChunkMeta 리스트로 변환.
    - 1-based 응답 자동 보정(휴리스틱)
    - 경계 클램핑/역전 교정
    - 최소 1문장은 포함되도록 필터
    """
    if not plan:
        return []

    # plan이 리스트(최상위 배열)이면 그대로 사용
    if isinstance(plan, list):
        items = plan
    elif isinstance(plan, dict) and "chunks" in plan:
        items = plan["chunks"]
    else:
        items = plan.get("chunks", []) if isinstance(plan, dict) else []

    if not isinstance(items, list) or not items:
        return []

    # 1-based 여부 휴리스틱: 모든 first/last가 1 이상이면 1-based로 간주
    fs, ls = [], []
    for it in items:
        try:
            fs.append(int(it.get("first_sentence_index")))
            ls.append(int(it.get("last_sentence_index")))
        except Exception:
            pass
    minus_one = bool(fs and ls and min(fs + ls) >= 1)

    chunks: List[ChunkMeta] = []
    for idx, c in enumerate(items):
        try:
            a = int(c["first_sentence_index"])
            b = int(c["last_sentence_index"])
        except Exception:
            continue

        if minus_one:
            a -= 1
            b -= 1

        # 클램핑 & 순서 보정
        a = max(0, min(a, len(sents) - 1))
        b = max(0, min(b, len(sents) - 1))
        if b < a:
            a, b = b, a

        # 실제 문자 오프셋
        cs, ce = sent_spans[a][0], sent_spans[b][1]
        if ce <= cs:
            if debug:
                print(f"[DBG] drop invalid span: idx={idx}, a={a}, b={b}, cs={cs}, ce={ce}")
            continue

        slice_text = text[cs:ce]
        if not slice_text.strip():
            if debug:
                print(f"[DBG] drop empty slice: idx={idx}, a={a}, b={b}")
            continue

        # 단어 오프셋(rough)
        ws = len(text[:cs].split())
        we = ws + len(slice_text.split()) - 1 if slice_text.split() else ws

        chunks.append(ChunkMeta(
            chunk_index=len(chunks),
            text=slice_text,
            char_start=cs,
            char_end=ce,
            word_start=ws,
            word_end=we
        ))

    # (Optional) very small chunks filter can be added here if needed
    return chunks

def _fallback_rule_based_chunks(
    text: str,
    sents: List[str],
    sent_spans: List[Tuple[int, int]],
    max_sentences_per_chunk: int = 8,
) -> List[ChunkMeta]:
    """
    규칙 기반(문장 N개 단위) 분할. 최소 3문장/청크를 기본으로 하되,
    max_sentences_per_chunk 한도 내에서 묶음.
    """
    if not sents:
        t = text.strip()
        if not t:
            return []
        return [
            _make_chunk(0, t, 0, len(text), 0, len(t.split()) - 1 if t.split() else 0)
        ]

    # Moderate step so we always get multiple reasonable chunks
    step = max(3, min(10, max_sentences_per_chunk))
    chunks: List[ChunkMeta] = []
    idx = 0
    for i in range(0, len(sents), step):
        a = i
        b = min(i + step - 1, len(sents) - 1)
        cs, ce = sent_spans[a][0], sent_spans[b][1]
        slice_text = text[cs:ce]
        ws = len(text[:cs].split())
        we = ws + len(slice_text.split()) - 1 if slice_text.strip() else ws
        chunks.append(ChunkMeta(
            chunk_index=idx,
            text=slice_text,
            char_start=cs,
            char_end=ce,
            word_start=ws,
            word_end=we
        ))
        idx += 1
    return chunks

# =========================
# Small utilities
# =========================

def _strip_code_fences(s: str) -> str:
    return re.sub(r"^```json|^```|```$", "", s, flags=re.MULTILINE).strip()

def _shorten(s: Optional[str], n: int) -> str:
    if not s: return ""
    return s if len(s) <= n else s[:n] + " …(truncated)"

def _make_chunk(
    chunk_index: int,
    text: str,
    char_start: int,
    char_end: int,
    word_start: int,
    word_end: int,
) -> ChunkMeta:
    return ChunkMeta(
        chunk_index=chunk_index,
        text=text,
        char_start=char_start,
        char_end=char_end,
        word_start=word_start,
        word_end=word_end,
    )
