# 1. file_reader 에서 'text chunk'들을 받음
# 2. 각 chunk 를 llm 에 돌려서, 어느 부분을 기준으로 자를지 물어봄
# 3. chunk 를, 2번의 결과에 따라 자름

# llm 부르는 건, Models/llm.py 를 쓰기로
# from Models.embedding import ExampleFunction() 같은 느낌으로

# input : file reader 에서 크게 숭덩숭덩 자른 chunk
# output : LLM 의 결정에 따라 더 섬세하게 자른 chunk
#                (해당 chunk 가, 해당 파일의 어디부터 어디까지인지도 전달해줘야 함)

# GPT 초안

from ..Models.llm import LLM

# text_chunker.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Protocol, runtime_checkable
import json
import re

# ---- Interfaces ----

@runtime_checkable
class LLMClient(Protocol):
    """
    임의의 LLM 클라이언트를 주입하기 위한 최소 인터페이스.
    예) 믿:음 2.0, OpenAI, Bedrock 등
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
    # 선택적으로 LLM 응답 원문/JSON 등 디버그용
    llm_raw: Optional[str] = None
    mapping_info: Optional[Dict[str, Any]] = None

# ---- Public API ----

def llm_guided_sentence_chunk(
    text: str,
    llm: LLMClient,
    max_sentences_per_chunk: int = 20,
    system_hint: Optional[str] = None,
) -> ChunkingResult:
    """
    1) 텍스트를 문장 단위로 분할
    2) LLM에게 '의미 기준 청크'를 물어보되, 각 청크의 첫문장/끝문장 인덱스만 JSON으로 받음
    3) 해당 구간을 실제 문자열로 슬라이싱
    4) 각 청크의 문자/단어 오프셋 기록

    반환: ChunkMeta 리스트
    """
    sents = split_sentences_ko_en(text)
    sent_spans = build_sentence_char_spans(text, sents)  # [(start,end),...]

    prompt = _build_chunk_prompt(sents, max_sentences_per_chunk, system_hint)
    llm_out = llm.complete(prompt)

    # 기대 JSON 포맷:
    # {
    #   "chunks": [
    #     {"first_sentence_index": 0, "last_sentence_index": 5, "title": "개요"},
    #     {"first_sentence_index": 6, "last_sentence_index": 12, "title": "세부사항"},
    #     ...
    #   ]
    # }
    plan = _safe_parse_json(llm_out)
    chunk_plan = plan.get("chunks", []) if isinstance(plan, dict) else []

    chunks: List[ChunkMeta] = []
    for idx, c in enumerate(chunk_plan):
        try:
            a = int(c["first_sentence_index"])
            b = int(c["last_sentence_index"])
            if a < 0 or b < a or b >= len(sents):
                continue
        except Exception:
            continue

        char_start = sent_spans[a][0]
        char_end = sent_spans[b][1]
        text_slice = text[char_start:char_end]

        # 단어 오프셋(공백 분리 기준; 한국어에서도 rough 기준으로 기록)
        word_start = len(text[:char_start].split())
        word_end = word_start + len(text_slice.split()) - 1 if text_slice.strip() else word_start

        chunks.append(ChunkMeta(
            chunk_index=idx,
            text=text_slice,
            char_start=char_start,
            char_end=char_end,
            word_start=word_start,
            word_end=word_end
        ))

    return ChunkingResult(
        chunks=chunks,
        llm_raw=llm_out,
        mapping_info={"num_sentences": len(sents)}
    )

def split_sentences_ko_en(text: str) -> List[str]:
    """
    초경량 문장 분할기.
    - 한국어/영문 혼합 텍스트에 대해 마침표/물음표/느낌표/개행/한국어 종결 표현을 기준으로 분할
    - 실제 서비스에서는 kss 라이브러리 사용을 권장 (여기서는 의존성 최소화)
      pip install kss -> from kss import split_sentences
    """
    if not text.strip():
        return []

    # 1차 개행 분할
    lines = re.split(r"\n+", text)
    sents: List[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 한국어 종결(다./요./니다.) + 영문 구두점 기준
        parts = re.split(r"(?<=[\.!\?])\s+|(?<=[다요니다]\.)\s+", line)
        for p in parts:
            p = p.strip()
            if p:
                sents.append(p)
    return sents

def build_sentence_char_spans(text: str, sentences: List[str]) -> List[Tuple[int, int]]:
    """
    원문 내 각 문장의 (char_start, char_end) 위치를 계산.
    단순 검색이므로 동일 문장 반복 시 앞에서부터 매칭.
    """
    spans: List[Tuple[int, int]] = []
    cursor = 0
    for s in sentences:
        s_esc = re.escape(s.strip())
        m = re.search(s_esc, text[cursor:])
        if not m:
            # fallback: 근사 매칭 실패 시 길이 기반 추정
            start = cursor
            end = min(len(text), start + len(s))
        else:
            start = cursor + m.start()
            end = cursor + m.end()
        spans.append((start, end))
        cursor = end
    return spans

def _build_chunk_prompt(sentences: List[str], max_sentences_per_chunk: int, system_hint: Optional[str]) -> str:
    """
    모델 컨텍스트 부담을 줄이기 위해 앞부분 몇십 문장만 요약 표본으로 제공하는 등의 최적화는
    호출부에서 결정. 스켈레톤에서는 전량을 문자열화(현업에선 길이에 따라 슬라이싱).
    """
    # 한 문장당 한 줄, 길면 앞 300자 truncate
    lines = []
    for i, s in enumerate(sentences):
        s_short = (s[:300] + "…") if len(s) > 300 else s
        lines.append(f"[{i}] {s_short}")
    guideline = system_hint or "논리/주제 전환을 기준으로 묶고, 각 청크는 5~20문장 범위로 제안해 주세요."

    return (
        "다음은 문장 리스트입니다. 의미 단위로 청크를 제안하고 JSON만 반환하세요.\n"
        f"가이드라인: {guideline}\n"
        "응답 형식(JSON): {\"chunks\": [{\"first_sentence_index\": int, \"last_sentence_index\": int, \"title\": str}]}\n"
        + "\n".join(lines)
    )

def _safe_parse_json(s: str) -> Any:
    # 코드블록/잡텍스트 감싸짐 방지
    s = s.strip()
    s = re.sub(r"^```json|^```|```$", "", s, flags=re.MULTILINE).strip()
    try:
        return json.loads(s)
    except Exception:
        # 최후: 중괄호만 추출 시도
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}
