"""
통합 파일 감시 및 전송 시스템
- 파일 생성/수정/삭제 감시
- 파일 전송 기능
- 파일 요청 처리 HTTP 서버
"""

import os
import time
import getpass
import threading
import json
import base64
from pathlib import Path

import zmq
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import git
from git import Repo, InvalidGitRepositoryError
from accessDB import DummyAuthDB


class FileWatcher:
    def __init__(self, watch_folder, push_port=5555, router_port=5556, access_port=5559):
        self.watch_folder = Path(watch_folder)
        self.push_port = push_port
        self.router_port = router_port
        self.access_port = access_port
        self.user_id = getpass.getuser()
        
        # ZeroMQ context 생성
        self.context = zmq.Context()
        
        # PUSH 소켓 (파일 변경사항 전송용)
        self.push_socket = self.context.socket(zmq.PUSH)
        self.push_socket.bind(f"tcp://localhost:{self.push_port}")
        
        # ROUTER 소켓 (파일 요청 처리용)
        self.router_socket = self.context.socket(zmq.ROUTER)
        self.router_socket.bind(f"tcp://*:{self.router_port}")
        
        # REP 소켓 (access 함수 처리용)
        self.rep_socket = self.context.socket(zmq.REP)
        self.rep_socket.bind(f"tcp://*:{self.access_port}")
        
        # 감시 대상 파일 확장자
        self.allowed_extensions = {'.docx', '.pdf', '.hwp', '.txt'}
        
        # Observer 설정
        self.observer = Observer()
        
        # Git 저장소 설정
        self.repo = None
        self._init_git_repo()
        
        # Router 처리를 위한 스레드 플래그
        self.router_running = False
        self.access_running = False

        self.auth_db = DummyAuthDB()
        
    def _init_git_repo(self):
        """Git 저장소 초기화"""
        try:
            # 폴더 생성 (Git 초기화 전에 필요)
            self.watch_folder.mkdir(exist_ok=True)
            
            # 기존 Git 저장소인지 확인
            try:
                self.repo = Repo(str(self.watch_folder))
                print(f"✅ 기존 Git 저장소 연결: {self.watch_folder}")
            except InvalidGitRepositoryError:
                # Git 저장소가 아닌 경우 새로 초기화
                self.repo = Repo.init(str(self.watch_folder))
                print(f"🆕 새 Git 저장소 초기화: {self.watch_folder}")
                
                # 초기 커밋 생성 (gitignore 추가)
                gitignore_path = self.watch_folder / ".gitignore"
                with open(gitignore_path, 'w', encoding='utf-8') as f:
                    f.write("# 임시 파일\n*.tmp\n*.swp\n*.swo\n")
                
                self.repo.index.add([".gitignore"])
                self.repo.index.commit(f"Initial commit by {self.user_id}")
                
        except Exception as e:
            print(f"❌ Git 저장소 초기화 실패: {e}")
            self.repo = None
    
    def _is_target_file(self, file_path):
        """감시 대상 파일인지 확인"""
        _, ext = os.path.splitext(file_path)
        return ext.lower() in self.allowed_extensions
    
    def _get_file_diff(self, file_path):
        """파일의 Git diff 정보를 가져오기"""
        if not self.repo:
            return None
            
        try:
            # 파일 경로를 상대 경로로 변환
            rel_path = os.path.relpath(file_path, self.watch_folder)
            
            # 스테이징된 파일과 현재 파일의 차이점 확인
            try:
                # HEAD와 현재 작업 디렉터리의 차이점
                diff = self.repo.git.diff('HEAD', rel_path)
                if diff:
                    return {
                        'type': 'modification',
                        'diff': diff,
                        'file_path': rel_path
                    }
                
                # 새 파일인지 확인 (아직 추적되지 않은 파일)
                untracked_files = self.repo.untracked_files
                if rel_path in untracked_files:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    return {
                        'type': 'new_file',
                        'diff': f"--- /dev/null\n+++ b/{rel_path}\n" + 
                               "\n".join([f"+{line}" for line in content.split('\n')]),
                        'file_path': rel_path
                    }
                        
            except Exception as e:
                print(f"⚠️ diff 생성 중 오류: {e}")
                return None
                
        except Exception as e:
            print(f"❌ Git diff 처리 실패: {e}")
            return None
        
        return None
    
    def _commit_file_change(self, file_path, event_type):
        """파일 변경사항을 Git에 커밋"""
        if not self.repo:
            return False
            
        try:
            rel_path = os.path.relpath(file_path, self.watch_folder)
            
            if event_type == 'delete':
                # 파일 삭제의 경우
                try:
                    self.repo.index.remove([rel_path])
                    commit_msg = f"Delete {rel_path} by {self.user_id}"
                    self.repo.index.commit(commit_msg)
                    print(f"📝 Git 커밋: {commit_msg}")
                    return True
                except Exception as e:
                    print(f"⚠️ 삭제 커밋 실패: {e}")
                    return False
            else:
                # 파일 생성/수정의 경우
                if os.path.exists(file_path):
                    self.repo.index.add([rel_path])
                    
                    if event_type == 'create':
                        commit_msg = f"Add {rel_path} by {self.user_id}"
                    else:  # update
                        commit_msg = f"Update {rel_path} by {self.user_id}"
                    
                    self.repo.index.commit(commit_msg)
                    print(f"📝 Git 커밋: {commit_msg}")
                    return True
                    
        except Exception as e:
            print(f"❌ Git 커밋 실패: {e}")
            return False
        
        return False
    
    def _send_file(self, file_path, event_type):
        """파일을 서버로 전송"""
        try:
            # 절대 경로를 상대 경로로 변환
            rel_path = os.path.relpath(file_path, self.watch_folder)
            
            # 폴더명 추출하여 좋아요 사용자 정보 조회
            folder_name = rel_path.split('/')[0] if '/' in rel_path else rel_path.split('\\')[0]
            liked_users = self.auth_db.get_folder_liked_users(folder_name)
            
            # Git diff 정보 수집 (update인 경우)
            diff_info = None
            if event_type == 'update':
                diff_info = self._get_file_diff(file_path)
            
            # Git 커밋 수행
            commit_success = self._commit_file_change(file_path, event_type)
            
            # 전송할 메시지 구성
            message = {
                'event_type': event_type,
                'user_id': self.user_id,
                'file_path': rel_path,
                'liked_users': liked_users,
                'git_committed': commit_success,
                'timestamp': time.time()
            }
            
            if event_type == 'delete':
                # 삭제 이벤트: 메타데이터만 전송
                message['file_content'] = None
            else:
                # 생성/수정 이벤트: 파일 내용을 base64로 인코딩하여 전송
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'rb') as file:
                            file_content = file.read()
                            message['file_content'] = base64.b64encode(file_content).decode('utf-8')
                            message['file_size'] = len(file_content)
                    except Exception as e:
                        print(f"⚠️ 파일 읽기 실패: {e}")
                        message['file_content'] = None
                else:
                    print(f"파일을 찾을 수 없습니다: {file_path}")
                    return
            
            # diff 정보가 있으면 추가
            if diff_info:
                message['diff_type'] = diff_info['type']
                message['diff_content'] = diff_info['diff']
                message['relative_path'] = diff_info['file_path']
            
            # ZeroMQ PUSH로 메시지 전송
            self.push_socket.send_json(message)
            
            # 상세한 전송 정보 출력
            print(f"📤 [SEND -> file_preprocessor] 파일 전송 성공: {file_path}")
            print(f"   📋 이벤트 타입: {event_type}")
            print(f"   👤 사용자: {self.user_id}")
            print(f"   📅 타임스탬프: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(message['timestamp']))}")
            
            if event_type != 'delete':
                file_size = message.get('file_size', 0)
                print(f"   📏 파일 크기: {file_size:,} bytes")
                print(f"   🔒 Base64 인코딩: {'✅' if message.get('file_content') else '❌'}")
            
            print(f"   🌿 Git 커밋: {'✅' if commit_success else '❌'}")
            
            if diff_info:
                print(f"   📊 Diff 정보: {diff_info['type']} ({len(diff_info['diff'])} chars)")
            
            print(f"   🚀 전송 포트: tcp://localhost:{self.push_port}")
            print("   " + "-" * 50)
                
        except Exception as e:
            print(f"❌ 파일 전송 중 오류 발생: {e}")
    
    def _handle_file_request_router(self):
        """ZeroMQ ROUTER 소켓으로 파일 요청 처리"""
        self.router_running = True
        print(f"🚀 파일 요청 서버 시작: tcp://*:{self.router_port}")
        
        while self.router_running:
            try:
                # 메시지 수신 (non-blocking with timeout)
                if self.router_socket.poll(timeout=1000):  # 1초 타임아웃
                    # [client_id, empty, request_message]
                    client_id = self.router_socket.recv()
                    empty = self.router_socket.recv()
                    request_data = self.router_socket.recv_json()
                    
                    print(f"📥 파일 요청 수신: {request_data}")
                    
                    # 응답 메시지 구성
                    response = self._process_file_request(request_data)
                    
                    # 클라이언트에게 응답 전송
                    try:
                        response_json = json.dumps(response, ensure_ascii=False)
                        self.router_socket.send_multipart([
                            client_id,
                            b'',
                            response_json.encode('utf-8')
                        ])
                    except Exception as json_error:
                        print(f"❌ JSON 인코딩 오류: {json_error}")
                        # 오류 응답 전송
                        error_response = {
                            'status': 'error',
                            'error': f'JSON 인코딩 실패: {str(json_error)}'
                        }
                        self.router_socket.send_multipart([
                            client_id,
                            b'',
                            json.dumps(error_response, ensure_ascii=False).encode('utf-8')
                        ])
                    
                    # 응답 전송 로그 출력
                    if response.get('status') == 'success':
                        file_name = response.get('file_name', 'Unknown')
                        file_size = response.get('file_size', 0)
                        print(f"📤 [RESPONSE -> {client_id.decode()[:8]}...] 파일 요청 응답 전송")
                        print(f"   📄 파일명: {file_name}")
                        print(f"   📏 파일 크기: {file_size:,} bytes")
                        print(f"   🔒 Base64 인코딩: ✅")
                        print(f"   🚀 응답 포트: tcp://*:{self.router_port}")
                        print("   " + "-" * 50)
                    else:
                        error_msg = response.get('error', 'Unknown error')
                        print(f"❌ [ERROR RESPONSE -> {client_id.decode()[:8]}...] 파일 요청 실패")
                        print(f"   ⚠️ 오류: {error_msg}")
                        print("   " + "-" * 50)
                    
            except Exception as e:
                if self.router_running:  # 종료 중이 아닌 경우에만 에러 출력
                    print(f"❌ 파일 요청 처리 중 오류: {e}")
    
    def _handle_access_request_rep(self):
        """ZeroMQ REP 소켓으로 access 요청 처리"""
        self.access_running = True
        print(f"🔑 access 서버 시작: tcp://*:{self.access_port}")
        
        while self.access_running:
            try:
                # 메시지 수신 (non-blocking with timeout)
                if self.rep_socket.poll(timeout=1000):  # 1초 타임아웃
                    request = self.rep_socket.recv_json()
                    print(f"📥 access 요청 수신: {request}")
                    
                    # access 함수 호출
                    user_id = request.get('user_id')
                    if user_id:
                        pathlist = self.access(user_id)
                        response = {'status': 'success', 'pathlist': pathlist}
                    else:
                        response = {'status': 'error', 'error': 'user_id가 필요합니다'}
                    
                    # 응답 전송
                    self.rep_socket.send_json(response)
                    print(f"📤 access 응답 전송: {len(pathlist) if user_id else 0}개 파일")
                    
            except Exception as e:
                if self.access_running:  # 종료 중이 아닌 경우에만 에러 출력
                    print(f"❌ access 요청 처리 중 오류: {e}")

    def _process_file_request(self, request_data):
        """파일 요청 처리 로직"""
        try:
            file_path = request_data.get('file_path')
            if not file_path:
                return {'error': '파일 경로가 필요합니다', 'status': 'error'}
            
            # 받은 경로를 Path 객체로 변환
            requested_path = Path(file_path)
            
            # 절대 경로인 경우 상대 경로로 변환
            if requested_path.is_absolute():
                try:
                    requested_path = requested_path.relative_to(self.watch_folder)
                except ValueError:
                    # watch_folder 밖의 파일은 접근 불가
                    return {'error': 'watch_folder 외부 파일에는 접근할 수 없습니다', 'status': 'error'}
            
            # watch_folder 기준으로 절대 경로 생성
            full_path = self.watch_folder / requested_path
            
            # 파일 존재 확인
            if not full_path.exists():
                print(f"❌ 파일을 찾을 수 없음: {full_path} (요청된 경로: {file_path})")
                return {'error': '파일을 찾을 수 없습니다', 'status': 'error'}
            
            # 대상 파일 확인
            if not self._is_target_file(str(full_path)):
                return {'error': '지원하지 않는 파일 형식입니다', 'status': 'error'}
            
            # 파일 읽기 및 base64 인코딩
            with open(full_path, 'rb') as file:
                file_content = file.read()
                encoded_content = base64.b64encode(file_content).decode('utf-8')
            
            print(f"📤 파일 요청 처리 완료: {full_path} (상대경로: {requested_path})")
            return {
                'status': 'success',
                'file_path': str(full_path),
                'file_content': encoded_content,
                'file_size': len(file_content),
                'file_name': full_path.name
            }
            
        except Exception as e:
            print(f"❌ 파일 요청 처리 중 오류: {e}")
            return {'error': str(e), 'status': 'error'}


    def access(self, user_id: str) -> list:
        """
        Retrieve the list of authorized file paths for a given user.

        Args:
            user_id: The ID of the user.

        Returns:
            A list of file paths the user is authorized to access.
        """
        try:
            authorized_paths = self.auth_db.get_authorized_paths(user_id)
            print(f"🔑 Authorized paths for user {user_id}: {authorized_paths}")
            return authorized_paths
        except Exception as e:
            print(f"❌ Error retrieving authorized paths for user {user_id}: {e}")
            return []

    
    def start_watching(self):
        """파일 감시 시작"""
        class Handler(FileSystemEventHandler):
            def __init__(self, watcher):
                self.watcher = watcher
            
            def on_created(self, event):
                if not event.is_directory and self.watcher._is_target_file(event.src_path):
                    # Update file structure in database
                    rel_path = os.path.relpath(event.src_path, self.watcher.watch_folder)
                    self.watcher.auth_db.update_file_structure(rel_path, 'create')
                    # Send file to server
                    self.watcher._send_file(event.src_path, 'create')
            
            def on_modified(self, event):
                if not event.is_directory and self.watcher._is_target_file(event.src_path):
                    self.watcher._send_file(event.src_path, 'update')
            
            def on_deleted(self, event):
                if not event.is_directory and self.watcher._is_target_file(event.src_path):
                    # Update file structure in database
                    rel_path = os.path.relpath(event.src_path, self.watcher.watch_folder)
                    self.watcher.auth_db.update_file_structure(rel_path, 'delete')
                    # Send file deletion to server
                    self.watcher._send_file(event.src_path, 'delete')
        
        # 감시 폴더 생성
        self.watch_folder.mkdir(exist_ok=True)
        
        # 이벤트 핸들러 등록
        event_handler = Handler(self)
        self.observer.schedule(event_handler, str(self.watch_folder), recursive=True)
        
        # 감시 시작
        self.observer.start()
        print(f"👀 폴더 감시 시작: {self.watch_folder}")
    
    def start_router_server(self):
        """ZeroMQ ROUTER 서버 시작"""
        router_thread = threading.Thread(target=self._handle_file_request_router, daemon=True)
        router_thread.start()
        return router_thread
    
    def start_access_server(self):
        """ZeroMQ REP 서버 시작 (access 함수 처리용)"""
        access_thread = threading.Thread(target=self._handle_access_request_rep, daemon=True)
        access_thread.start()
        return access_thread

    def start(self):
        """전체 시스템 시작"""
        print("=" * 50)
        print("🔮 DB Sorcerer File Watcher 시작")
        print("=" * 50)
        
        # 파일 감시 시작
        self.start_watching()
        
        # ZeroMQ Router 서버를 별도 스레드에서 시작
        router_thread = self.start_router_server()
        
        # ZeroMQ REP 서버를 별도 스레드에서 시작 (access 처리용)
        access_thread = self.start_access_server()
        
        try:
            print("\n📋 사용 방법:")
            print(f"  • 감시 폴더: {self.watch_folder}")
            print(f"  • 지원 파일: {', '.join(self.allowed_extensions)}")
            print(f"  • 파일 변경사항 전송: PUSH tcp://localhost:{self.push_port}")
            print(f"  • 파일 요청 처리: ROUTER tcp://*:{self.router_port}")
            print(f"  • Access 권한 처리: REP tcp://*:{self.access_port}")
            if self.repo:
                print(f"  • Git 저장소: 활성화됨")
                print(f"  • Git 브랜치: {self.repo.active_branch.name}")
            else:
                print(f"  • Git 저장소: 비활성화됨")
            print("\n⏹️  종료하려면 Ctrl+C를 누르세요")
            print("-" * 50)
            
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n🛑 시스템 종료 중...")
            self.router_running = False
            self.access_running = False
            self.observer.stop()
            print("✅ 감시 종료 완료")
        
        self.observer.join()
        if router_thread.is_alive():
            router_thread.join(timeout=1)
        if access_thread.is_alive():
            access_thread.join(timeout=1)
        
        # ZeroMQ 정리
        self.push_socket.close()
        self.router_socket.close()
        self.rep_socket.close()
        self.context.term()


def main():
    """메인 실행 함수"""
    # 설정값들 (필요에 따라 수정)
    WATCH_FOLDER = "./test_files"
    PUSH_PORT = 5555  # 파일 변경사항 전송용 (PUSH 소켓)
    ROUTER_PORT = 5556  # 파일 요청 처리용 (ROUTER 소켓)
    ACCESS_PORT = 5559  # access 함수 처리용 (REP 소켓)
    
    # FileWatcher 인스턴스 생성 및 시작
    watcher = FileWatcher(
        watch_folder=WATCH_FOLDER,
        push_port=PUSH_PORT,
        router_port=ROUTER_PORT,
        access_port=ACCESS_PORT
    )
    
    watcher.start()


if __name__ == "__main__":
    main()