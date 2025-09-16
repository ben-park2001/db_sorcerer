
import requests

url = "http://inputnameplz.iptime.org:12345/v1/chat/completions"

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

    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        result = response.json()["choices"][0]["message"]["content"]
        # print(result["choices"][0]["message"]["content"])

    return result