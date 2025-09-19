"""
FileRetriever 사용 예시
test_files 디렉토리의 파일들을 검색하는 간결한 예시
"""

from retriever import FileRetriever

def main():
    # FileRetriever 초기화
    retriever = FileRetriever()
    
    try:
        # 검색할 쿼리
        query = "computer, ai and gpu"
        
        print(f"🔍 검색 쿼리: '{query}'")
        print("-" * 50)
        
        # chunk 검색 및 반환
        results = retriever.search_chunks(query, top_n=3)
        
        # print(results)

        if results:
            print(f"✅ {len(results)}개의 관련 내용을 찾았습니다:\n")
            for i, chunk in enumerate(results, 1):
                print(f"📄 결과 {i}:")
                print(f"{chunk[:200]}...")  # 처음 200자만 출력
                print("-" * 30)
        else:
            print("❌ 관련 내용을 찾을 수 없습니다.")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    
    finally:
        # 연결 종료
        retriever.close()

if __name__ == "__main__":
    main()