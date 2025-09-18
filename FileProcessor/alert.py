from flask import Flask, request, jsonify
import os

app = Flask(__name__)

def process_file_content(file_content, filename, event_type, user_id):
    """파일 내용을 메모리에 받아와서 보관하는 함수"""
    print(f"파일 수신: {filename} ({event_type}) - 사용자: {user_id}")
    print(f"파일 크기: {len(file_content)} bytes")
    
    # 파일 내용을 file_reader.py나 다른 처리 모듈로 전달할 수 있도록 반환
    # 실제 텍스트 추출, 임베딩, 청킹 등은 file_reader.py에서 처리
    
    return file_content

@app.route('/upload', methods=['POST'])
def upload_file():
    """파일 수신 및 메모리 처리"""
    # 추가 데이터 받기
    event_type = request.form.get('event_type')
    user_id = request.form.get('user_id')
    
    # delete 이벤트 처리
    if event_type == 'delete':
        file_path = request.form.get('file_path')
        print(f"파일 삭제 이벤트: {file_path} - 사용자: {user_id}")
        
        # 여기서 DB에서 해당 파일 관련 데이터 삭제 로직 추가
        
        return jsonify({
            'message': '파일 삭제 처리 완료',
            'file_path': file_path,
            'event_type': event_type,
            'user_id': user_id
        })
    
    # create/update 이벤트 처리
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '파일명이 없습니다'}), 400
    
    # 파일 내용을 메모리로 읽기
    file_content = file.read()
    filename = file.filename
    
    # 파일 내용을 메모리에 보관 (file_reader.py로 전달 준비)
    processed_content = process_file_content(file_content, filename, event_type, user_id)
    
    return jsonify({
        'message': '파일 수신 완료',
        'filename': filename,
        'size': len(file_content),
        'event_type': event_type,
        'user_id': user_id,
        'ready_for_processing': True
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
    
