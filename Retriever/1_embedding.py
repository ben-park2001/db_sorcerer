# 일단 Retrieving Tool 만 만들고, llm 이랑 CoT 는 Frontend+LLM 하면서 진행할 예정

# embedding 만들기

# input : query 문장 (llm 이 해줄거임)
# output : query 문장 / embedding vector

from ..Models.embedding import Embedding

def query_embedding(query):
    embedding_vector = Embedding(query)
    return query, embedding_vector