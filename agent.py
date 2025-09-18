"""
RAG LLM Agent - MVP
- 사용자 질문을 받아서 관련 문서를 검색하고 LLM으로 답변 생성
"""

from Models.llm import LLM
from Retriever.retriever import FileRetriever


class RAGAgent:
    """간단한 RAG LLM Agent"""
    
    def __init__(self, top_k_chunks=3):
        """
        Args:
            top_k_chunks: 검색할 상위 chunk 개수
        """
        self.retriever = FileRetriever()
        self.top_k_chunks = top_k_chunks
        print("🤖 RAG Agent 초기화 완료")
    
    def answer(self, question: str) -> str:
        """
        질문에 대한 답변을 생성합니다.
        
        Args:
            question: 사용자 질문
            
        Returns:
            LLM이 생성한 답변
        """
        print(f"\n❓ 질문: {question}")
        
        # 1. 관련 문서 검색
        print("🔍 관련 문서 검색 중...")
        relevant_chunks = self.retriever.search_chunks(question, top_n=self.top_k_chunks)
        
        if not relevant_chunks:
            return "죄송합니다. 관련된 문서를 찾을 수 없습니다."
        
        # 2. 컨텍스트 구성
        context = "\n\n".join([f"문서 {i+1}:\n{chunk}" for i, chunk in enumerate(relevant_chunks)])
        
        # 3. 프롬프트 생성
        prompt = self._create_prompt(question, context)
        
        # 4. LLM으로 답변 생성
        print("🧠 답변 생성 중...")
        answer = LLM(prompt)
        
        print("✅ 답변 완료")
        return answer
    
    def _create_prompt(self, question: str, context: str) -> str:
        """RAG 프롬프트를 생성합니다."""
        return f"""다음 문서들을 참고하여 질문에 답변해주세요.

참고 문서:
{context}

질문: {question}

답변: 위 문서들의 내용을 바탕으로 정확하고 도움이 되는 답변을 제공해주세요."""
    
    def close(self):
        """리소스 정리"""
        self.retriever.close()
        print("🔌 RAG Agent 종료")


def main():
    """간단한 테스트 실행"""
    agent = RAGAgent()
    
    try:
        # 테스트 질문들
        test_questions = [
            "이 프로젝트는 무엇에 관한 것인가요?",
            "파일 처리는 어떻게 작동하나요?",
        ]
        
        for question in test_questions:
            answer = agent.answer(question)
            print(f"\n💬 답변: {answer}\n")
            print("-" * 50)
    
    except KeyboardInterrupt:
        print("\n👋 종료 중...")
    
    finally:
        agent.close()


if __name__ == "__main__":
    main()
