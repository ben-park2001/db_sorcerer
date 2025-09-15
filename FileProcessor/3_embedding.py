# 1. text_chunker 에서 chunk들을 받아옴(LLM 이 세세하게 잘라준 것)
# 2. 각 chunk 에 대해, embedding 모델을 돌림

# embedding model 부르는 건, Models/embedding.py 쓰기로

# input : text chunker 에서 llm 이 세세하게 잘라준 chunk
# output : chunk 에 대한 embedding + 파일정보(파일 경로, 해당 파일의 어디부터 어디까지인지 등등)

# 이후에는 DB 쪽으로 보내야 함. 최상단의 DB 폴더 참조

from ..Models.embedding import Embedding