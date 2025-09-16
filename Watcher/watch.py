#C, U, D 감지 역할만

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import os
import getpass
from fetch import send_file  # fetch 모듈에서 함수 임포트

class FolderHandler(FileSystemEventHandler):
    def is_target_file(self, file_path):
        allowed_extensions = {'.docx', '.pdf', '.hwp', '.txt'}
        _, ext = os.path.splitext(file_path)
        return ext.lower() in allowed_extensions
    
    def on_created(self, event):
        if not event.is_directory and self.is_target_file(event.src_path):  # 파일만 감시 (폴더 이벤트 제외)
            send_file(event.src_path, 'create', getpass.getuser())

    def on_deleted(self, event):
        if not event.is_directory and self.is_target_file(event.src_path):
            send_file(event.src_path, 'delete', getpass.getuser())
    
    def on_modified(self, event):
        if not event.is_directory and self.is_target_file(event.src_path):
            send_file(event.src_path, 'update', getpass.getuser())

watch_folder = "./watch_folder"
event_handler = FolderHandler()
observer = Observer()
observer.schedule(event_handler, watch_folder, recursive=True)

observer.start()
print(f"폴더 감시 시작: {watch_folder}")

try:
    while True:
        time.sleep(2)  # CPU 사용량 제어
except KeyboardInterrupt:
    observer.stop()
    print("\n감시 종료")

observer.join() # 스레드 종료 대기

