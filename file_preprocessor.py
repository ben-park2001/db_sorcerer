"""
파일 전처리기 (File Preprocessor)
- file_watcher로부터 파일 변경사항(C/U/D) 수신 및 처리
- 다른 노드의 파일 요청을 file_watcher에 중계
- 처리된 파일 정보를 다음 노드로 전송
"""

import os
import time
import json
import base64
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Union

import zmq
from FileProcessor.file_reader import read_file


class FilePreprocessor:
    def __init__(self, 
                 pull_port=5555,           # file_watcher PUSH 소켓으로부터 수신
                 file_request_port=5556,   # file_watcher ROUTER 소켓에 요청
                 rep_port=5557,           # 다른 노드들의 요청 처리
                 push_port=5558):         # 다음 노드로 전송
        
        self.pull_port = pull_port
        self.file_request_port = file_request_port
        self.rep_port = rep_port
        self.push_port = push_port
        
        # ZeroMQ context 생성
        self.context = zmq.Context()
        
        # PULL 소켓 (file_watcher로부터 파일 변경사항 수신)
        self.pull_socket = self.context.socket(zmq.PULL)
        self.pull_socket.connect(f"tcp://localhost:{self.pull_port}")
        
        # REQ 소켓 (file_watcher에게 파일 요청)
        self.req_socket = self.context.socket(zmq.REQ)
        self.req_socket.connect(f"tcp://localhost:{self.file_request_port}")
        
        # REP 소켓 (다른 노드들의 파일 요청 처리)
        self.rep_socket = self.context.socket(zmq.REP)
        self.rep_socket.bind(f"tcp://*:{self.rep_port}")
        
        # PUSH 소켓 (다음 노드로 전송)
        self.push_socket = self.context.socket(zmq.PUSH)
        self.push_socket.bind(f"tcp://*:{self.push_port}")
        
        # 실행 상태 플래그
        self.running = False
        
        print(f"🔧 File Preprocessor 초기화 완료")
        print(f"   📥 파일 변경사항 수신: PULL tcp://localhost:{self.pull_port}")
        print(f"   📤 파일 요청: REQ tcp://localhost:{self.file_request_port}")
        print(f"   🔄 파일 요청 처리: REP tcp://*:{self.rep_port}")
        print(f"   📤 다음 노드 전송: PUSH tcp://*:{self.push_port}")
    
    def _extract_file_content(self, file_path: str, encoded_content: Optional[str] = None) -> Optional[str]:
        """
        파일에서 텍스트 내용을 추출합니다.
        
        Args:
            file_path: 파일 경로
            encoded_content: base64 인코딩된 파일 내용 (있는 경우)
            
        Returns:
            추출된 텍스트 내용 또는 None
        """
        try:
            if encoded_content:
                # base64 디코딩된 내용으로 임시 파일 생성하여 처리
                decoded_content = base64.b64decode(encoded_content)
                temp_path = f"temp_{int(time.time())}_{os.path.basename(file_path)}"
                
                try:
                    with open(temp_path, 'wb') as f:
                        f.write(decoded_content)
                    
                    # file_reader로 내용 추출
                    content = read_file(temp_path)
                    return content
                    
                finally:
                    # 임시 파일 삭제
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            else:
                # 파일 경로로 직접 읽기
                if os.path.exists(file_path):
                    return read_file(file_path)
                else:
                    print(f"⚠️ 파일을 찾을 수 없습니다: {file_path}")
                    return None
                    
        except Exception as e:
            print(f"❌ 파일 내용 추출 실패 ({file_path}): {e}")
            return None
    
    def _process_file_change(self, message: Dict[str, Any]):
        """
        파일 변경사항을 처리합니다.
        
        Args:
            message: file_watcher로부터 받은 메시지
        """
        try:
            event_type = message.get('event_type')
            file_path = message.get('file_path')
            user_id = message.get('user_id')
            timestamp = message.get('timestamp')
            file_content = message.get('file_content')  # base64 encoded
            
            print(f"📄 파일 변경사항 처리: {file_path} ({event_type})")
            
            # 다음 노드로 전송할 메시지 구성
            processed_message = {
                'event_type': event_type,
                'file_path': file_path,
                'user_id': user_id,
                'timestamp': timestamp,
                'processed_timestamp': time.time(),
                'processor': 'file_preprocessor'
            }
            
            if event_type == 'delete':
                # 삭제: 파일 경로만 전송
                processed_message['content'] = None
                processed_message['status'] = 'deleted'
                
            elif event_type in ['create', 'update']:
                # 생성/수정: 파일 내용 추출
                extracted_content = self._extract_file_content(str(file_path), file_content)
                
                if extracted_content:
                    processed_message['content'] = extracted_content
                    processed_message['content_length'] = len(extracted_content)
                    processed_message['status'] = 'processed'
                    
                    # 수정인 경우 diff 정보도 포함
                    if event_type == 'update':
                        processed_message['diff_type'] = message.get('diff_type')
                        processed_message['diff_content'] = message.get('diff_content')
                        processed_message['relative_path'] = message.get('relative_path')
                        
                    print(f"✅ 파일 내용 추출 완료: {len(extracted_content)} 문자")
                else:
                    processed_message['content'] = None
                    processed_message['status'] = 'extraction_failed'
                    print(f"❌ 파일 내용 추출 실패: {file_path}")
            
            # 다음 노드로 전송
            self.push_socket.send_json(processed_message)
            print(f"📤 다음 노드로 전송 완료: {file_path}")
            
        except Exception as e:
            print(f"❌ 파일 변경사항 처리 중 오류: {e}")
    
    def _request_file_from_watcher(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        file_watcher에게 파일을 요청합니다.
        
        Args:
            file_path: 요청할 파일 경로
            
        Returns:
            file_watcher로부터 받은 응답 또는 None
        """
        try:
            # file_watcher에게 파일 요청
            request = {'file_path': file_path}
            self.req_socket.send_json(request)
            
            # 응답 수신 (타임아웃 설정)
            if self.req_socket.poll(timeout=5000):  # 5초 타임아웃
                response = self.req_socket.recv_json()
                if isinstance(response, dict):
                    return response
                else:
                    print(f"⚠️ 예상하지 못한 응답 형식: {response}")
                    return None
            else:
                print(f"⏰ file_watcher 응답 타임아웃: {file_path}")
                return None
                
        except Exception as e:
            print(f"❌ file_watcher 요청 중 오류: {e}")
            return None
    
    def _handle_file_request(self):
        """
        다른 노드들의 파일 요청을 처리합니다.
        """
        while self.running:
            try:
                # 파일 요청 수신 (타임아웃 설정)
                if self.rep_socket.poll(timeout=1000):  # 1초 타임아웃
                    request = self.rep_socket.recv_json()
                    
                    if not isinstance(request, dict):
                        print(f"⚠️ 잘못된 요청 형식: {request}")
                        self.rep_socket.send_json({
                            'status': 'error',
                            'error': '잘못된 요청 형식'
                        })
                        continue
                    
                    file_path = request.get('file_path')
                    if not file_path or not isinstance(file_path, str):
                        print(f"⚠️ 잘못된 파일 경로: {file_path}")
                        self.rep_socket.send_json({
                            'status': 'error',
                            'error': '유효하지 않은 파일 경로'
                        })
                        continue
                        
                    print(f"📥 파일 요청 수신: {file_path}")
                    
                    # file_watcher에게 파일 요청
                    watcher_response = self._request_file_from_watcher(file_path)
                    
                    if watcher_response and watcher_response.get('status') == 'success':
                        # 파일 내용 추출
                        file_content = watcher_response.get('file_content')
                        extracted_content = self._extract_file_content(file_path, file_content)
                        
                        if extracted_content:
                            response = {
                                'status': 'success',
                                'file_path': file_path,
                                'content': extracted_content,
                                'content_length': len(extracted_content),
                                'file_name': watcher_response.get('file_name'),
                                'file_size': watcher_response.get('file_size')
                            }
                            print(f"✅ 파일 요청 처리 완료: {file_path}")
                        else:
                            response = {
                                'status': 'error',
                                'error': '파일 내용 추출 실패',
                                'file_path': file_path
                            }
                    else:
                        response = {
                            'status': 'error',
                            'error': watcher_response.get('error', 'file_watcher 요청 실패') if watcher_response else 'file_watcher 응답 없음',
                            'file_path': file_path
                        }
                    
                    # 응답 전송
                    self.rep_socket.send_json(response)
                    
            except Exception as e:
                if self.running:  # 종료 중이 아닌 경우에만 에러 출력
                    print(f"❌ 파일 요청 처리 중 오류: {e}")
    
    def _listen_file_changes(self):
        """
        file_watcher로부터 파일 변경사항을 수신합니다.
        """
        while self.running:
            try:
                # 파일 변경사항 수신 (타임아웃 설정)
                if self.pull_socket.poll(timeout=1000):  # 1초 타임아웃
                    message = self.pull_socket.recv_json()
                    
                    if isinstance(message, dict):
                        self._process_file_change(message)
                    else:
                        print(f"⚠️ 잘못된 메시지 형식: {message}")
                    
            except Exception as e:
                if self.running:  # 종료 중이 아닌 경우에만 에러 출력
                    print(f"❌ 파일 변경사항 수신 중 오류: {e}")
    
    def start(self):
        """
        File Preprocessor를 시작합니다.
        """
        print("=" * 60)
        print("🔮 DB Sorcerer File Preprocessor 시작")
        print("=" * 60)
        
        self.running = True
        
        # 파일 변경사항 수신 스레드
        change_thread = threading.Thread(target=self._listen_file_changes, daemon=True)
        change_thread.start()
        
        # 파일 요청 처리 스레드
        request_thread = threading.Thread(target=self._handle_file_request, daemon=True)
        request_thread.start()
        
        try:
            print("\n📋 서비스 상태:")
            print(f"  • 파일 변경사항 수신: 활성화됨")
            print(f"  • 파일 요청 처리: 활성화됨")
            print(f"  • 다음 노드 전송: 대기 중")
            print("\n⏹️  종료하려면 Ctrl+C를 누르세요")
            print("-" * 60)
            
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n🛑 시스템 종료 중...")
            self.running = False
            
            # 스레드 종료 대기
            change_thread.join(timeout=1)
            request_thread.join(timeout=1)
            
        finally:
            # ZeroMQ 정리
            self.pull_socket.close()
            self.req_socket.close()
            self.rep_socket.close()
            self.push_socket.close()
            self.context.term()
            
            print("✅ File Preprocessor 종료 완료")


def main():
    """메인 실행 함수"""
    # 설정값들
    PULL_PORT = 5555      # file_watcher PUSH 소켓으로부터 수신
    FILE_REQUEST_PORT = 5556  # file_watcher ROUTER 소켓에 요청
    REP_PORT = 5557       # 다른 노드들의 요청 처리
    PUSH_PORT = 5558      # 다음 노드로 전송
    
    # FilePreprocessor 인스턴스 생성 및 시작
    preprocessor = FilePreprocessor(
        pull_port=PULL_PORT,
        file_request_port=FILE_REQUEST_PORT,
        rep_port=REP_PORT,
        push_port=PUSH_PORT
    )
    
    preprocessor.start()


if __name__ == "__main__":
    main()
