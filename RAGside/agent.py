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
                    "description": "다음에 검색할 쿼리 (continue_iterate가 true일 때만 의미있음, false일 때는 빈 문자열)"
                }
            },
            "required": ["llm_output", "continue_iterate"],
            "additionalProperties": False
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
            
            # 2. LLM에게 현재 상황을 전달하고 다음 액션 결정 (최종 반복 여부 전달)
            is_final_iteration = (iteration == self.max_iterations)
            prompt = self._build_prompt(user_input, accumulated_context, iteration, conversation_history, is_final_iteration)
            
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
                
                # 최종 반복이거나 더 이상 검색하지 않겠다면 종료
                if is_final_iteration or not result['continue_iterate']:
                    print("✅ 검색 완료")
                    self._show_referenced_chunks(last_search_results)
                    return result['llm_output']
                
                # 다음 검색 쿼리 설정
                current_query = result.get('search_query', '').strip()
                if not current_query:
                    current_query = user_input
                print(f"➡️ 다음 검색 쿼리: {current_query}")
                
            except Exception as e:
                print(f"❌ LLM 처리 오류: {e}")
                if is_final_iteration:
                    # 최종 반복에서 실패한 경우, 수집된 정보로 간단한 답변 시도
                    return f"수집된 정보를 바탕으로 답변드리기 어렵습니다. 검색된 정보: {accumulated_context[:500]}..."
                continue
        
        # 이 부분은 실행되지 않아야 함 (while 루프에서 이미 처리됨)
        return "예상치 못한 오류가 발생했습니다."
    
    def _build_prompt(self, user_input: str, context: str, iteration: int, conversation_history: List[Dict[str, str]], is_final_iteration: bool = False) -> str:
        """모드에 따라 적절한 프롬프트 빌더를 호출합니다."""
        
        if self.mode == "normal":
            # Normal 모드는 반복이 없지만, 구조 일관성을 위해 is_final_iteration을 전달합니다.
            return self._build_normal_prompt(user_input, context, conversation_history)
        elif self.mode == "deep":
            return self._build_deep_prompt(user_input, context, iteration, conversation_history, is_final_iteration)
        elif self.mode == "deeper":
            return self._build_deeper_prompt(user_input, context, iteration, conversation_history, is_final_iteration)
        else: # 기본값 처리
            return self._build_deep_prompt(user_input, context, iteration, conversation_history, is_final_iteration)
        
    def _build_normal_prompt(self, user_input: str, context: str, conversation_history: List[Dict[str, str]], is_final_iteration: bool = False) -> str:
        """
        Normal 모드용 프롬프트: 신속하고 간결한 답변 생성에 집중합니다.
        """
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-3:]])
        
        return f"""
    당신은 주어진 정보를 바탕으로 사용자의 질문에 핵심만 간결하게 답변하는 AI 어시스턴트입니다.

    [대화 히스토리]
    {history_text}

    [사용자 질문]
    {user_input}

    [검색된 정보]
    {context if context else "검색된 정보가 없습니다."}

    **[Normal 모드 지침]**
    이 모드는 신속한 답변을 위해 1회 검색만 수행합니다.
    
    **[응답 형식]**
    - `llm_output`: 검색된 정보를 바탕으로 한 간결하고 정확한 답변을 작성하세요.
    - `continue_iterate`: 반드시 `false`로 설정하세요 (Normal 모드는 추가 검색을 하지 않습니다).
    - `search_query`: 생략하거나 빈 문자열로 설정하세요 (Normal 모드에서는 사용되지 않습니다).

    **[중요 원칙]**
    - 오직 위에 제시된 [검색된 정보]만을 활용하여 답변하세요.
    - 정보가 부족한 경우 "검색된 정보가 부족하여 정확한 답변을 드리기 어렵습니다"라고 명시하세요.
    - 추측이나 일반 지식으로 답변을 보완하지 마세요.
    """
    def _build_deep_prompt(self, user_input: str, context: str, iteration: int, conversation_history: List[Dict[str, str]], is_final_iteration: bool) -> str:
        """
        Deep 모드용 프롬프트: 균형잡힌 탐색과 답변 품질 확보에 집중합니다.
        """
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-5:]])
        
        if is_final_iteration:
            action_instruction = """
    **[마지막 단계 지침]**
    이번이 마지막 검색입니다. 더 이상의 정보 수집은 불가능합니다.
    1. **분석**: 현재까지 수집된 모든 정보를 종합하여 사용자의 질문에 답변할 수 있는지 평가하세요.
    2. **실행**: `continue_iterate`를 `false`로 설정하고, 다음 중 하나를 선택하세요:
       - **충분한 정보가 있는 경우**: `llm_output`에 수집된 정보를 바탕으로 한 완전한 답변을 작성하세요.
       - **정보가 부족한 경우**: `llm_output`에 "수집된 정보로는 해당 질문에 대한 정확한 답변을 드리기 어렵습니다."라고 명시하고, 어떤 정보가 부족한지 설명하세요.
    """
        else:
            action_instruction = f"""
    **[현재 단계({iteration}/{self.max_iterations}) 지침]**
    1. **분석**: 현재 정보가 질문에 답변하기에 충분한지, 혹은 답변의 품질을 높이기 위해 어떤 정보가 더 필요한지 분석하세요.
    2. **실행**:
       - **정보가 충분할 경우**: `continue_iterate`를 `false`로 설정하고 `llm_output`에 최종 답변을 작성하세요.
       - **정보가 부족할 경우**: `continue_iterate`를 `true`로 설정하고, `llm_output`에는 다음 검색이 필요한 이유를, `search_query`에는 현재 정보의 약점을 보완할 구체적인 다음 검색어를 작성하세요.
    """

        return f"""
    당신은 체계적인 분석을 통해 품질 높은 답변을 생성하는 AI 에이전트입니다.

    [대화 히스토리]
    {history_text}

    [사용자 질문]
    {user_input}

    [현재까지 수집된 정보]
    {context if context else "아직 수집된 정보가 없습니다."}

    **[핵심 원칙]**
    - 수집된 정보에 없는 내용은 추측하거나 일반적인 지식으로 보완하지 마세요.
    - 정보가 부족하다면 솔직하게 "정보가 부족하다"고 답변하세요.

    {action_instruction}
    """

    def _build_deeper_prompt(self, user_input: str, context: str, iteration: int, conversation_history: List[Dict[str, str]], is_final_iteration: bool) -> str:
        """
        Deeper 모드용 프롬프트: 다각적이고 심층적인 분석에 집중합니다.
        """
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-7:]])
        strategy = self._get_iteration_strategy(iteration)
        
        if is_final_iteration:
            action_instruction = """
    **[최종 종합 및 검증 지침]**
    이번이 마지막 단계입니다. 더 이상의 검색은 없습니다.
    1. **분석**: 현재까지 수집된 모든 정보를 종합하고, 이 정보들이 사용자의 질문에 답변하기에 충분한지 평가하세요.
    2. **실행**: `continue_iterate`를 `false`로 설정하고, 다음 중 하나를 선택하세요:
       - **충분한 정보가 있는 경우**: 수집된 정보를 바탕으로 완전하고 정확한 최종 답변을 `llm_output`에 작성하세요.
       - **정보가 불충분한 경우**: `llm_output`에 "현재 수집된 정보로는 완전한 답변을 드리기 어렵습니다."라고 명시하고, 수집된 정보의 한계와 부족한 부분을 구체적으로 설명하세요.
    """
        else:
            action_instruction = f"""
    **[현재 단계({iteration}/{self.max_iterations}) 심층 분석 지침]**
    **이번 단계 목표**: {strategy}
    1. **분석**: 위 목표에 따라 현재까지 수집된 정보를 분석하세요. 사용자의 숨겨진 의도나 질문의 여러 측면을 고려하여, 목표 달성을 위해 어떤 정보가 더 필요한지 식별하세요.
    2. **실행**:
       - **현재 정보로 충분하거나 더 이상 진행이 무의미하다면**: `continue_iterate`를 `false`로 설정하고 `llm_output`에 최종 답변을 작성하세요.
       - **추가 탐색이 필요하다면**: `continue_iterate`를 `true`로 설정하고, `llm_output`에는 현재까지의 분석 내용과 다음 탐색의 필요성을, `search_query`에는 이번 단계 목표에 맞는 새로운 관점의 검색어를 작성하세요.
    """

        return f"""
    당신은 포괄적이고 심층적인 분석을 통해 완전한 답변을 생성하는 전문 AI 리서처입니다.

    [대화 히스토리]
    {history_text}

    [사용자 질문]
    {user_input}

    [누적 수집된 정보]
    {context if context else "아직 수집된 정보가 없습니다."}

    **[핵심 원칙]**
    - 수집된 정보만을 바탕으로 답변하세요. 추측이나 일반 지식으로 빈 공간을 채우지 마세요.
    - 정보가 불충분하면 그 사실을 명확히 밝히고 어떤 정보가 부족한지 설명하세요.

    {action_instruction}
    """
    def _get_iteration_strategy(self, iteration: int) -> str:
        """Deeper 모드의 반복 단계별 전략 가이드를 반환합니다."""
        strategies = {
            1: "기초 정보 수집: 질문의 핵심 개념과 관련된 기본 사실을 확보합니다.",
            2: "세부 정보 탐색: 구체적인 사례, 데이터, 통계 등 상세 내용을 수집합니다.",
            3: "맥락 및 배경 확장: 관련 역사, 배경 지식, 주변 분야 정보를 탐색합니다.",
            4: "다각적 관점 확보: 상반된 의견, 다른 시각, 전문가 비평 등을 찾아봅니다.",
            5: "정보 검증 및 종합: 수집된 정보들의 신뢰성을 교차 확인하고 최종 답변을 위한 누락된 부분을 보완합니다."
        }
        return strategies.get(iteration, "종합적인 정보를 수집합니다.")
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
