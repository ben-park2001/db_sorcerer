import numpy as np
import requests
import json


server_url = "http://inputnameplz.iptime.org:12347"  # vLLM 서버 주소
model_name = "Qwen/Qwen3-Embedding-0.6B"  # 사용하는 임베딩 모델명


def Embedding(texts):
    url = f"{server_url}/v1/embeddings"
    
    payload = {
        "model": model_name,
        "input": texts
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        # Extract only the embedding vectors and return as a list of arrays
        embeddings = [item['embedding'] for item in result['data']]
        return embeddings
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")
