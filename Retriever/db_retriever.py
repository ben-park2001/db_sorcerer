# query 와 embedding 을 받아서
# ChromaDB 에서 검색해옴
# embedding + TF-IDF ? 등등 정교하게

# input : query + embedding
# output : query + chunk data(파일 경로(파일명 포함), 해당 부분 원문 등)

import chromadb
from chromadb.config import Settings

# ChromaDB client setup (assuming server running on localhost:8000)
chroma_client = chromadb.HttpClient(host="localhost", port=8000)

def db_retriever(query, embedding):
    vector_db_search_result = vector_db_search(query, embedding) # returns list of (filepath, start_index, end_index)
    chunks = []
    for chunk_data in vector_db_search_result:
        chunk_content = file_db_retrieve(chunk_data)
        chunks.append([chunk_data, chunk_content])  # [메타데이터, 실제내용]
    return query, chunks

def vector_db_search(query, embedding, collection_name="documents", n_results=5):
    """ChromaDB에서 유사한 벡터 검색 - 메타데이터만 반환"""
    try:
        collection = chroma_client.get_collection(name=collection_name)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["metadatas"]  # documents 제외, 메타데이터만 포함
        )
        
        # 결과 포맷: (filepath, start_index, end_index)
        search_results = []
        if results['metadatas']:
            for metadata in results['metadatas'][0]:
                filepath = metadata.get('filepath', 'unknown')
                start_index = metadata.get('start_index', 0)
                end_index = metadata.get('end_index', 0)
                search_results.append((filepath, start_index, end_index))
        
        return search_results
    except Exception as e:
        print(f"ChromaDB search error: {e}")
        return []

def file_db_retrieve(chunk_data): 
    """파일에서 실제 청크 내용을 가져옴 - 나중에 file processor 연동 예정"""
    filepath, start_index, end_index = chunk_data
    
    # TODO: file processor 모듈과 연동
    # 실제 구현 시: FileProcessor.read_chunk(filepath, start_index, end_index)
    
    # 현재는 dummy 구현
    dummy_content = f"[DUMMY] File: {filepath}, Chunk: {start_index}-{end_index}"
    
    try:
        # 간단한 파일 읽기 (나중에 file processor로 대체)
        with open(filepath, 'r', encoding='utf-8') as f:
            f.seek(start_index)
            actual_content = f.read(end_index - start_index)
            return actual_content if actual_content else dummy_content
    except Exception as e:
        print(f"File read error: {e}")
        return dummy_content