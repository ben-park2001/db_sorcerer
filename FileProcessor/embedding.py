# 1. text_chunker 에서 chunk들을 받아옴(LLM 이 세세하게 잘라준 것)
# 2. 각 chunk 에 대해, embedding 모델을 돌림

# embedding model 부르는 건, Models/embedding.py 쓰기로

# input : text chunker 에서 llm 이 세세하게 잘라준 chunk
# output : chunk 에 대한 embedding + 파일정보(파일 경로, 해당 파일의 어디부터 어디까지인지 등등)

# 이후에는 DB 쪽으로 보내야 함. 최상단의 DB 폴더 참조

#from ..Models.embedding import Embedding

# embedder.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Protocol, runtime_checkable, Optional

@dataclass
class FileChunkInfo:
    file_path: str
    filetype: str
    chunk_index: int
    char_start: int
    char_end: int
    word_start: int
    word_end: int

@dataclass
class EmbeddingRecord:
    vector: List[float]          # 임베딩 벡터
    text: str                    # 청크 원문
    meta: FileChunkInfo          # 파일/오프셋 메타
    extra: Optional[Dict[str, Any]] = None  # 필요 시 추가 정보

@runtime_checkable
class EmbeddingClient(Protocol):
    """
    임베딩 모델을 교체 가능하게 주입하기 위한 최소 인터페이스.
    예) Qwen3-Embedding-4B, OpenAI text-embedding-3-large 등
    """
    def embed(self, texts: List[str], **kwargs) -> List[List[float]]: ...

def build_embeddings(
    chunks: List[str],
    file_path: str,
    filetype: str,
    offsets: List[Dict[str, int]],
    embedder: EmbeddingClient,
    **embed_kwargs
) -> List[EmbeddingRecord]:
    """
    input:
      - chunks: 청크 텍스트 리스트
      - file_path/filetype: 원본 파일 정보
      - offsets: 각 청크의 오프셋 dict
        (예: {"chunk_index":0,"char_start":0,"char_end":123,"word_start":0,"word_end":20})
      - embedder: 임베딩 클라이언트 (주입식)
    output:
      - EmbeddingRecord 리스트
    """
    if not chunks:
        return []

    vectors = embedder.embed(chunks, **embed_kwargs)
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding output size mismatch")

    records: List[EmbeddingRecord] = []
    for i, (vec, text) in enumerate(zip(vectors, chunks)):
        off = offsets[i]
        info = FileChunkInfo(
            file_path=file_path,
            filetype=filetype,
            chunk_index=off.get("chunk_index", i),
            char_start=off.get("char_start", -1),
            char_end=off.get("char_end", -1),
            word_start=off.get("word_start", -1),
            word_end=off.get("word_end", -1),
        )
        records.append(EmbeddingRecord(
            vector=vec,
            text=text,
            meta=info,
            extra=None
        ))
    return records
