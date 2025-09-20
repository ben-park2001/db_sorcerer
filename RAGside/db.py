import chromadb

client = chromadb.HttpClient(host='localhost', port=8000)
collection = client.get_or_create_collection("sentences")

def create_data(file_path, start_idx, end_idx, embedding):
    doc_id = f"{file_path}_{start_idx}_{end_idx}"
    collection.add(
        ids=[doc_id],
        embeddings=[embedding],
        metadatas=[{"file_path": file_path, "start_idx": start_idx, "end_idx": end_idx}]
    )

def delete_data(file_path):
    collection.delete(where={"file_path": file_path})

def search_data(query_embedding, n_results=10, pathlist=None):
    if pathlist:
        # pathlist가 있으면 해당 파일들만 검색
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where={"file_path": {"$in": pathlist}}
        )
        return [(meta["file_path"], meta["start_idx"], meta["end_idx"]) 
                for meta in results["metadatas"][0]]
    else:
        # pathlist가 없으면 권한이 없으므로 빈 리스트 반환
        return []