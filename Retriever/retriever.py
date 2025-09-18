"""
파일 검색기 (File Retriever)
- file_preprocessor에게 파일을 요청하고 텍스트 내용을 받아오는 간단한 클라이언트
- query로 관련 chunk들을 검색하고 reranking하여 반환
"""

import zmq
import json
import chromadb
from typing import Optional, Dict, Any, List
from ..Models.embedding import Embedding
from ..Models.reranker import Reranker


class FileRetriever:
    """파일을 요청하고 내용을 받아오는 간단한 클라이언트"""
    
    def __init__(self, preprocessor_host="localhost", preprocessor_port=5557, 
                 chroma_path="./chroma_db", collection_name="documents"):
        """
        Args:
            preprocessor_host: file_preprocessor 서버 주소
            preprocessor_port: file_preprocessor 서버 포트 (기본값: 5557)
            chroma_path: ChromaDB 저장 경로
            collection_name: ChromaDB 컬렉션 이름
        """
        self.preprocessor_host = preprocessor_host
        self.preprocessor_port = preprocessor_port
        
        # ZeroMQ 컨텍스트와 소켓 초기화
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{preprocessor_host}:{preprocessor_port}")
        
        # ChromaDB 초기화
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)
        
        print(f"📡 FileRetriever 연결됨: tcp://{preprocessor_host}:{preprocessor_port}")
        print(f"🗄️ ChromaDB 연결됨: {chroma_path}/{collection_name}")
    
    def get_file_content(self, file_path: str, timeout_ms: int = 5000) -> Optional[str]:
        """
        파일 경로를 전송하고 텍스트 내용을 받아옵니다.
        
        Args:
            file_path: 요청할 파일의 경로
            timeout_ms: 응답 대기 시간 (밀리초, 기본값: 5초)
            
        Returns:
            파일의 텍스트 내용 또는 None (실패시)
        """
        try:
            print(f"📄 파일 요청: {file_path}")
            
            # 요청 메시지 구성
            request = {"file_path": file_path}
            
            # 요청 전송
            self.socket.send_json(request)
            
            # 응답 대기 (타임아웃 설정)
            if self.socket.poll(timeout=timeout_ms):
                response = self.socket.recv_json()
                
                # 응답 처리
                if isinstance(response, dict) and response.get("status") == "success":
                    content = response.get("content")
                    content_length = response.get("content_length", 0)
                    print(f"✅ 파일 내용 수신 완료: {content_length} 문자")
                    return str(content) if content is not None else None
                elif isinstance(response, dict):
                    error_msg = response.get("error", "알 수 없는 오류")
                    print(f"❌ 파일 요청 실패: {error_msg}")
                    return None
                else:
                    print(f"❌ 잘못된 응답 형식: {response}")
                    return None
            else:
                print(f"⏰ 응답 타임아웃: {file_path}")
                return None
                
        except Exception as e:
            print(f"❌ 파일 요청 중 오류: {e}")
            return None
    
    def close(self):
        """연결을 종료합니다."""
        self.socket.close()
        self.context.term()
        print("🔌 FileRetriever 연결 종료됨")
    
    def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """query 문장의 embedding을 생성합니다."""
        try:
            return Embedding(query)
        except Exception as e:
            print(f"❌ Query embedding 생성 실패: {e}")
            return None
    
    def _search_similar_chunks(self, query_embedding: List[float], n_results: int = 10) -> List[Dict]:
        """ChromaDB에서 유사한 chunk들을 검색합니다."""
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            chunks = []
            if results['ids'] and results['ids'][0]:
                for i, chunk_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    chunks.append({
                        'file_path': metadata.get('file_path', ''),
                        'start_pos': metadata.get('start_pos', 0),
                        'end_pos': metadata.get('end_pos', 0),
                        'distance': results['distances'][0][i] if results['distances'] else 0
                    })
            
            print(f"🔍 ChromaDB 검색 완료: {len(chunks)}개 chunk 발견")
            return chunks
            
        except Exception as e:
            print(f"❌ ChromaDB 검색 실패: {e}")
            return []
    
    def _extract_chunk_text(self, file_path: str, start_pos: int, end_pos: int) -> Optional[str]:
        """파일에서 특정 위치의 chunk 원문을 추출합니다."""
        try:
            file_content = self.get_file_content(file_path)
            if file_content:
                return file_content[start_pos:end_pos]
            return None
        except Exception as e:
            print(f"❌ Chunk 추출 실패 ({file_path}): {e}")
            return None
    
    def search_chunks(self, query: str, top_n: int = 5) -> List[str]:
        """
        query로 관련 chunk들을 검색하고 reranking하여 상위 n개를 반환합니다.
        
        Args:
            query: 검색할 query 문장
            top_n: 반환할 상위 chunk 개수
            
        Returns:
            상위 n개 chunk 원문들의 리스트
        """
        try:
            print(f"🔍 검색 시작: '{query}'")
            
            # 1. Query embedding 생성
            query_embedding = self._get_query_embedding(query)
            if not query_embedding:
                return []
            
            # 2. ChromaDB에서 유사한 chunk들 검색
            similar_chunks = self._search_similar_chunks(query_embedding, n_results=top_n*2)
            if not similar_chunks:
                return []
            
            # 3. 각 chunk의 원문 추출
            chunk_texts = []
            for chunk in similar_chunks:
                chunk_text = self._extract_chunk_text(
                    chunk['file_path'], 
                    chunk['start_pos'], 
                    chunk['end_pos']
                )
                if chunk_text:
                    chunk_texts.append(chunk_text)
            
            if not chunk_texts:
                return []
            
            # 4. Reranking으로 상위 n개 선별
            try:
                reranked_chunks = Reranker(query, chunk_texts, top_n=top_n)
                print(f"✅ 검색 완료: {len(reranked_chunks)}개 chunk 반환")
                return reranked_chunks
            except Exception as e:
                print(f"⚠️ Reranking 실패, 원본 순서로 반환: {e}")
                return chunk_texts[:top_n]
                
        except Exception as e:
            print(f"❌ 검색 중 오류: {e}")
            return []

