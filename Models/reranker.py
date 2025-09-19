import requests


def Reranker(query, documents, top_n=None):
    """
    LLM을 이용한 reranker 함수
    query와 각 document의 연관성을 LLM으로 평가하여 점수를 반환
    """
    rerank_url = "http://inputnameplz.iptime.org:12346/v1/chat/completions"
    
    # 각 document에 대한 프롬프트 생성
    batch_messages = []
    for doc in documents:
        prompt = f"Rate the relevance between the query and context with a number.\nquery: {query}\ncontext: {doc}\nOutput only a single number."
        batch_messages.append({
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 3,
            "temperature": 0
        })
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # 배치 요청 전송 (각각 개별 요청으로 처리)
    scores = []
    for message_data in batch_messages:
        response = requests.post(rerank_url, json=message_data, headers=headers)
        
        if response.status_code == 200:
            result = response.json()["choices"][0]["message"]["content"].strip()
            print(result)
            try:
                # 숫자만 추출하여 점수로 사용
                score = float(result)
                scores.append(score)
            except ValueError:
                # 숫자로 변환 실패 시 0점 처리
                scores.append(0.0)
        else:
            scores.append(0.0)
    
    # 점수와 문서 인덱스를 함께 정렬
    scored_docs = list(enumerate(scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    
    # top_n이 지정된 경우 상위 n개만 반환
    if top_n is not None:
        scored_docs = scored_docs[:top_n]
    
    # reranker.py와 동일한 형태로 결과 반환
    results = []
    for idx, score in scored_docs:
        results.append({
            "index": idx,
            "relevance_score": score,
            "document": documents[idx]
        })

    return {"results": results}