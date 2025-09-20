"""
RAGAgent Web Server
- Flask를 사용하여 RAGAgent를 웹에서 접근 가능하도록 하는 간단한 서버
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from agent import RAGAgent

app = Flask(__name__)
# CORS 설정 - 모든 origin에서 접근 가능하도록 설정 (개발용)
# 실제 배포시에는 specific origins를 명시하는 것이 보안상 좋습니다
CORS(app, origins="*")

# RAGAgent 인스턴스들 (user_id별로 관리)
rag_agents = {}

def get_rag_agent(mode="deep", user_id="anonymous"):
    """RAGAgent 인스턴스를 가져오거나 생성"""
    global rag_agents
    agent_key = f"{user_id}_{mode}"
    
    if agent_key not in rag_agents:
        rag_agents[agent_key] = RAGAgent(mode=mode, user_id=user_id)
    
    return rag_agents[agent_key]

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
        
        # user_id 설정 (기본값: anonymous)
        user_id = data.get('user_id', 'anonymous')
        if not user_id or not user_id.strip():
            user_id = 'anonymous'
        
        # RAGAgent로 처리
        agent = get_rag_agent(mode, user_id)
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
        # 모든 RAGAgent 인스턴스 종료
        for agent in rag_agents.values():
            agent.close()
        print("✅ 서버 종료 완료")
    except Exception as e:
        print(f"❌ 서버 시작 실패: {e}")
        # 모든 RAGAgent 인스턴스 종료
        for agent in rag_agents.values():
            agent.close()
