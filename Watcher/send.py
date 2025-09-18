import requests
import os

def send_file(file_path, event_type, user_id):
    """파일을 alert.py 서버로 전송"""
    try:
        # 파일이 존재하는지 확인 (delete 이벤트는 제외)
        if event_type != 'delete' and not os.path.exists(file_path):
            print(f"파일을 찾을 수 없습니다: {file_path}")
            return
        
        # alert.py 서버 URL
        url = "http://localhost:8000/upload"
        
        # delete 이벤트의 경우 파일 없이 메타데이터만 전송
        if event_type == 'delete':
            data = {
                'event_type': event_type,
                'user_id': user_id,
                'file_path': file_path
            }
            response = requests.post(url, data=data)
        else:
            # create/update 이벤트의 경우 파일과 함께 전송
            with open(file_path, 'rb') as file:
                files = {'file': file}
                data = {
                    'event_type': event_type,
                    'user_id': user_id
                }
                response = requests.post(url, files=files, data=data)
        
        if response.status_code == 200:
            print(f"파일 전송 성공: {file_path} ({event_type})")
        else:
            print(f"파일 전송 실패: {response.status_code}")
            
    except Exception as e:
        print(f"파일 전송 중 오류 발생: {e}")



