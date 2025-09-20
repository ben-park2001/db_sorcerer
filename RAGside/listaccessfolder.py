"""
클라이언트에서 user_id를 받아 Oracle과 통신하여 
사용자가 접근 가능한 폴더 구조를 반환하는 모듈
"""

import zmq
from typing import List, Set


class FolderAccessClient:
    def __init__(self, oracle_host="localhost", oracle_port=5560):
        """
        FolderAccessClient 초기화
        
        Args:
            oracle_host (str): Oracle 서버 호스트
            oracle_port (int): Oracle 서버 포트 (5560)
        """
        self.oracle_host = oracle_host
        self.oracle_port = oracle_port
        self.context = zmq.Context()
        
    def get_accessible_folders(self, user_id: str) -> List[str]:
        """
        사용자가 접근 가능한 폴더 목록을 가져온다
        
        Args:
            user_id (str): 사용자 ID
            
        Returns:
            List[str]: 접근 가능한 폴더 목록, 오류 시 빈 리스트
        """
        # REQ 소켓 생성
        socket = self.context.socket(zmq.REQ)
        
        # 타임아웃 설정 (5초)
        socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5초 수신 타임아웃
        socket.setsockopt(zmq.SNDTIMEO, 5000)  # 5초 송신 타임아웃
        
        socket.connect(f"tcp://{self.oracle_host}:{self.oracle_port}")
        
        try:
            # Oracle에 사용자 권한 요청
            request = {"user_id": user_id}
            socket.send_json(request)
            
            # Oracle로부터 응답 수신
            response = socket.recv_json()
            
            if response.get('status') == 'success':
                file_paths = response.get('pathlist', [])
                
                # 파일 경로에서 폴더 목록만 추출
                folders = self._extract_folders(file_paths)
                return folders
            else:
                print(f"[ERR] Oracle 오류: {response.get('error', 'Unknown error')}")
                return []
                
        except zmq.Again:
            print(f"[ERR] Oracle 서버 응답 타임아웃 (5초)")
            return []
        except zmq.ZMQError as e:
            print(f"[ERR] ZMQ 통신 오류: {e}")
            return []
        except Exception as e:
            print(f"[ERR] Oracle 통신 실패: {e}")
            return []
        finally:
            socket.close()
    
    def _extract_folders(self, file_paths: List[str]) -> List[str]:
        """
        파일 경로 리스트에서 폴더 목록만 추출한다
        
        Args:
            file_paths (List[str]): 파일 경로 리스트 (folder/filename 형태)
            
        Returns:
            List[str]: 폴더 목록
        """
        folders = set()
        
        for file_path in file_paths:
            if '/' in file_path:
                folder = file_path.split('/', 1)[0]
                folders.add(folder)
        
        return sorted(list(folders))
    
    def close(self):
        """컨텍스트 정리"""
        self.context.term()


def get_user_folders(user_id: str, oracle_host="localhost", oracle_port=5560) -> List[str]:
    """
    편의 함수: 사용자가 접근 가능한 폴더 목록을 가져온다
    
    Args:
        user_id (str): 사용자 ID
        oracle_host (str): Oracle 서버 호스트
        oracle_port (int): Oracle 서버 포트
        
    Returns:
        List[str]: 접근 가능한 폴더 목록
    """
    client = FolderAccessClient(oracle_host, oracle_port)
    try:
        return client.get_accessible_folders(user_id)
    finally:
        client.close()


if __name__ == "__main__":
    # 테스트 코드
    print("=== FolderAccessClient 테스트 ===")
    
    test_users = ["guest", "user1", "user2", "admin"]
    
    for user in test_users:
        print(f"\n사용자: {user}")
        
        try:
            folders = get_user_folders(user)
            if folders:
                print(f"접근 가능한 폴더: {folders}")
            else:
                print("접근 가능한 폴더 없음")
                
        except Exception as e:
            print(f"[ERR] 테스트 실패: {e}")
    
    print("\n=== 테스트 완료 ===")
