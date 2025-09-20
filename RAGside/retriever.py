"""
파일 검색기 (File Retriever)
- file_preprocessor에게 파일을 요청하고 텍스트 내용을 받아오는 간단한 클라이언트
- query로 관련 chunk들을 검색하고 reranking하여 반환
"""

import zmq
import json
import sys
import os
from typing import Optional, Dict, Any, List

from Models.embedding import Embedding
from Models.reranker import Reranker
from db import search_data


class FileRetriever:
    """파일을 요청하고 내용을 받아오는 간단한 클라이언트"""
    
    def __init__(self, preprocessor_host="localhost", preprocessor_port=5557, oracle_host="localhost", oracle_port=5559, user_id=None):
        """
        Args:
            preprocessor_host: file_preprocessor 서버 주소
            preprocessor_port: file_preprocessor 서버 포트 (기본값: 5557)
            oracle_host: oracle 서버 주소 (access 함수용)
            oracle_port: oracle 서버 포트 (기본값: 5559)
            user_id: 사용자 ID (권한 확인용, 필수)
        """
        if not user_id:
            raise ValueError("사용자 ID가 필요합니다. 접근이 거부되었습니다.")
        
        self.preprocessor_host = preprocessor_host
        self.preprocessor_port = preprocessor_port
        self.oracle_host = oracle_host
        self.oracle_port = oracle_port
        self.user_id = user_id
        
        # ZeroMQ 컨텍스트와 소켓 초기화
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{preprocessor_host}:{preprocessor_port}")
        
        print(f"📡 FileRetriever 연결됨: tcp://{preprocessor_host}:{preprocessor_port}")
        print(f"🔑 Oracle 연결됨: tcp://{oracle_host}:{oracle_port}")
        print(f"🗄️ db.py 연결됨")
        if user_id:
            print(f"👤 사용자 ID: {user_id}")
    
    def _get_user_accessible_files(self, user_id: str) -> List[str]:
        """
        ZMQ 통신을 통해 oracle.py의 access 함수를 호출하여 
        사용자 ID를 기반으로 접근 가능한 파일 목록을 반환합니다.
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            접근 가능한 파일 경로 목록 (빈 리스트 가능)
        """
        if not user_id:
            return []
        
        try:
            # Oracle 서버에 REQ 소켓으로 연결
            oracle_socket = self.context.socket(zmq.REQ)
            oracle_socket.connect(f"tcp://{self.oracle_host}:{self.oracle_port}")
            
            # access 요청 전송
            request = {"user_id": user_id}
            oracle_socket.send_json(request)
            
            # 응답 수신 (5초 타임아웃)
            if oracle_socket.poll(timeout=5000):
                response = oracle_socket.recv_json()
                
                if response.get('status') == 'success':
                    pathlist = response.get('pathlist', [])
                    print(f"🔑 Oracle에서 권한 정보 수신: {len(pathlist)}개 파일")
                    oracle_socket.close()
                    return pathlist
                else:
                    error_msg = response.get('error', '알 수 없는 오류')
                    print(f"❌ Oracle 권한 조회 실패: {error_msg}")
                    oracle_socket.close()
                    return []
            else:
                print(f"⏰ Oracle 응답 타임아웃")
                oracle_socket.close()
                return []
                
        except Exception as e:
            print(f"❌ Oracle 통신 오류: {e}")
            return []
    
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
            embeddings = Embedding(query)
            # Embedding() 함수는 리스트의 리스트를 반환하므로 첫 번째 요소만 가져옴
            return embeddings[0] if embeddings and len(embeddings) > 0 else None
        except Exception as e:
            print(f"❌ Query embedding 생성 실패: {e}")
            return None
    
    def _search_similar_chunks(self, query_embedding: List[float], n_results: int = 10, pathlist=None) -> List[Dict]:
        """db.py를 사용하여 유사한 chunk들을 검색합니다."""
        try:
            results = search_data(query_embedding, n_results=n_results, pathlist=pathlist)
            
            chunks = []
            for i, (file_path, start_idx, end_idx) in enumerate(results):
                chunks.append({
                    'file_path': file_path,
                    'start_pos': start_idx,  # start_idx를 start_pos로 매핑
                    'end_pos': end_idx,      # end_idx를 end_pos로 매핑
                    'distance': 0  # db.py에서는 distance 정보를 제공하지 않음
                })
            
            print(f"🔍 db.py 검색 완료: {len(chunks)}개 chunk 발견")
            return chunks
            
        except Exception as e:
            print(f"❌ db.py 검색 실패: {e}")
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
    
    def search_chunks(self, query: str, top_n: int = 5) -> List[Dict[str, str]]:
        """
        query로 관련 chunk들을 검색하고 reranking하여 상위 n개를 반환합니다.
        
        Args:
            query: 검색할 query 문장
            top_n: 반환할 상위 chunk 개수
            
        Returns:
            상위 n개 chunk 정보들의 리스트 (각 항목은 {'text': chunk 원문, 'file_name': 파일명} 형태)
        """
        try:
            print(f"🔍 검색 시작: '{query}'")
            
            # 1. Query embedding 생성
            query_embedding = self._get_query_embedding(query)
            if not query_embedding:
                return []
            
            # 2. 사용자 권한에 따른 pathlist 생성
            pathlist = self._get_user_accessible_files(self.user_id)
            if not pathlist:
                print(f"❌ DB 접근 권한이 없습니다. 사용자: {self.user_id}")
                return []
            print(f"� 권한 필터링: {len(pathlist)}개 파일에 대해서만 검색")
            
            # 3. ChromaDB에서 유사한 chunk들 검색
            similar_chunks = self._search_similar_chunks(query_embedding, n_results=top_n*2, pathlist=pathlist)
            if not similar_chunks:
                return [{'text': '검색된 문서가 없습니다', 'file_name': ''}]
            
            # 4. 각 chunk의 원문과 파일명 추출
            chunk_data = []
            for chunk in similar_chunks:
                chunk_text = self._extract_chunk_text(
                    chunk['file_path'], 
                    chunk['start_pos'], 
                    chunk['end_pos']
                )
                if chunk_text:
                    import os
                    file_name = os.path.basename(chunk['file_path'])
                    chunk_data.append({
                        'text': chunk_text,
                        'file_name': file_name,
                        'file_path': chunk['file_path']  # reranking을 위해 임시 저장
                    })
            
            if not chunk_data:
                return []
            
            # 5. Reranking으로 상위 n개 선별
            try:
                # reranking을 위해 텍스트만 추출
                chunk_texts = [item['text'] for item in chunk_data]
                reranked_chunks = Reranker(query, chunk_texts, top_n=top_n)['results']
                
                # reranking 결과를 바탕으로 원본 chunk_data에서 해당하는 항목들을 찾아서 반환
                result_chunks = []
                for reranked_chunk in reranked_chunks:
                    reranked_text = reranked_chunk['document']
                    # 원본 chunk_data에서 해당 텍스트를 찾기
                    for chunk_item in chunk_data:
                        if chunk_item['text'] == reranked_text:
                            result_chunks.append({
                                'text': chunk_item['text'],
                                'file_name': chunk_item['file_name']
                            })
                            break
                
                print(f"✅ 검색 완료: {len(result_chunks)}개 chunk 반환")
                return result_chunks
            except Exception as e:
                print(f"⚠️ Reranking 실패, 원본 순서로 반환: {e}")
                # reranking 실패시 원본 순서로 반환 (file_path 제거)
                return [{'text': item['text'], 'file_name': item['file_name']} for item in chunk_data[:top_n]]
                
        except Exception as e:
            print(f"❌ 검색 중 오류: {e}")
            return []

