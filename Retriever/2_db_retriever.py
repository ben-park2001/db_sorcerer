# query 와 embedding 을 받아서
# DB 에서 검색해옴
# embedding + TF-IDF ? 등등 정교하게

# input : query + embedding
# output : query + chunk data(파일 경로(파일명 포함), 해당 부분 원문 등)

from ..DB.dummy_db import RetrieverVectorSearchTest, RetrieverFileSearchTest

def db_retriever(query, embedding):
    vector_db_search_result = vector_db_search(query, embedding) # (filepath, content index)
    chunks = []
    for chunk_data in vector_db_search_result:
        chunk_content = file_db_retrieve(chunk_data)
        chunks.append([chunk_data, chunk_content])
    return query, chunks

def vector_db_search(query, embedding):
    vector_db_search_result = RetrieverVectorSearchTest(query, embedding) # (filepath, content index)
    return vector_db_search_result

def file_db_retrieve(chunk_data): # 파일 내용 전체 받아와서 잘라주는 함수
    file_path, chunk_index = chunk_data
    file_content= RetrieverFileSearchTest(file_path)
    chunk_content = file_content[0:2] # 원래는 chunk index 써야함
    return chunk_content