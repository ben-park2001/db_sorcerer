"""
RAGAgent Web Server
- Flask를 사용하여 RAGAgent를 웹에서 접근 가능하도록 하는 간단한 서버
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from agent import RAGAgent

app = Flask(__name__)
# CORS 설정 - 프론트엔드에서 접근 가능하도록 설정
CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000'])

# RAGAgent 인스턴스 (전역으로 관리)
rag_agent = None

def get_rag_agent(mode="deep"):
    """RAGAgent 인스턴스를 가져오거나 생성"""
    global rag_agent
    if rag_agent is None or (hasattr(rag_agent, 'mode') and rag_agent.mode != mode):
        if rag_agent:
            rag_agent.close()
        rag_agent = RAGAgent(mode=mode)
    return rag_agent

@app.route('/api/chat', methods=['POST'])
def chat():
    """채팅 API - 사용자 질문을 받고 RAGAgent로 처리"""
    try:
        # 요청 데이터 파싱
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                'status': 'error',
                'error': '메시지가 필요합니다.'
            }), 400
        
        user_message = data['message'].strip()
        if not user_message:
            return jsonify({
                'status': 'error', 
                'error': '빈 메시지는 처리할 수 없습니다.'
            }), 400
        
        # 모드 설정 (기본값: deep)
        mode = data.get('mode', 'deep')
        if mode not in ['normal', 'deep', 'deeper']:
            mode = 'deep'
        
        # RAGAgent로 처리
        agent = get_rag_agent(mode)
        response = agent.process(user_message)
        
        return jsonify({
            'status': 'success',
            'response': response,
            'mode': mode
        })
        
    except Exception as e:
        print(f"❌ API 오류: {e}")
        return jsonify({
            'status': 'error',
            'error': f'처리 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """서버 상태 확인"""
    return jsonify({
        'status': 'healthy',
        'message': 'RAGAgent Web Server is running'
    })

if __name__ == '__main__':
    try:
        print("🚀 RAGAgent API Server 시작...")
        print("📡 API 서버 주소: http://localhost:5000")
        print("� Chat API: http://localhost:5000/api/chat")
        print("❤️ Health Check: http://localhost:5000/api/health")
        print("🌐 Frontend는 별도 서버에서 실행하세요 (예: localhost:3000)")
        
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True
        )
    except KeyboardInterrupt:
        print("\n🛑 서버 종료 중...")
        if rag_agent:
            rag_agent.close()
        print("✅ 서버 종료 완료")
    except Exception as e:
        print(f"❌ 서버 시작 실패: {e}")
        if rag_agent:
            rag_agent.close()
