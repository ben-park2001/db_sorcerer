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
from pathlib import Path

import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from flask import Flask, request, jsonify, send_file
import git
from git import Repo, InvalidGitRepositoryError


class FileWatcher:
    def __init__(self, watch_folder="./watch_folder", server_url="http://localhost:8000/upload", port=9000):
        self.watch_folder = Path(watch_folder)
        self.server_url = server_url
        self.port = port
        self.user_id = getpass.getuser()
        
        # Flask 앱 설정
        self.app = Flask(__name__)
        self._setup_routes()
        
        # 감시 대상 파일 확장자
        self.allowed_extensions = {'.docx', '.pdf', '.hwp', '.txt'}
        
        # Observer 설정
        self.observer = Observer()
        
        # Git 저장소 설정
        self.repo = None
        self._init_git_repo()
        
    def _setup_routes(self):
        """Flask 라우트 설정"""
        @self.app.route('/get_file', methods=['GET'])
        def get_file():
            return self._handle_file_request()
    
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
            # Git diff 정보 수집 (update인 경우)
            diff_info = None
            if event_type == 'update':
                diff_info = self._get_file_diff(file_path)
            
            # Git 커밋 수행
            commit_success = self._commit_file_change(file_path, event_type)
            
            if event_type == 'delete':
                # 삭제 이벤트: 메타데이터만 전송
                data = {
                    'event_type': event_type,
                    'user_id': self.user_id,
                    'file_path': str(file_path),
                    'git_committed': str(commit_success)
                }
                response = requests.post(self.server_url, data=data)
            else:
                # 생성/수정 이벤트: 파일과 함께 전송
                if not os.path.exists(file_path):
                    print(f"파일을 찾을 수 없습니다: {file_path}")
                    return
                
                with open(file_path, 'rb') as file:
                    files = {'file': file}
                    data = {
                        'event_type': event_type,
                        'user_id': self.user_id,
                        'git_committed': str(commit_success)
                    }
                    
                    # diff 정보가 있으면 추가
                    if diff_info:
                        data['diff_type'] = diff_info['type']
                        data['diff_content'] = diff_info['diff']
                        data['relative_path'] = diff_info['file_path']
                    
                    response = requests.post(self.server_url, files=files, data=data)
            
            if response.status_code == 200:
                print(f"✅ 파일 전송 성공: {file_path} ({event_type})")
                if diff_info:
                    print(f"   📊 Diff 정보 포함: {diff_info['type']}")
            else:
                print(f"❌ 파일 전송 실패: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 파일 전송 중 오류 발생: {e}")
    
    def _handle_file_request(self):
        """파일 요청 처리"""
        try:
            file_path = request.args.get('file_path')
            if not file_path:
                return jsonify({'error': '파일 경로가 필요합니다'}), 400
            
            # 절대 경로로 변환
            full_path = Path(file_path)
            if not full_path.is_absolute():
                full_path = self.watch_folder / file_path
            
            # 파일 존재 확인
            if not full_path.exists():
                return jsonify({'error': '파일을 찾을 수 없습니다'}), 404
            
            # 대상 파일 확인
            if not self._is_target_file(str(full_path)):
                return jsonify({'error': '지원하지 않는 파일 형식입니다'}), 400
            
            print(f"📤 파일 요청 처리: {full_path}")
            return send_file(str(full_path), as_attachment=True)
            
        except Exception as e:
            print(f"❌ 파일 요청 처리 중 오류: {e}")
            return jsonify({'error': str(e)}), 500
    
    def start_watching(self):
        """파일 감시 시작"""
        class Handler(FileSystemEventHandler):
            def __init__(self, watcher):
                self.watcher = watcher
            
            def on_created(self, event):
                if not event.is_directory and self.watcher._is_target_file(event.src_path):
                    self.watcher._send_file(event.src_path, 'create')
            
            def on_modified(self, event):
                if not event.is_directory and self.watcher._is_target_file(event.src_path):
                    self.watcher._send_file(event.src_path, 'update')
            
            def on_deleted(self, event):
                if not event.is_directory and self.watcher._is_target_file(event.src_path):
                    self.watcher._send_file(event.src_path, 'delete')
        
        # 감시 폴더 생성
        self.watch_folder.mkdir(exist_ok=True)
        
        # 이벤트 핸들러 등록
        event_handler = Handler(self)
        self.observer.schedule(event_handler, str(self.watch_folder), recursive=True)
        
        # 감시 시작
        self.observer.start()
        print(f"👀 폴더 감시 시작: {self.watch_folder}")
    
    def start_server(self):
        """HTTP 서버 시작"""
        print(f"🚀 파일 요청 서버 시작: http://localhost:{self.port}")
        self.app.run(host='localhost', port=self.port, debug=False, use_reloader=False)
    
    def start(self):
        """전체 시스템 시작"""
        print("=" * 50)
        print("🔮 DB Sorcerer File Watcher 시작")
        print("=" * 50)
        
        # 파일 감시 시작
        self.start_watching()
        
        # HTTP 서버를 별도 스레드에서 시작
        server_thread = threading.Thread(target=self.start_server, daemon=True)
        server_thread.start()
        
        try:
            print("\n📋 사용 방법:")
            print(f"  • 감시 폴더: {self.watch_folder}")
            print(f"  • 지원 파일: {', '.join(self.allowed_extensions)}")
            print(f"  • 파일 요청: GET http://localhost:{self.port}/get_file?file_path=파일경로")
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
            self.observer.stop()
            print("✅ 감시 종료 완료")
        
        self.observer.join()


def main():
    """메인 실행 함수"""
    # 설정값들 (필요에 따라 수정)
    WATCH_FOLDER = "./watch_folder"
    SERVER_URL = "http://localhost:8000/upload"
    PORT = 9000
    
    # FileWatcher 인스턴스 생성 및 시작
    watcher = FileWatcher(
        watch_folder=WATCH_FOLDER,
        server_url=SERVER_URL,
        port=PORT
    )
    
    watcher.start()


if __name__ == "__main__":
    main()