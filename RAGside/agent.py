"""
RAG Agent - 개선된 버전 (파싱 오류 방지 + 모드별 최적화)
"""

import json
from typing import Dict, Any, List, Optional
from Models.llm import structured_LLM
from retriever import FileRetriever


class RAGAgent:
    """RAG 시스템을 이용한 에이전트"""
    
    def __init__(self, mode: str = "deep", user_id: str = None):
        if not user_id:
            raise ValueError("사용자 ID가 필요합니다. 접근이 거부되었습니다.")
        
        self.mode = mode
        self.user_id = user_id
        self.max_iterations = self._get_max_iterations()
        self.retriever = FileRetriever(user_id=user_id)
        
        # 간단하고 안정적인 JSON 스키마
        self.output_schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "need_more": {"type": "boolean"},
                "next_query": {"type": "string"}
            },
            "required": ["answer", "need_more", "next_query"]
        }
    
    def _get_max_iterations(self) -> int:
        modes = {"normal": 1, "deep": 3, "deeper": 5}
        return modes.get(self.mode, 3)
    
    def process(self, user_input: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        if conversation_history is None:
            conversation_history = []
            
        print(f"🤖 사용자 질문: {user_input}")
        
        accumulated_context = ""
        last_search_results = []
        iteration = 0
        current_query = user_input
        
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n🔄 반복 {iteration}/{self.max_iterations}")
            
            # 검색 수행
            print(f"🔍 검색 쿼리: {current_query}")
            search_results = self.retriever.search_chunks(current_query, top_n=3)
            last_search_results = search_results
            
            if search_results:
                # 딕셔너리 형태의 검색 결과에서 텍스트만 추출하여 컨텍스트 구성
                context_texts = [result['text'] for result in search_results]
                new_context = "\n".join(context_texts)
                accumulated_context += f"\n\n=== 검색 결과 {iteration} ===\n{new_context}"
                print(f"✅ {len(search_results)}개 문서 조각 발견")
            else:
                print("❌ 검색 결과 없음")
            
            # LLM 처리
            is_final = (iteration == self.max_iterations)
            prompt = self._build_prompt(user_input, accumulated_context, iteration, is_final)
            
            try:
                response = structured_LLM(prompt, self.output_schema)
                result = json.loads(response)
                
                print(f"🧠 AI 응답: {result['answer']}")
                print(f"🔄 계속 검색 필요: {result['need_more']}")
                
                # Normal 모드나 최종 반복이거나 더 이상 검색 불필요시 종료
                if self.mode == "normal" or is_final or not result['need_more']:
                    print("✅ 검색 완료")
                    self._show_referenced_chunks(last_search_results)
                    return result['answer']
                
                # 다음 검색 쿼리 설정
                current_query = result.get('next_query', '').strip() or user_input
                print(f"➡️ 다음 검색 쿼리: {current_query}")
                
            except Exception as e:
                print(f"❌ LLM 처리 오류: {e}")
                if is_final:
                    return f"수집된 정보를 바탕으로 답변드리기 어렵습니다. 검색된 정보: {accumulated_context[:500]}..."
                continue
        
        return "예상치 못한 오류가 발생했습니다."
    
    def _build_prompt(self, user_input: str, context: str, iteration: int, is_final: bool) -> str:
        """모드별 최적화된 프롬프트 생성"""
        
        # 기본 정보
        base_info = f"""
사용자 질문: {user_input}
현재까지 수집된 정보:
{context if context else "아직 수집된 정보가 없습니다."}
"""
        
        # 모드별 지침
        if self.mode == "normal":
            instruction = """
빠른 답변 모드입니다. 현재 정보로 답변하세요.
- answer: 핵심을 담은 답변
- need_more: 이 항목은 *반드시* false 로 답변
- next_query: "" 이 항목은 *반드시* 빈 문자열로 답변
"""
        elif self.mode == "deep":
            if is_final:
                instruction = f"""
마지막 단계({iteration}회차)입니다. 수집된 정보로 최종 답변하세요.
- answer: 종합적인 최종 답변 또는 "정보 부족으로 답변 어려움" 명시
- need_more: 이 항목은 *반드시* false 로 답변
- next_query: "" 이 항목은 *반드시* 빈 문자열로 답변
"""
            else:
                instruction = f"""
균형잡힌 탐색 모드 {iteration}회차입니다. 정보가 충분한지 판단하세요.
- answer: 현재 분석 결과나 중간 답변
- need_more: 더 검색이 필요하면 true, 충분하면 false
- next_query: 필요시 다음 검색어, 불필요하면 ""
"""
        else:  # deeper
            strategies = {
                1: "기초 정보 수집",
                2: "세부 정보 탐색", 
                3: "맥락 및 배경 확장",
                4: "다각적 관점 확보",
                5: "정보 검증 및 종합"
            }
            current_strategy = strategies.get(iteration, "종합 분석")
            
            if is_final:
                instruction = f"""
심층 분석 최종 단계({iteration}회차)입니다. 모든 정보를 종합하여 완전한 답변하세요.
- answer: 심층 분석을 통한 완전한 최종 답변
- need_more: false
- next_query: ""
"""
            else:
                instruction = f"""
심층 분석 모드 {iteration}회차 - {current_strategy}
현재 단계 목표에 맞게 추가 탐색이 필요한지 판단하세요.
- answer: 현재까지의 분석 내용
- need_more: 목표 달성을 위해 더 필요하면 true
- next_query: 다음 단계에 맞는 새로운 관점의 검색어
"""
        
        return base_info + "\n" + instruction + """

중요: 오직 검색된 정보만 사용하고, 추측하지 마세요.
JSON 형식으로 정확히 응답하세요."""
    
    def _show_referenced_chunks(self, chunks: list):
        if not chunks:
            return
            
        print(f"\n📚 참고한 문서 ({len(chunks)}개):")
        print("=" * 50)
        for i, chunk in enumerate(chunks, 1):
            if isinstance(chunk, dict):
                chunk_text = chunk.get('text', '')
                file_name = chunk.get('file_name', '알 수 없는 파일')
                preview = chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text
                print(f"{i}. 📄 {file_name}")
                print(f"   {preview}")
            else:
                # 이전 버전과의 호환성을 위해 문자열 처리도 유지
                preview = chunk[:200] + "..." if len(chunk) > 200 else chunk
                print(f"{i}. {preview}")
            print("-" * 30)
    
    def close(self):
        self.retriever.close()


def main():
    print("RAG Agent - 검색 모드를 선택하세요:")
    print("1. normal - 빠른 검색 (1회)")
    print("2. deep - 일반 검색 (3회, 기본값)")  
    print("3. deeper - 심화 검색 (5회)")
    
    mode_input = input("모드를 선택하세요 (1/2/3, 엔터=기본값): ").strip()
    mode_map = {"1": "normal", "2": "deep", "3": "deeper"}
    mode = mode_map.get(mode_input, "deep")
    
    user_id = input("사용자 ID를 입력하세요: ").strip()
    if not user_id:
        print("❌ 사용자 ID가 필요합니다.")
        return
    
    try:
        agent = RAGAgent(mode, user_id=user_id)
        print(f"🚀 {mode} 모드로 시작합니다.")
        
        user_question = input("질문을 입력하세요: ")
        answer = agent.process(user_question)
        print(f"\n🎯 최종 답변:\n{answer}")
        
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        agent.close()


if __name__ == "__main__":
    main()