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
            "path1": {"path": "/data/file1.txt", "description": "File 1"},
            "path2": {"path": "/data/file2.txt", "description": "File 2"},
            "path3": {"path": "/data/file3.txt", "description": "File 3"}
        }

        # Permissions table
        self.permissions = [
            {"user_id": "user1", "path_id": "path1", "permission": "read"},
            {"user_id": "user1", "path_id": "path2", "permission": "read"},
            {"user_id": "user2", "path_id": "path3", "permission": "read"},
            {"user_id": "admin", "path_id": "path1", "permission": "read"},
            {"user_id": "admin", "path_id": "path2", "permission": "read"},
            {"user_id": "admin", "path_id": "path3", "permission": "read"}
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
