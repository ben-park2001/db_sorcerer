# text_chunker.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Protocol, runtime_checkable
import json
import re

# =========================
# Public types & interface (다른 모듈과의 호환성을 위해 변경 없음)
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
    LLM이 청크의 '첫 문장'과 '끝 문장'을 직접 출력하는 방식으로 작동하며,
    프롬프트가 한국어 LLM에 최적화된 버전입니다.
    """
    if not text or not text.strip():
        return ChunkingResult(chunks=[], llm_raw=None, mapping_info={"reason": "empty_text"})

    # --- 1) 문장 분할 & 스팬 생성 ---
    sents = split_sentences_ko_en(text)
    if not sents:
        single = _make_chunk(0, text, 0, len(text), 0, len(text.split()))
        return ChunkingResult(chunks=[single], mapping_info={"reason": "no_sentence_detected"})
    sent_spans = build_sentence_char_spans(text, sents)

    # --- 2) 한국어 프롬프트 구성 및 LLM 호출 ---
    prompt = _build_chunk_prompt_by_sentence_content_ko(sents, system_hint)
    llm_raw_first = llm.complete(prompt, temperature=0.0, max_tokens=2000)

    if debug:
        print("=== RAW LLM OUTPUT (first try) ===")
        print(_shorten(llm_raw_first, 1200))

    plan = _safe_parse_json(llm_raw_first)
    indices_plan = _map_plan_to_indices(plan, sents, debug=debug)
    chunks = _indices_to_chunks(indices_plan, text, sents, sent_spans)

    used_strategy = "llm_content_ko"
    llm_raw_all = llm_raw_first or ""

    # --- 3) 재시도 (옵션) ---
    if not chunks and retry_on_fail:
        reprompt = _build_repair_prompt_by_sentence_content_ko(sents, llm_raw_first)
        llm_raw_retry = llm.complete(reprompt, temperature=0.0, max_tokens=2000)

        if debug:
            print("=== RAW LLM OUTPUT (retry) ===")
            print(_shorten(llm_raw_retry, 1200))

        plan_retry = _safe_parse_json(llm_raw_retry)
        indices_plan_retry = _map_plan_to_indices(plan_retry, sents, debug=debug)
        chunks = _indices_to_chunks(indices_plan_retry, text, sents, sent_spans)
        llm_raw_all += "\n\n=== RETRY ===\n" + (llm_raw_retry or "")
        used_strategy = "llm_content_ko_retry" if chunks else used_strategy

    # --- 4) 룰기반 Fallback (옵션) ---
    if not chunks and fallback_on_fail:
        if debug:
            print("⚠️ LLM 응답 처리 실패 → 룰기반 분할로 fallback 합니다.")
        chunks = _fallback_rule_based_chunks(text, sents, sent_spans)
        used_strategy = "fallback_rule"

    return ChunkingResult(
        chunks=chunks,
        llm_raw=llm_raw_all,
        mapping_info={"num_sentences": len(sents), "used_strategy": used_strategy},
    )

# =========================
# NEW: Core Logic with Korean Prompts
# =========================

def _build_chunk_prompt_by_sentence_content_ko(sents: List[str], system_hint: Optional[str]) -> str:
    """번호 매겨진 문장 목록을 포함하는 한국어 프롬프트 생성"""
    guideline = system_hint or "당신은 문장들을 논리적인 청크(chunk)로 그룹화하는 텍스트 분석 전문가입니다. 당신의 출력은 반드시 단 하나의 JSON 객체여야 합니다."

    example_input = (
        "1. 인공지능은 기술입니다.\n"
        "2. 스마트폰에 사용됩니다.\n"
        "3. 자동화는 직업을 변화시킵니다.\n"
        "4. 단순 업무가 대체됩니다.\n"
        "5. 윤리적 문제도 중요합니다.\n"
        "6. 데이터 편향이 문제입니다."
    )
    example_output = json.dumps({
        "chunks": [
            {"title": "AI 기술 소개", "first_sentence": "인공지능은 기술입니다.", "last_sentence": "스마트폰에 사용됩니다."},
            {"title": "직업 변화", "first_sentence": "자동화는 직업을 변화시킵니다.", "last_sentence": "단순 업무가 대체됩니다."},
            {"title": "윤리적 문제", "first_sentence": "윤리적 문제도 중요합니다.", "last_sentence": "데이터 편향이 문제입니다."}
        ]
    }, ensure_ascii=False)

    numbered_sentences = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sents))

    return (
        f"{guideline}\n\n"
        f"### 예시\n입력 문장:\n---\n{example_input}\n---\n출력 JSON:\n{example_output}\n\n"
        f"### 작업 지시\n"
        f"이제, 아래 문장들을 논리적인 청크로 묶어주세요. 'first_sentence'와 'last_sentence'의 값은 반드시 아래 입력 문장에서 정확히 복사해야 합니다.\n\n"
        f"입력 문장:\n---\n{numbered_sentences}\n---\n출력 JSON:\n"
    )

def _build_repair_prompt_by_sentence_content_ko(sents: List[str], previous_output: str) -> str:
    """콘텐츠 기반 재시도용 한국어 프롬프트"""
    prev = _shorten(_strip_code_fences(previous_output or ""), 800)
    numbered_sentences = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sents))
    return (
        "이전 응답이 유효하지 않았습니다. 다시 시도해 주세요.\n"
        "당신의 출력은 반드시 지정된 형식을 엄격하게 따르는 단 하나의 JSON 객체여야 합니다.\n"
        "'first_sentence'와 'last_sentence' 값은 아래 제공된 입력 문장에서 정확히 복사해야 합니다.\n\n"
        f"### 이전의 유효하지 않은 출력 (일부):\n{prev}\n\n"
        f"### 입력 문장 (참고용):\n---\n{numbered_sentences}\n---\n출력 JSON:\n"
    )

def _map_plan_to_indices(plan: Any, sents: List[str], debug: bool) -> List[Tuple[int, int]]:
    """LLM이 출력한 (첫 문장, 끝 문장) 텍스트를 원본 문장 리스트의 인덱스로 변환"""
    if not isinstance(plan, dict) or "chunks" not in plan or not isinstance(plan["chunks"], list):
        return []

    indices_plan = []
    cursor = 0  # 동일 문장 반복 처리를 위한 검색 시작 위치
    
    for i, chunk_plan in enumerate(plan["chunks"]):
        if not isinstance(chunk_plan, dict): continue
        first_s = chunk_plan.get("first_sentence")
        last_s = chunk_plan.get("last_sentence")

        if not first_s or not last_s: continue

        try:
            # 시작 인덱스 찾기: cursor 위치부터 검색
            start_idx = sents.index(first_s, cursor)
            # 끝 인덱스 찾기: 시작 인덱스 위치부터 검색
            end_idx = sents.index(last_s, start_idx)
            indices_plan.append((start_idx, end_idx))
            cursor = end_idx + 1 # 다음 검색을 위해 cursor 업데이트
        except ValueError:
            if debug:
                print(f"[WARN] Failed to find sentence from plan chunk #{i}. First='{_shorten(first_s, 50)}', Last='{_shorten(last_s, 50)}'")
            continue # 문장을 찾지 못하면 해당 청크는 건너뜀

    return indices_plan

def _indices_to_chunks(indices_plan: List[Tuple[int, int]], text: str, sents: List[str], sent_spans: List[Tuple[int, int]]) -> List[ChunkMeta]:
    """변환된 인덱스 계획을 바탕으로 최종 ChunkMeta 리스트 생성"""
    chunks = []
    for chunk_index, (start_idx, end_idx) in enumerate(indices_plan):
        if end_idx < start_idx: continue # 유효하지 않은 인덱스

        char_start = sent_spans[start_idx][0]
        char_end = sent_spans[end_idx][1]
        chunk_text = text[char_start:char_end]
        if not chunk_text.strip(): continue

        word_start = len(text[:char_start].split())
        word_end = word_start + len(chunk_text.split()) - 1 if chunk_text.split() else word_start

        chunks.append(_make_chunk(chunk_index, chunk_text, char_start, char_end, word_start, word_end))
    return chunks

# =========================
# Unchanged Helper Functions
# =========================

def split_sentences_ko_en(text: str) -> List[str]:
    if not text.strip(): return []
    lines = re.split(r"\n+", text)
    sents: List[str] = []
    for line in lines:
        line = line.strip()
        if not line: continue
        parts = re.split(r"(?<=[\.!\?])\s+", line)
        sents.extend(p for p in parts if p.strip())
    return sents

def build_sentence_char_spans(text: str, sentences: List[str]) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    cursor = 0
    for s in sentences:
        try:
            start = text.index(s, cursor)
            end = start + len(s)
            spans.append((start, end))
            cursor = end
        except ValueError:
            spans.append((cursor, cursor))
    return spans

def _fallback_rule_based_chunks(text: str, sents: List[str], sent_spans: List[Tuple[int, int]], max_sentences_per_chunk: int = 8) -> List[ChunkMeta]:
    if not sents: return []
    step = max(3, min(10, max_sentences_per_chunk))
    chunks: List[ChunkMeta] = []
    for i in range(0, len(sents), step):
        start_idx, end_idx = i, min(i + step - 1, len(sents) - 1)
        char_start, char_end = sent_spans[start_idx][0], sent_spans[end_idx][1]
        chunk_text = text[char_start:char_end]
        if not chunk_text.strip(): continue
        word_start = len(text[:char_start].split())
        word_end = word_start + len(chunk_text.split()) - 1 if chunk_text.split() else word_start
        chunks.append(_make_chunk(len(chunks), chunk_text, char_start, char_end, word_start, word_end))
    return chunks

def _safe_parse_json(s: Any) -> Any:
    if not isinstance(s, str): return {}
    raw = _strip_code_fences(s.strip())
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return {}
    return {}

def _strip_code_fences(s: str) -> str:
    return re.sub(r"^```json|^```|```$", "", s, flags=re.MULTILINE).strip()

def _shorten(s: Optional[str], n: int) -> str:
    if not s: return ""
    return s if len(s) <= n else s[:n] + " …(truncated)"

def _make_chunk(chunk_index: int, text: str, char_start: int, char_end: int, word_start: int, word_end: int) -> ChunkMeta:
    return ChunkMeta(chunk_index, text, char_start, char_end, word_start, word_end)
