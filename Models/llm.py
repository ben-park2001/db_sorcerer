
import requests

base_model_url = "http://inputnameplz.iptime.org:12345/v1/chat/completions"
mini_model_url = "http://inputnameplz.iptime.org:12346/v1/chat/completions"

# base model
def LLM(message):
    data = {
        "messages": [
            {"role": "user", "content": message}
        ],
        "max_tokens": 100,
        "temperature": 0.1
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(base_model_url, json=data, headers=headers)

    if response.status_code == 200:
        result = response.json()["choices"][0]["message"]["content"]
        return result
    else:
        print(f"LLM API 호출 실패: {response.status_code}")
        return ""

# mini model
def LLM_small(message):
    data = {
        "messages": [
            {"role": "user", "content": message}
        ],
        "max_tokens": 100,
        "temperature": 0.1
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(base_model_url, json=data, headers=headers)

    if response.status_code == 200:
        result = response.json()["choices"][0]["message"]["content"]
        return result
    else:
        print(f"LLM API 호출 실패: {response.status_code}")
        return ""