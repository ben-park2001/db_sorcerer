"""
파일 전처리기 (File Preprocessor)
- file_watcher로부터 파일 변경사항(C/U/D) 수신 및 처리
- 다른 노드의 파일 요청을 file_watcher에 중계
- 처리된 파일 정보를 다음 노드로 전송
"""

import os
import time
import json
import base64
import threading
import struct
import zlib
import re
import unicodedata
from pathlib import Path
from typing import Dict, Any, Optional, Union

import zmq
from docx import Document
import pdfplumber
import olefile


def read_file(file_path: str) -> str:
    """
    주어진 경로의 파일(.txt, .docx, .pdf, .hwp)을 읽어 텍스트 내용을 문자열로 반환합니다.
    한국어 파일에 최적화되어 있습니다.

    Args:
        file_path (str): 읽을 파일의 경로

    Returns:
        str: 파일에서 추출한 텍스트 내용

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 경우 발생합니다.
        ValueError: 지원하지 않는 파일 형식일 경우 발생합니다.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"오류: '{file_path}' 파일을 찾을 수 없습니다.")

    # 파일 확장자를 소문자로 추출
    _, extension = os.path.splitext(file_path)
    extension = extension.lower()

    full_text = ""

    try:
        if extension == '.txt':
            # UTF-8으로 먼저 시도하고, 오류 발생 시 CP949로 재시도 (Windows 환경 호환)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    full_text = f.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='cp949') as f:
                    full_text = f.read()

        elif extension == '.docx':
            doc = Document(file_path)
            text_list = [para.text for para in doc.paragraphs]
            full_text = '\n'.join(text_list)

        elif extension == '.pdf':
            with pdfplumber.open(file_path) as pdf:
                text_list = [page.extract_text() for page in pdf.pages if page.extract_text()]
                full_text = '\n'.join(text_list)

        elif extension == '.hwp':
            full_text = _extract_hwp_file(file_path)

        else:
            raise ValueError(
                f"지원하지 않는 파일 형식입니다: '{extension}'. "
                "지원 형식: .txt, .docx, .pdf, .hwp"
            )
            
    except Exception as e:
        # 파일 처리 중 발생할 수 있는 모든 예외를 처리합니다.
        print(f"'{file_path}' 파일 처리 중 오류 발생: {e}")
        return "" # 오류 발생 시 빈 문자열 반환

    return full_text


def _extract_hwp_file(file_path: str) -> str:
    """Main HWP extraction logic."""

    # HWP file constants
    FILE_HEADER_SECTION = "FileHeader"
    HWP_SUMMARY_SECTION = "\x05HwpSummaryInformation"
    SECTION_NAME_LENGTH = len("Section")
    BODYTEXT_SECTION = "BodyText"
    HWP_TEXT_TAGS = [67]

    ole_file = olefile.OleFileIO(file_path)
    directories = ole_file.listdir()

    # Validate HWP file
    has_header = [FILE_HEADER_SECTION] in directories
    has_summary = [HWP_SUMMARY_SECTION] in directories
    if not (has_header and has_summary):
        ole_file.close()
        raise ValueError("Not a valid HWP file")

    # Check if compressed
    header_stream = ole_file.openstream("FileHeader")
    header_data = header_stream.read()
    is_compressed = (header_data[36] & 1) == 1

    # Get body sections
    section_numbers = []
    for directory in directories:
        if directory[0] == BODYTEXT_SECTION:
            section_num = int(directory[1][SECTION_NAME_LENGTH:])
            section_numbers.append(section_num)

    sections = [f"BodyText/Section{num}" for num in sorted(section_numbers)]

    # Extract text from all sections
    extracted_text = ""
    for section in sections:
        extracted_text += _extract_hwp_section_text(
            ole_file, section, is_compressed, HWP_TEXT_TAGS
        )
        extracted_text += "\n"

    ole_file.close()
    return extracted_text.strip()


def _extract_hwp_section_text(
    ole_file, section_name: str, is_compressed: bool, hwp_text_tags: list
) -> str:
    """Extract text from a specific HWP section."""
    section_stream = ole_file.openstream(section_name)
    raw_data = section_stream.read()

    if is_compressed:
        try:
            unpacked_data = zlib.decompress(raw_data, -15)
        except zlib.error:
            return ""
    else:
        unpacked_data = raw_data

    # Parse section data to extract text content
    size = len(unpacked_data)
    position = 0
    text_content = ""

    while position < size:
        try:
            header = struct.unpack_from("<I", unpacked_data, position)[0]
            record_type = header & 0x3FF
            record_length = (header >> 20) & 0xFFF

            if record_type in hwp_text_tags:
                record_data = unpacked_data[position + 4 : position + 4 + record_length]
                decoded_text = _decode_hwp_record_data(record_data)
                if decoded_text:
                    text_content += decoded_text + "\n"

            position += 4 + record_length

        except (struct.error, IndexError):
            # Skip problematic data and continue
            position += 1
            continue

    return text_content


def _decode_hwp_record_data(record_data: bytes) -> str:
    """Decode HWP record data to text."""
    try:
        decoded_text = record_data.decode("utf-16le")

        # Clean extracted text by removing unwanted characters
        # Remove Chinese characters
        text = re.sub(r"[\u4e00-\u9fff]+", "", decoded_text)

        # Remove control characters
        text = "".join(char for char in text if unicodedata.category(char)[0] != "C")

        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text
    except UnicodeDecodeError:
        return ""


class FilePreprocessor:
    def __init__(self, 
                 pull_port=5555,           # file_watcher PUSH 소켓으로부터 수신
                 file_request_port=5556,   # file_watcher ROUTER 소켓에 요청
                 rep_port=5557,           # 다른 노드들의 요청 처리
                 push_port=5558):         # 다음 노드로 전송
        
        self.pull_port = pull_port
        self.file_request_port = file_request_port
        self.rep_port = rep_port
        self.push_port = push_port
        
        # ZeroMQ context 생성
        self.context = zmq.Context()
        
        # PULL 소켓 (file_watcher로부터 파일 변경사항 수신)
        self.pull_socket = self.context.socket(zmq.PULL)
        self.pull_socket.connect(f"tcp://localhost:{self.pull_port}")
        
        # REQ 소켓 (file_watcher에게 파일 요청)
        self.req_socket = self.context.socket(zmq.REQ)
        self.req_socket.connect(f"tcp://localhost:{self.file_request_port}")
        
        # REP 소켓 (다른 노드들의 파일 요청 처리)
        self.rep_socket = self.context.socket(zmq.REP)
        self.rep_socket.bind(f"tcp://*:{self.rep_port}")
        
        # PUSH 소켓 (다음 노드로 전송)
        self.push_socket = self.context.socket(zmq.PUSH)
        self.push_socket.bind(f"tcp://*:{self.push_port}")
        
        # 실행 상태 플래그
        self.running = False
        
        print(f"🔧 File Preprocessor 초기화 완료")
        print(f"   📥 파일 변경사항 수신: PULL tcp://localhost:{self.pull_port}")
        print(f"   📤 파일 요청: REQ tcp://localhost:{self.file_request_port}")
        print(f"   🔄 파일 요청 처리: REP tcp://*:{self.rep_port}")
        print(f"   📤 다음 노드 전송: PUSH tcp://*:{self.push_port}")
    
    def _extract_file_content(self, file_path: str, encoded_content: Optional[str] = None) -> Optional[str]:
        """
        파일에서 텍스트 내용을 추출합니다.
        
        Args:
            file_path: 파일 경로
            encoded_content: base64 인코딩된 파일 내용 (있는 경우)
            
        Returns:
            추출된 텍스트 내용 또는 None
        """
        try:
            if encoded_content:
                # base64 디코딩된 내용으로 임시 파일 생성하여 처리
                decoded_content = base64.b64decode(encoded_content)
                temp_path = f"temp_{int(time.time())}_{os.path.basename(file_path)}"
                
                try:
                    with open(temp_path, 'wb') as f:
                        f.write(decoded_content)
                    
                    # file_reader로 내용 추출
                    content = read_file(temp_path)
                    return content
                    
                finally:
                    # 임시 파일 삭제
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            else:
                # 파일 경로로 직접 읽기
                if os.path.exists(file_path):
                    return read_file(file_path)
                else:
                    print(f"⚠️ 파일을 찾을 수 없습니다: {file_path}")
                    return None
                    
        except Exception as e:
            print(f"❌ 파일 내용 추출 실패 ({file_path}): {e}")
            return None
    
    def _process_file_change(self, message: Dict[str, Any]):
        """
        파일 변경사항을 처리합니다.
        
        Args:
            message: file_watcher로부터 받은 메시지
        """
        try:
            event_type = message.get('event_type')
            file_path = message.get('file_path')
            user_id = message.get('user_id')
            timestamp = message.get('timestamp')
            file_content = message.get('file_content')  # base64 encoded
            
            # 메시지 수신 로그 출력
            print(f"� [RECEIVE <- file_watcher] 파일 변경사항 수신")
            print(f"   📄 파일: {file_path}")
            print(f"   📋 이벤트: {event_type}")
            print(f"   👤 사용자: {user_id}")
            print(f"   📅 타임스탬프: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}")
            
            if event_type != 'delete':
                file_size = message.get('file_size', 0)
                print(f"   📏 파일 크기: {file_size:,} bytes")
                has_content = bool(file_content)
                print(f"   🔒 Base64 인코딩: {'✅' if has_content else '❌'}")
                
                if event_type == 'update':
                    diff_type = message.get('diff_type')
                    diff_content = message.get('diff_content')
                    if diff_type:
                        print(f"   📊 Diff 타입: {diff_type}")
                        print(f"   📊 Diff 크기: {len(diff_content)} chars" if diff_content else "   📊 Diff: 없음")
            
            print("   " + "-" * 50)
            
            # 다음 노드로 전송할 메시지 구성
            processed_message = {
                'event_type': event_type,
                'file_path': file_path,
                'user_id': user_id,
                'timestamp': timestamp,
                'processed_timestamp': time.time(),
                'processor': 'file_preprocessor'
            }
            
            if event_type == 'delete':
                # 삭제: 파일 경로만 전송
                processed_message['content'] = None
                processed_message['status'] = 'deleted'
                
            elif event_type in ['create', 'update']:
                # 생성/수정: 파일 내용 추출
                extracted_content = self._extract_file_content(str(file_path), file_content)
                
                if extracted_content:
                    processed_message['content'] = extracted_content
                    processed_message['content_length'] = len(extracted_content)
                    processed_message['status'] = 'processed'
                    
                    # 수정인 경우 diff 정보도 포함
                    if event_type == 'update':
                        processed_message['diff_type'] = message.get('diff_type')
                        processed_message['diff_content'] = message.get('diff_content')
                        processed_message['relative_path'] = message.get('relative_path')
                        
                    print(f"✅ 파일 내용 추출 완료: {len(extracted_content)} 문자")
                else:
                    processed_message['content'] = None
                    processed_message['status'] = 'extraction_failed'
                    print(f"❌ 파일 내용 추출 실패: {file_path}")
            
            # 다음 노드로 전송
            self.push_socket.send_json(processed_message)
            
            # 전송 로그 출력
            print(f"📤 [SEND -> file_postprocessor] 처리된 파일 정보 전송")
            print(f"   📄 파일: {file_path}")
            print(f"   📋 이벤트: {event_type}")
            print(f"   ✅ 처리 상태: {processed_message.get('status')}")
            
            if processed_message.get('content'):
                content_length = processed_message.get('content_length', 0)
                print(f"   📏 추출된 내용 길이: {content_length:,} 문자")
            
            if event_type == 'update' and processed_message.get('diff_content'):
                print(f"   📊 Diff 정보: 포함됨")
            
            print(f"   📅 처리 시간: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(processed_message['processed_timestamp']))}")
            print(f"   🚀 전송 포트: tcp://*:{self.push_port}")
            print("   " + "-" * 50)
            
        except Exception as e:
            print(f"❌ 파일 변경사항 처리 중 오류: {e}")
    
    def _request_file_from_watcher(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        file_watcher에게 파일을 요청합니다.
        
        Args:
            file_path: 요청할 파일 경로
            
        Returns:
            file_watcher로부터 받은 응답 또는 None
        """
        try:
            # file_watcher에게 파일 요청
            request = {'file_path': file_path}
            print(f"📤 [REQUEST -> file_watcher] 파일 요청 전송: {file_path}")
            self.req_socket.send_json(request)
            
            # 응답 수신 (타임아웃 설정)
            if self.req_socket.poll(timeout=5000):  # 5초 타임아웃
                response = self.req_socket.recv_json()
                if isinstance(response, dict):
                    print(f"📥 [RECEIVE <- file_watcher] 응답 수신: {response.get('status', 'unknown')}")
                    return response
                else:
                    print(f"⚠️ 예상하지 못한 응답 형식: {response}")
                    return None
            else:
                print(f"⏰ file_watcher 응답 타임아웃: {file_path}")
                return None
                
        except Exception as e:
            print(f"❌ file_watcher 요청 중 오류: {e}")
            return None
    
    def _handle_file_request(self):
        """
        다른 노드들의 파일 요청을 처리합니다.
        """
        while self.running:
            try:
                # 파일 요청 수신 (타임아웃 설정)
                if self.rep_socket.poll(timeout=1000):  # 1초 타임아웃
                    request = self.rep_socket.recv_json()
                    
                    if not isinstance(request, dict):
                        print(f"⚠️ 잘못된 요청 형식: {request}")
                        self.rep_socket.send_json({
                            'status': 'error',
                            'error': '잘못된 요청 형식'
                        })
                        continue
                    
                    file_path = request.get('file_path')
                    if not file_path or not isinstance(file_path, str):
                        print(f"⚠️ 잘못된 파일 경로: {file_path}")
                        self.rep_socket.send_json({
                            'status': 'error',
                            'error': '유효하지 않은 파일 경로'
                        })
                        continue
                        
                    print(f"📥 [REQUEST] 파일 요청 수신: {file_path}")
                    
                    # file_watcher에게 파일 요청
                    print(f"🔄 [REQUEST -> file_watcher] 파일 데이터 요청 중...")
                    watcher_response = self._request_file_from_watcher(file_path)
                    
                    if watcher_response and watcher_response.get('status') == 'success':
                        print(f"✅ [RECEIVE <- file_watcher] 파일 데이터 수신 성공")
                        file_size = watcher_response.get('file_size', 0)
                        print(f"   📏 파일 크기: {file_size:,} bytes")
                        
                        # 파일 내용 추출
                        file_content = watcher_response.get('file_content')
                        extracted_content = self._extract_file_content(file_path, file_content)
                        
                        if extracted_content:
                            response = {
                                'status': 'success',
                                'file_path': file_path,
                                'content': extracted_content,
                                'content_length': len(extracted_content),
                                'file_name': watcher_response.get('file_name'),
                                'file_size': watcher_response.get('file_size')
                            }
                            print(f"✅ 파일 내용 추출 완료: {len(extracted_content):,} 문자")
                            print(f"📤 [RESPONSE] 클라이언트에게 응답 전송")
                        else:
                            response = {
                                'status': 'error',
                                'error': '파일 내용 추출 실패',
                                'file_path': file_path
                            }
                            print(f"❌ 파일 내용 추출 실패")
                    else:
                        error_msg = watcher_response.get('error', 'file_watcher 요청 실패') if watcher_response else 'file_watcher 응답 없음'
                        print(f"❌ [ERROR <- file_watcher] {error_msg}")
                        response = {
                            'status': 'error',
                            'error': error_msg,
                            'file_path': file_path
                        }
                    
                    # 응답 전송
                    self.rep_socket.send_json(response)
                    
            except Exception as e:
                if self.running:  # 종료 중이 아닌 경우에만 에러 출력
                    print(f"❌ 파일 요청 처리 중 오류: {e}")
    
    def _listen_file_changes(self):
        """
        file_watcher로부터 파일 변경사항을 수신합니다.
        """
        while self.running:
            try:
                # 파일 변경사항 수신 (타임아웃 설정)
                if self.pull_socket.poll(timeout=1000):  # 1초 타임아웃
                    message = self.pull_socket.recv_json()
                    
                    if isinstance(message, dict):
                        self._process_file_change(message)
                    else:
                        print(f"⚠️ 잘못된 메시지 형식: {message}")
                    
            except Exception as e:
                if self.running:  # 종료 중이 아닌 경우에만 에러 출력
                    print(f"❌ 파일 변경사항 수신 중 오류: {e}")
    
    def start(self):
        """
        File Preprocessor를 시작합니다.
        """
        print("=" * 60)
        print("🔮 DB Sorcerer File Preprocessor 시작")
        print("=" * 60)
        
        self.running = True
        
        # 파일 변경사항 수신 스레드
        change_thread = threading.Thread(target=self._listen_file_changes, daemon=True)
        change_thread.start()
        
        # 파일 요청 처리 스레드
        request_thread = threading.Thread(target=self._handle_file_request, daemon=True)
        request_thread.start()
        
        try:
            print("\n📋 서비스 상태:")
            print(f"  • 파일 변경사항 수신: 활성화됨")
            print(f"  • 파일 요청 처리: 활성화됨")
            print(f"  • 다음 노드 전송: 대기 중")
            print("\n⏹️  종료하려면 Ctrl+C를 누르세요")
            print("-" * 60)
            
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n🛑 시스템 종료 중...")
            self.running = False
            
            # 스레드 종료 대기
            change_thread.join(timeout=1)
            request_thread.join(timeout=1)
            
        finally:
            # ZeroMQ 정리
            self.pull_socket.close()
            self.req_socket.close()
            self.rep_socket.close()
            self.push_socket.close()
            self.context.term()
            
            print("✅ File Preprocessor 종료 완료")


def main():
    """메인 실행 함수"""
    # 설정값들
    PULL_PORT = 5555      # file_watcher PUSH 소켓으로부터 수신
    FILE_REQUEST_PORT = 5556  # file_watcher ROUTER 소켓에 요청
    REP_PORT = 5557       # 다른 노드들의 요청 처리
    PUSH_PORT = 5558      # 다음 노드로 전송
    
    # FilePreprocessor 인스턴스 생성 및 시작
    preprocessor = FilePreprocessor(
        pull_port=PULL_PORT,
        file_request_port=FILE_REQUEST_PORT,
        rep_port=REP_PORT,
        push_port=PUSH_PORT
    )
    
    preprocessor.start()


if __name__ == "__main__":
    main()
