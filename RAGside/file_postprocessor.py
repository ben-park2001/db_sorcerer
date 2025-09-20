import zmq
import time
from Models.embedding import Embedding
from Models.llm import LLM, LLM_small
from db import create_data, delete_data

#클라이언트는 요약하는 애는 전부다 sllm으로 수정 필요
class FilePostprocessor:
    def __init__(self, pull_port=5558):
        self.context = zmq.Context()
        self.pull_socket = self.context.socket(zmq.PULL)
        self.pull_socket.connect(f"tcp://localhost:{pull_port}")
        self.running = False

    def handle_create(self, message):
        """파일 생성 처리"""
        file_path = message.get('file_path')
        content = message.get('content')
        print(f"🔨 [CREATE] 파일 생성 처리 시작: {file_path}")

        if content:
            print(f"   📝 텍스트 청킹 시작...")
            chunks, offsets = self._chunk_content(content, file_path)
            print(f"   ✅ 청킹 완료: {len(chunks)}개 청크 생성")
            
            print(f"   🔍 임베딩 생성 시작...")
            embeddings = self._process_content(chunks, file_path, offsets)
            print(f"   ✅ 임베딩 생성 완료: {len(embeddings)}개 벡터")
            
            print(f"   💾 ChromaDB 업로드 시작...")
            self._upload_embeddings(embeddings, file_path)
            print(f"   ✅ ChromaDB 업로드 완료")
            
            print(f"   📊 요약 생성 시작...")
            self._summarize(chunks, file_path)
            print(f"   ✅ 요약 생성 완료")
        else:
            print(f"   ⚠️ 파일 내용이 없습니다.")
            
        print(f"🎉 [CREATE] 파일 생성 처리 완료: {file_path}")
        print("   " + "=" * 50)

    def handle_update(self, message):
        """파일 수정 처리"""
        file_path = message.get('file_path')
        content = message.get('content')
        diff_content = message.get('diff_content')
        
        print(f"🔄 [UPDATE] 파일 수정 처리 시작: {file_path}")
        
        print(f"   🗑️ 기존 데이터 삭제 중...")
        delete_data(file_path)
        print(f"   ✅ 기존 데이터 삭제 완료")
        
        if diff_content: 
            print(f"   📊 변경사항 요약 생성 중...")
            summary = LLM_small(f"다음 변경사항을 1~2문장으로 요약해주세요: {diff_content}")
            file_name = file_path.split('\\')[-1]
            print(f"   📋 {file_name} 파일이 수정되었습니다.")
            print(f"   📍 경로: {file_path}")
            print(f"   📝 변경사항: {summary}")
        
        if content:
            print(f"   📝 텍스트 청킹 시작...")
            chunks, offsets = self._chunk_content(content, file_path)
            print(f"   ✅ 청킹 완료: {len(chunks)}개 청크 생성")
            
            print(f"   🔍 임베딩 생성 시작...")
            embeddings = self._process_content(chunks, file_path, offsets)
            print(f"   ✅ 임베딩 생성 완료: {len(embeddings)}개 벡터")
            
            print(f"   💾 ChromaDB 업로드 시작...")
            self._upload_embeddings(embeddings, file_path)
            print(f"   ✅ ChromaDB 업로드 완료")
        else:
            print(f"   ⚠️ 파일 내용이 없습니다.")
            
        print(f"🎉 [UPDATE] 파일 수정 처리 완료: {file_path}")
        print("   " + "=" * 50)

    def handle_delete(self, message):
        """파일 삭제 처리"""
        file_path = message.get('file_path')
        print(f"🗑️ [DELETE] 파일 삭제 처리 시작: {file_path}")
        
        print(f"   💾 ChromaDB에서 데이터 삭제 중...")
        delete_data(file_path)
        print(f"   ✅ ChromaDB 데이터 삭제 완료")
        
        file_name = file_path.split('\\')[-1] if '\\' in file_path else file_path.split('/')[-1]
        print(f"   📋 {file_name} 파일이 삭제되었습니다.")
        print(f"   📍 경로: {file_path}")
        
        print(f"🎉 [DELETE] 파일 삭제 처리 완료: {file_path}")
        print("   " + "=" * 50)

    def _chunk_content(self, content, file_path):
        """텍스트 청킹"""
        if not content or not content.strip():
            return [], []
        
        # 1. content를 overlap과 함께 작은 chunk들로 나누기
        pre_chunks = self._split_with_overlap(content, 1000, 200)
        
        # 2. 각 pre_chunk에서 LLM으로 의미적 끝점의 마지막 문장들 추출
        all_end_sentences = []
        for pre_chunk in pre_chunks:
            end_sentences = self._extract_end_sentences(pre_chunk)
            all_end_sentences.extend(end_sentences)
        
        # 3. 마지막 문장들의 위치를 찾아서 content를 최종 분할
        final_chunks = self._split_by_end_sentences(content, all_end_sentences)
        
        chunks = [chunk["text"] for chunk in final_chunks]
        offsets = [{
            "chunk_index": chunk["chunk_index"],
            "char_start": chunk["char_start"],
            "char_end": chunk["char_end"],
            "word_start": chunk["word_start"],
            "word_end": chunk["word_end"]
        } for chunk in final_chunks]
        
        return chunks, offsets

    def _split_with_overlap(self, content, chunk_size, overlap):
        """content를 지정된 크기로 overlap과 함께 분할"""
        chunks = []
        start = 0
        
        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunk = content[start:end]
            chunks.append(chunk)
            
            if end >= len(content):
                break
                
            start = end - overlap
        
        return chunks

    def _extract_end_sentences(self, text):
        """LLM을 사용하여 텍스트에서 의미적으로 끝나는 지점의 마지막 문장들을 추출"""
        prompt = f"""다음 텍스트에서 의미적으로 완결되는 지점들의 마지막 문장을 찾아주세요.
각 마지막 문장을 한 줄에 하나씩 출력해주세요.

텍스트:
{text}

마지막 문장들:"""
        
        try:
            response = LLM_small(prompt)
            sentences = [line.strip() for line in response.split('\n') if line.strip()]
            return sentences
        except Exception as e:
            print(f"LLM 호출 실패: {e}")
            return []

    def _split_by_end_sentences(self, content, end_sentences):
        """마지막 문장들의 위치를 기준으로 content를 최종 분할"""
        if not end_sentences:
            # LLM 실패시 단순 분할
            return [{"chunk_index": 0, "text": content, "char_start": 0, "char_end": len(content), 
                    "word_start": 0, "word_end": len(content.split()) - 1}]
        
        chunks = []
        last_end = 0
        chunk_index = 0
        
        for end_sentence in end_sentences:
            end_pos = content.find(end_sentence, last_end)
            if end_pos == -1:
                continue
                
            actual_end = end_pos + len(end_sentence)
            chunk_text = content[last_end:actual_end].strip()
            if not chunk_text:
                continue
            
            chunk = {
                "chunk_index": chunk_index,
                "text": chunk_text,
                "char_start": last_end,
                "char_end": actual_end,
                "word_start": len(content[:last_end].split()),
                "word_end": len(content[:actual_end].split()) - 1
            }
            
            chunks.append(chunk)
            last_end = actual_end
            chunk_index += 1
        
        # 마지막 남은 부분 추가
        if last_end < len(content):
            remaining_text = content[last_end:].strip()
            if remaining_text:
                chunk = {
                    "chunk_index": chunk_index,
                    "text": remaining_text,
                    "char_start": last_end,
                    "char_end": len(content),
                    "word_start": len(content[:last_end].split()),
                    "word_end": len(content.split()) - 1
                }
                chunks.append(chunk)
        
        return chunks

    def _process_content(self, chunks, file_path, offsets):
        """임베딩 배치 생성"""
        # 모든 chunks를 한 번에 배치 처리
        embedding_vectors = Embedding(chunks)
        
        # 임베딩과 오프셋 정보를 매핑하여 반환
        embeddings = []
        for i, (embedding_vector, chunk_text) in enumerate(zip(embedding_vectors, chunks)):
            embeddings.append({
                'embedding': embedding_vector,
                'text': chunk_text,
                'offset': offsets[i]
            })
        
        return embeddings

    def _summarize(self, chunks, file_path):
        """배치 청크 요약 후 최종 요약"""
        print(f"       📊 개별 청크 요약 생성 중... ({len(chunks)}개 청크)")
        
        # 모든 chunks를 한 번에 배치 처리로 요약
        prompts = [f"다음 텍스트를 1~2문장으로 요약해주세요: {chunk}" for chunk in chunks]
        chunk_summaries = [LLM_small(prompt) for prompt in prompts]
        
        print(f"       ✅ 개별 청크 요약 완료")
        print(f"       📝 최종 요약 생성 중...")
        
        # 요약들을 종합하여 최종 요약
        combined_summaries = "\n".join(chunk_summaries)
        final_summary = LLM_small(f"다음 요약들을 종합하여 최종 요약을 2~3문장으로 만들어주세요: {combined_summaries}")
        
        file_name = file_path.split('\\')[-1]
        print(f"       📋 {file_name} 파일이 생성되었습니다.")
        print(f"       📍 경로: {file_path}")
        print(f"       📝 내용: {final_summary}")
        print(f"       ✅ 최종 요약 완료")

    def _upload_embeddings(self, embeddings, file_path):
        """임베딩을 ChromaDB에 업로드"""
        print(f"       💾 ChromaDB 업로드 진행 중... ({len(embeddings)}개 임베딩)")
        
        success_count = 0
        for i, embedding_data in enumerate(embeddings):
            try:
                create_data(
                    file_path=file_path,
                    start_idx=embedding_data['offset']['char_start'],
                    end_idx=embedding_data['offset']['char_end'],
                    embedding=embedding_data['embedding']
                )
                success_count += 1
                
                # 진행률 표시 (10% 단위)
                progress = (i + 1) / len(embeddings) * 100
                if (i + 1) % max(1, len(embeddings) // 10) == 0 or i == len(embeddings) - 1:
                    print(f"       📈 업로드 진행률: {progress:.0f}% ({i + 1}/{len(embeddings)})")
                    
            except Exception as e:
                print(f"       ❌ 임베딩 업로드 실패 (청크 {i}): {e}")
        
        print(f"       ✅ ChromaDB 업로드 완료: {success_count}/{len(embeddings)} 성공")

    def process_message(self, message):
        """메시지 처리"""
        event_type = message.get('event_type')
        file_path = message.get('file_path')
        user_id = message.get('user_id')
        timestamp = message.get('timestamp')
        processed_timestamp = message.get('processed_timestamp')
        status = message.get('status')
        
        # 메시지 수신 로그 출력
        print(f"📥 [RECEIVE <- file_preprocessor] 파일 처리 메시지 수신")
        print(f"   📄 파일: {file_path}")
        print(f"   📋 이벤트: {event_type}")
        print(f"   👤 사용자: {user_id}")
        print(f"   ✅ 전처리 상태: {status}")
        
        if timestamp:
            print(f"   📅 원본 타임스탬프: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}")
        if processed_timestamp:
            print(f"   📅 처리 타임스탬프: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(processed_timestamp))}")
        
        content = message.get('content')
        if content:
            content_length = message.get('content_length', len(content))
            print(f"   📏 내용 길이: {content_length:,} 문자")
        
        if event_type == 'update':
            diff_type = message.get('diff_type')
            diff_content = message.get('diff_content')
            if diff_type:
                print(f"   📊 Diff 타입: {diff_type}")
                if diff_content:
                    print(f"   📊 Diff 크기: {len(diff_content)} chars")
        
        print("   " + "-" * 50)
        
        # 실제 처리 로직 실행
        if event_type == 'create':
            self.handle_create(message)
        elif event_type == 'update':
            self.handle_update(message)
        elif event_type == 'delete':
            self.handle_delete(message)
        else:
            print(f"❌ 알 수 없는 이벤트 타입: {event_type}")

    def start(self):
        """서비스 시작"""
        self.running = True
        print("File Postprocessor 시작...")

        try:
            while self.running:
                if self.pull_socket.poll(timeout=1000):
                    message = self.pull_socket.recv_json()
                    self.process_message(message)

        except KeyboardInterrupt:
            print("종료 중...")
        finally:
            self.pull_socket.close()
            self.context.term()

if __name__ == "__main__":
    postprocessor = FilePostprocessor()
    postprocessor.start()