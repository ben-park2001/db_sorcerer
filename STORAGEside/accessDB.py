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
            "path1": {"path": "/test_files/newsadded.docx", "description": "News added document"},
            "path2": {"path": "/test_files/sample.txt", "description": "Sample text file"},
            "path3": {"path": "/test_files/sample_2.txt", "description": "Sample text file 2"},
            "path4": {"path": "/test_files/뉴스2.hwp", "description": "Korean news document"},
            "path5": {"path": "/test_files/신문3.pdf", "description": "Korean newspaper PDF"}
        }

        # Permissions table
        self.permissions = [
            {"user_id": "user1", "path_id": "path1", "permission": "read"},
            {"user_id": "user1", "path_id": "path2", "permission": "read"},
            {"user_id": "user1", "path_id": "path3", "permission": "read"},
            {"user_id": "user2", "path_id": "path2", "permission": "read"},
            {"user_id": "user2", "path_id": "path4", "permission": "read"},
            {"user_id": "admin", "path_id": "path1", "permission": "read"},
            {"user_id": "admin", "path_id": "path2", "permission": "read"},
            {"user_id": "admin", "path_id": "path3", "permission": "read"},
            {"user_id": "admin", "path_id": "path4", "permission": "read"},
            {"user_id": "admin", "path_id": "path5", "permission": "read"}
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
