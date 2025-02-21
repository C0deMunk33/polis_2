import os
import base64
import json

from libs.common import is_base64, apply_unified_diff
from libs.get_directory_structure import get_directory_structure

class FileManager:
    def __init__(self, root_directory):
        self.root_directory = os.path.abspath(root_directory)

def create_file(self, file_path, file_content):
    """
    Create a file with the given content, detecting if it's base64 encoded
    """
    if is_base64(file_content):
        # Decode base64 and write as binary
        decoded_content = base64.b64decode(file_content)
        with open(file_path, 'wb') as f:
            f.write(decoded_content)
    else:
        # Write as regular text
        with open(file_path, 'w') as f:
            f.write(file_content)

    def read_file(self, file_path, show_line_numbers=False):
        """
        Read a file and detect if content is binary/base64 or text
        Returns the content in its original format
        """
        file_path = os.path.join(self.root_directory, file_path)
        try:
            # First try reading as text
            with open(file_path, 'r') as f:
                content = f.read()
                if show_line_numbers:
                    return "\n".join([f"{i+1}: {line}" for i, line in enumerate(content.splitlines())])
                else:
                    return content
        except UnicodeDecodeError:
            # If we get Unicode error, it's likely binary content
            # Read as binary and convert to base64
            with open(file_path, 'rb') as f:
                binary_content = f.read()
                base64_content = base64.b64encode(binary_content).decode('utf-8')
                return base64_content

    def delete_file(self, file_path):
        file_path = os.path.join(self.root_directory, file_path)
        os.remove(file_path)
    
    def update_file(self, file_path, unified_diff):
        file_path = os.path.join(self.root_directory, file_path)
        with open(file_path, 'r') as f:
            file_content = f.read()
        new_content = apply_unified_diff(file_content, unified_diff)
        with open(file_path, 'w') as f:
            f.write(new_content)
    
    def create_directory(self, directory_path):
        directory_path = os.path.join(self.root_directory, directory_path)
        os.makedirs(directory_path, exist_ok=True)

    def delete_directory(self, directory_name, directory_path):
        directory_path = os.path.join(self.root_directory, directory_path)
        os.rmdir(directory_path)

    def list_file_structure(self):
        return get_directory_structure(self.root_directory)
    
    
