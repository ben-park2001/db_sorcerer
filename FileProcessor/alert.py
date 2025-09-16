# 실제로는 drag & drop 형태에서 file path 를 string 으로 추출해내는 작업이 필요할 것 같음. FE 에 통합 가능.
#send로부터 받아온 정보 토대로 알림 메시지 생성 및 발송 (사내메신저API와 연동)
# 파일을 수신하는 서버 코드
from flask import Flask, request, jsonify
import os


#create, update인 경우 표준 db업로드절차 (텍스트 추출,스마트 청킹,센텐스임베딩)
#create인경우 요약도 생성
#update인경우 변경사항만 반영
#delete인경우 db에서 삭제

#userid는 전송목록에서 빼기

app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload_file():
    """파일 수신 및 저장"""
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '파일명이 없습니다'}), 400
    
    # 추가 데이터 받기
    event_type = request.form.get('event_type')
    user_id = request.form.get('user_id')
    
    # 파일 저장
    save_path = os.path.join('received_files', file.filename)
    os.makedirs('received_files', exist_ok=True)
    file.save(save_path)
    
    return jsonify({
        'message': '파일 수신 완료',
        'filename': file.filename,
        'size': os.path.getsize(save_path),
        'event_type': event_type,
        'user_id': user_id
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
    
