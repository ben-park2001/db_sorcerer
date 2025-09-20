# Dummy Authorization Metadata DB
class DummyAuthDB:
    def __init__(self):
        # Users table
        self.users = {
            "guest": {"role": "guest"},
            "user1": {"role": "employee"},
            "user2": {"role": "employee"}, 
            "admin": {"role": "admin"}
        }

        # 폴더별 파일 구조
        self.folder_structure = {
            "confidential": [
                "암시장에서의 달러 환전 유의 공지.pdf",
                "[경제로세상읽기] 왜 그들은 자백을 했을까.pdf"
            ],
            "project1": [
                "newsadded.docx",
                "전력경제 레포트 (1).pdf"
            ],
            "project2": [
                "뉴스2.hwp",
                "신문3.pdf"
            ],
            "company_events": [
                "sample.txt",
                "sample_2.txt"
            ],
            "company_important_notice": [
                "sample_3.txt"
            ],
            "company_promotion": [
                "sample copy.txt"
            ]
        }

        # 사용자별 폴더 접근 권한
        self.folder_permissions = {
            "guest": ["company_events","company_important_notice","company_promotion"],
            "user1": ["project1", "company_events","company_important_notice","company_promotion"],
            "user2": ["project2", "company_events","company_important_notice","company_promotion"],
            "admin": ["confidential", "project1", "project2", "company_events","company_important_notice","company_promotion"]
        }

        # 폴더별 좋아요 누른 사용자 목록
        self.folder_liked_users = {
            "confidential": ["admin"],
            "project1": ["user1", "admin"],
            "project2": ["user2", "admin"],
            "company_events": ["guest", "user2", "admin"],
            "company_important_notice": ["user1", "user2", "admin"],
            "company_promotion": ["guest", "user1"]
        }

    def get_authorized_paths(self, user_id: str):
        """
        Retrieve the list of authorized paths for a given user.

        Args:
            user_id (str): The ID of the user.

        Returns:
            list: A list of paths the user is authorized to access.
        """
        authorized_paths = []
        
        # 사용자의 접근 가능한 폴더 목록 가져오기
        allowed_folders = self.folder_permissions.get(user_id, [])
        
        # 각 허용된 폴더의 파일들을 경로에 추가
        for folder in allowed_folders:
            if folder in self.folder_structure:
                for filename in self.folder_structure[folder]:
                    # 폴더/파일명 형태로 전체 경로 생성
                    full_path = f"{folder}/{filename}"
                    authorized_paths.append(full_path)
        
        return authorized_paths

    def add_file_to_folder(self, folder_name: str, filename: str):
        """
        Add a file to the specified folder structure.
        
        Args:
            folder_name (str): The folder to add the file to
            filename (str): The name of the file to add
        """
        if folder_name in self.folder_structure:
            if filename not in self.folder_structure[folder_name]:
                self.folder_structure[folder_name].append(filename)
                print(f"[+] Added file '{filename}' to folder '{folder_name}'")
            else:
                print(f"[!] File '{filename}' already exists in folder '{folder_name}'")
        else:
            print(f"[x] Folder '{folder_name}' not found in folder structure")

    def remove_file_from_folder(self, folder_name: str, filename: str):
        """
        Remove a file from the specified folder structure.
        
        Args:
            folder_name (str): The folder to remove the file from
            filename (str): The name of the file to remove
        """
        if folder_name in self.folder_structure:
            if filename in self.folder_structure[folder_name]:
                self.folder_structure[folder_name].remove(filename)
                print(f"[-] Removed file '{filename}' from folder '{folder_name}'")
            else:
                print(f"[!] File '{filename}' not found in folder '{folder_name}'")
        else:
            print(f"[x] Folder '{folder_name}' not found in folder structure")

    def update_file_structure(self, file_path: str, operation: str):
        """
        Update file structure based on file path and operation.
        
        Args:
            file_path (str): Relative path of the file (folder/filename format)
            operation (str): 'create' or 'delete'
        """
        try:
            # Parse folder and filename from path
            if '/' in file_path:
                folder_name, filename = file_path.split('/', 1)
            else:
                print(f"[!] Invalid file path format: {file_path}. Expected 'folder/filename'")
                return
            
            if operation == 'create':
                self.add_file_to_folder(folder_name, filename)
            elif operation == 'delete':
                self.remove_file_from_folder(folder_name, filename)
            else:
                print(f"[!] Unknown operation: {operation}. Use 'create' or 'delete'")
                
        except Exception as e:
            print(f"[x] Error updating file structure: {e}")

    def get_folder_liked_users(self, folder_name: str):
        """
        폴더에 좋아요를 누른 사용자 목록을 반환
        
        Args:
            folder_name (str): 폴더명
            
        Returns:
            list: 해당 폴더에 좋아요를 누른 사용자 목록
        """
        return self.folder_liked_users.get(folder_name, [])
