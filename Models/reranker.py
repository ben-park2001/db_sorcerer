# import numpy as np



# def Reranker(query, chunks):
#     scores = np.zeros(len(chunks))
#     return scores



import requests
import json

model="Qwen/Qwen3-Reranker-0.6B"
server_url="http://inputnameplz.iptime.org:12347"

def Reranker(query, documents,top_n=None):
    """
    vLLM 서버의 rerank API를 사용하여 문서를 재정렬합니다.
    """
    url = server_url+"/v1/rerank"
    
    payload = {
        "model": model,
        "query": query,
        "documents": documents
    }
    
    if top_n is not None:
        payload["top_n"] = top_n
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    return response.json()