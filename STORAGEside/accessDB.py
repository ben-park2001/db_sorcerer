# Dummy Authorization Metadata DB
class DummyAuthDB:
    def __init__(self):
        # Users table
        self.users = {
            "user1": {"role": "employee"},
            "user2": {"role": "guest"},
            "admin": {"role": "admin"}
        }

        # Paths table
        self.paths = {
            "path1": {"path": "newsadded.docx", "description": "News added document"},
            "path2": {"path": "sample.txt", "description": "Sample text file"},
            "path3": {"path": "sample_2.txt", "description": "Sample text file 2"},
            "path4": {"path": "sample_3.txt", "description": "Sample text file 3"},
            "path5": {"path": "뉴스2.hwp", "description": "Korean news document"},
            "path6": {"path": "신문3.pdf", "description": "Korean newspaper PDF"},
            "path7": {"path": "sample copy.txt", "description": "Sample copy text file"},
            "path8": {"path": "[경제로세상읽기] 왜 그들은 자백을 했을까.pdf", "description": "Economic reading - confession analysis PDF"},
            "path9": {"path": "암시장에서의 달러 환전 유의 공지.pdf", "description": "Black market dollar exchange notice PDF"},
            "path10": {"path": "전력경제 레포트 (1).pdf", "description": "Power economy report PDF"}
        }

        # Permissions table
        self.permissions = [
            # user1 (employee) permissions
            {"user_id": "user1", "path_id": "path1", "permission": "read"},
            {"user_id": "user1", "path_id": "path2", "permission": "read"},
            {"user_id": "user1", "path_id": "path3", "permission": "read"},
            {"user_id": "user1", "path_id": "path4", "permission": "read"},
            {"user_id": "user1", "path_id": "path7", "permission": "read"},
            
            # user2 (guest) permissions - limited access
            {"user_id": "user2", "path_id": "path2", "permission": "read"},
            {"user_id": "user2", "path_id": "path3", "permission": "read"},
            {"user_id": "user2", "path_id": "path5", "permission": "read"},
            {"user_id": "user2", "path_id": "path7", "permission": "read"},
            
            # admin permissions - full access
            {"user_id": "admin", "path_id": "path1", "permission": "read"},
            {"user_id": "admin", "path_id": "path2", "permission": "read"},
            {"user_id": "admin", "path_id": "path3", "permission": "read"},
            {"user_id": "admin", "path_id": "path4", "permission": "read"},
            {"user_id": "admin", "path_id": "path5", "permission": "read"},
            {"user_id": "admin", "path_id": "path6", "permission": "read"},
            {"user_id": "admin", "path_id": "path7", "permission": "read"},
            {"user_id": "admin", "path_id": "path8", "permission": "read"},
            {"user_id": "admin", "path_id": "path9", "permission": "read"},
            {"user_id": "admin", "path_id": "path10", "permission": "read"}
        ]

    def get_authorized_paths(self, user_id: str):
        """
        Retrieve the list of authorized paths for a given user.

        Args:
            user_id (str): The ID of the user.

        Returns:
            list: A list of paths the user is authorized to access.
        """
        authorized_paths = []
        for perm in self.permissions:
            if perm["user_id"] == user_id:
                path_id = perm["path_id"]
                authorized_paths.append(self.paths[path_id]["path"])
        return authorized_paths
