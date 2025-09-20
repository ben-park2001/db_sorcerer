"""
메시지 데이터베이스 서버
- ZMQ REP 서버 (5560 포트): postprocessor로부터 메시지 수신
- Flask 웹 서버 (5001) 포트): 사용자별 메시지 조회 API
"""

import zmq
import time
import threading
from flask import Flask, jsonify
from collections import defaultdict


class MessageDB:
    def __init__(self, zmq_port=5560, flask_port=5001):
        self.zmq_port = zmq_port
        self.flask_port = flask_port
        
        # 사용자별 메시지 저장소
        self.user_messages = defaultdict(list)
        
        # ZMQ 설정
        self.context = zmq.Context()
        self.rep_socket = self.context.socket(zmq.REP)
        self.rep_socket.bind(f"tcp://*:{self.zmq_port}")
        
        # Flask 앱 설정
        self.app = Flask(__name__)
        self.setup_routes()
        
        self.running = False

    def setup_routes(self):
        """Flask 라우트 설정"""
        @self.app.route('/messages/<user_id>', methods=['GET'])
        def get_user_messages(user_id):
            messages = self.get_user_messages(user_id)
            return jsonify({
                'user_id': user_id,
                'message_count': len(messages),
                'messages': messages
            })

    def add_message_to_users(self, user_list, message):
        """사용자 목록에 메시지 추가"""
        timestamp = time.time()
        message_data = {
            'message': message,
            'timestamp': timestamp,
            'formatted_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        }
        
        for user_id in user_list:
            self.user_messages[user_id].append(message_data)
        
        print(f"📬 메시지 저장 완료: {len(user_list)}명 사용자에게 추가")
        return len(user_list)

    def get_user_messages(self, user_id):
        """특정 사용자의 메시지 목록 반환"""
        return self.user_messages.get(user_id, [])

    def start_zmq_server(self):
        """ZMQ REP 서버 시작"""
        self.running = True
        print(f"🔗 ZMQ 서버 시작: tcp://*:{self.zmq_port}")
        
        while self.running:
            try:
                if self.rep_socket.poll(timeout=1000):
                    # 메시지 수신
                    request = self.rep_socket.recv_json()
                    print(f"📥 ZMQ 메시지 수신: {request}")
                    
                    # 메시지 처리
                    user_list = request.get('user_list', [])
                    message = request.get('message', '')
                    
                    if user_list and message:
                        count = self.add_message_to_users(user_list, message)
                        response = {'status': 'success', 'users_notified': count}
                    else:
                        response = {'status': 'error', 'error': 'user_list 및 message가 필요합니다'}
                    
                    # 응답 전송
                    self.rep_socket.send_json(response)
                    
            except Exception as e:
                if self.running:
                    print(f"❌ ZMQ 서버 오류: {e}")

    def start_flask_server(self):
        """Flask 웹 서버 시작"""
        print(f"🌐 Flask 서버 시작: http://localhost:{self.flask_port}")
        self.app.run(host='0.0.0.0', port=self.flask_port, debug=False, use_reloader=False)

    def start(self):
        """전체 서버 시작"""
        print("=" * 50)
        print("📬 MessageDB 서버 시작")
        print("=" * 50)
        
        # ZMQ 서버를 별도 스레드에서 시작
        zmq_thread = threading.Thread(target=self.start_zmq_server, daemon=True)
        zmq_thread.start()
        
        # Flask 서버를 별도 스레드에서 시작
        flask_thread = threading.Thread(target=self.start_flask_server, daemon=True)
        flask_thread.start()
        
        print(f"\n📋 서비스 정보:")
        print(f"  • ZMQ 포트: {self.zmq_port}")
        print(f"  • Flask 포트: {self.flask_port}")
        print(f"  • API 엔드포인트: http://localhost:{self.flask_port}/messages/<user_id>")
        print("\n⏹️  종료하려면 Ctrl+C를 누르세요")
        print("-" * 50)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 서버 종료 중...")
            self.running = False
            
        # 정리
        self.rep_socket.close()
        self.context.term()
        print("✅ MessageDB 서버 종료 완료")


def main():
    """메인 실행 함수"""
    messagedb = MessageDB()
    messagedb.start()


if __name__ == "__main__":
    main()
