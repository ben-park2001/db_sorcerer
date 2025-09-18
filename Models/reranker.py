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

# 사용 예시
# query = "파이썬 프로그래밍 학습"
# documents = [
#     "자바스크립트는 웹 개발에 사용되는 언어입니다",
#     "파이썬은 데이터 분석과 머신러닝에 널리 사용됩니다",
#     "C++은 시스템 프로그래밍에 적합한 언어입니다",
#     "파이썬 튜토리얼과 예제를 통해 프로그래밍을 배워보세요"
# ]
query = "Python programming tutorial"
documents = [
    "JavaScript is a programming language primarily used for web development",
    "Python is widely used for data analysis and machine learning applications",
    "C++ is a powerful language suitable for system programming and performance-critical applications",
    "Learn Python programming with step-by-step tutorials and practical examples",
    "Java is an object-oriented programming language used for enterprise applications",
    "HTML and CSS are markup languages for creating web pages",
    "Python offers excellent libraries like pandas, numpy, and scikit-learn for data science"
]
result = Reranker(query, documents, top_n=3)
print(result)
if result:
    print("Reranking 결과:")
    for item in result.get('results', []):
        print(f"순위: {item.get('index', 0) + 1}")
        print(f"점수: {item.get('relevance_score', 0):.4f}")
        print(f"문서: {documents[item.get('index', 0)]}")
        print()