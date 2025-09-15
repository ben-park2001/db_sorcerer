# 1. file_reader 에서 'text chunk'들을 받음
# 2. 각 chunk 를 llm 에 돌려서, 어느 부분을 기준으로 자를지 물어봄
# 3. chunk 를, 2번의 결과에 따라 자름

# llm 부르는 건, Models/llm.py 를 쓰기로
# from Models.embedding import ExampleFunction() 같은 느낌으로

# input : file reader 에서 크게 숭덩숭덩 자른 chunk
# output : LLM 의 결정에 따라 더 섬세하게 자른 chunk
#                (해당 chunk 가, 해당 파일의 어디부터 어디까지인지도 전달해줘야 함)

from ..Models.llm import LLM