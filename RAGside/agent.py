"""
RAG Agent - 사용자 질문에 대해 검색과 AI 추론을 반복하여 답변을 생성하는 에이전트
"""

import json
from typing import Dict, Any, List, Optional
from Models.llm import structured_LLM
from retriever import FileRetriever


class RAGAgent:
    """RAG 시스템을 이용한 에이전트"""
    
    def __init__(self, mode: str = "deep", user_id: str = None):
        """
        Args:
            mode: 검색 모드 ('normal': 1회, 'deep': 3회, 'deeper': 5회)
            user_id: 사용자 ID (권한 확인용, 필수)
        """
        if not user_id:
            raise ValueError("사용자 ID가 필요합니다. 접근이 거부되었습니다.")
        
        self.mode = mode
        self.user_id = user_id
        self.max_iterations = self._get_max_iterations()
        self.retriever = FileRetriever(user_id=user_id)
        
        # structured LLM을 위한 JSON 스키마
        self.output_schema = {
            "type": "object",
            "properties": {
                "llm_output": {
                    "type": "string",
                    "description": "AI의 응답이나 생각"
                },
                "continue_iterate": {
                    "type": "boolean", 
                    "description": "더 검색이 필요한지 여부"
                },
                "search_query": {
                    "type": "string",
                    "description": "다음에 검색할 쿼리 (continue_iterate가 true일 때만 사용)"
                }
            },
            "required": ["llm_output", "continue_iterate", "search_query"]
        }
    
    def _get_max_iterations(self) -> int:
        """모드에 따른 최대 반복 횟수 반환"""
        modes = {"normal": 1, "deep": 3, "deeper": 5}
        return modes.get(self.mode, 3)  # 잘못된 값이면 기본값 3
    
    def process(self, user_input: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        사용자 입력을 처리하여 최종 답변을 반환
        
        Args:
            user_input: 사용자의 질문이나 요청
            conversation_history: 이전 대화 히스토리 (optional)
            
        Returns:
            최종 AI 응답
        """
        if conversation_history is None:
            conversation_history = []
            
        print(f"🤖 사용자 질문: {user_input}")
        
        # 검색된 컨텍스트를 누적
        accumulated_context = ""
        last_search_results = []  # 마지막 검색 결과 저장
        iteration = 0
        
        # 첫 번째 검색 쿼리는 사용자 입력 그대로 사용
        current_query = user_input
        
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n🔄 반복 {iteration}/{self.max_iterations}")
            
            # 1. 현재 쿼리로 검색 수행
            print(f"🔍 검색 쿼리: {current_query}")
            search_results = self.retriever.search_chunks(current_query, top_n=3)
            last_search_results = search_results  # 마지막 검색 결과 저장
            
            if search_results:
                new_context = "\n".join(search_results)
                accumulated_context += f"\n\n=== 검색 결과 {iteration} ===\n{new_context}"
                print(f"✅ {len(search_results)}개 문서 조각 발견")
            else:
                print("❌ 검색 결과 없음")
            
            # 2. LLM에게 현재 상황을 전달하고 다음 액션 결정
            prompt = self._build_prompt(user_input, accumulated_context, iteration, conversation_history)
            
            try:
                response = structured_LLM(prompt, self.output_schema)
                result = json.loads(response)
                
                print(f"🧠 AI 응답: {result['llm_output']}")
                print(f"🔄 계속 검색 필요: {result['continue_iterate']}")
                
                # Normal 모드는 첫 검색 후 무조건 종료
                if self.mode == "normal":
                    print("✅ Normal 모드 - 검색 완료")
                    self._show_referenced_chunks(last_search_results)
                    return result['llm_output']
                
                # 계속 검색이 필요하지 않다면 종료
                if not result['continue_iterate']:
                    print("✅ 검색 완료")
                    self._show_referenced_chunks(last_search_results)
                    return result['llm_output']
                
                # 다음 검색 쿼리 설정
                current_query = result['search_query']
                print(f"➡️ 다음 검색 쿼리: {current_query}")
                
            except Exception as e:
                print(f"❌ LLM 처리 오류: {e}")
                break
        
        # 최대 반복 횟수 도달 시 마지막 시도
        print(f"\n⏰ 최대 반복 횟수 도달. 최종 답변 생성...")
        final_prompt = f"""
사용자 질문: {user_input}

수집된 정보:
{accumulated_context}

위 정보를 바탕으로 사용자 질문에 대한 최종 답변을 제공해주세요.
"""
        
        try:
            final_response = structured_LLM(final_prompt, self.output_schema)
            final_result = json.loads(final_response)
            self._show_referenced_chunks(last_search_results)
            return final_result['llm_output']
        except Exception as e:
            print(f"❌ 최종 답변 생성 실패: {e}")
            return "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다."
    
    def _build_prompt(self, user_input: str, context: str, iteration: int, conversation_history: List[Dict[str, str]]) -> str:
        """LLM용 프롬프트 생성"""
        # 히스토리 텍스트 생성 (최근 5개만 사용)
        history_text = ""
        if conversation_history:
            recent_history = conversation_history[-5:]  # 최근 5개만
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])
        
        return f"""
당신은 사용자의 질문에 답하기 위해 문서를 검색하고 분석하는 AI 에이전트입니다.

대화 히스토리:
{history_text}

사용자 질문: {user_input}

현재까지 수집된 정보:
{context}

현재 반복: {iteration}/{self.max_iterations}

다음 중 하나를 선택하세요:
1. 충분한 정보가 있다면 -> continue_iterate: false, 최종 답변 제공
2. 더 검색이 필요하다면 -> continue_iterate: true, 새로운 검색 쿼리 제안

응답 형식:
- llm_output: 현재 상황에 대한 당신의 분석이나 답변
- continue_iterate: 더 검색할지 여부 (true/false)  
- search_query: 다음 검색할 내용 (continue_iterate가 true일 때만)
"""
    
    def _show_referenced_chunks(self, chunks: list):
        """마지막에 참고한 chunk들을 표시"""
        if not chunks:
            return
            
        print(f"\n📚 참고한 문서 ({len(chunks)}개):")
        print("=" * 50)
        for i, chunk in enumerate(chunks, 1):
            # chunk 텍스트가 너무 길면 앞부분만 표시
            preview = chunk[:200] + "..." if len(chunk) > 200 else chunk
            print(f"{i}. {preview}")
            print("-" * 30)
    
    def close(self):
        """리소스 정리"""
        self.retriever.close()


def main():
    """사용 예시"""
    print("RAG Agent - 검색 모드를 선택하세요:")
    print("1. normal - 빠른 검색 (1회)")
    print("2. deep - 일반 검색 (3회, 기본값)")
    print("3. deeper - 심화 검색 (5회)")
    
    mode_input = input("모드를 선택하세요 (1/2/3, 엔터=기본값): ").strip()
    mode_map = {"1": "normal", "2": "deep", "3": "deeper"}
    mode = mode_map.get(mode_input, "deep")
    
    # 사용자 ID 입력
    user_id = input("사용자 ID를 입력하세요: ").strip()
    if not user_id:
        print("❌ 사용자 ID가 필요합니다. 프로그램을 종료합니다.")
        return
    
    try:
        agent = RAGAgent(mode, user_id=user_id)
        print(f"🚀 {mode} 모드로 시작합니다.")
        print(f"👤 사용자: {user_id}")
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    try:
        # 사용자 입력 받기
        user_question = input("질문을 입력하세요: ")
        
        # 처리 및 결과 출력
        answer = agent.process(user_question)
        print(f"\n🎯 최종 답변:\n{answer}")
        
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        agent.close()


if __name__ == "__main__":
    main()