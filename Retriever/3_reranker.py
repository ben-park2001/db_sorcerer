# query 랑 chunk data 들 받아서
# reranking 함(score 를 내줌)

# input : query, chunk data
# output : chunk data(파일 경로, chunk의 원문 내용)+score 의 배열

from ..Models.reranker import Reranker

def rerank_score(query, chunks):
    scores = Reranker(query, chunks)
    for i, chunk in enumerate(chunks):
        chunk.append(scores[i])
    return chunks