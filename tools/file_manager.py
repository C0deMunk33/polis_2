import os
import base64
import json
from pydantic import BaseModel
from datetime import datetime

from libs.common import is_base64, apply_unified_diff, ToolCall, ToolSchema, ToolsetDetails
from libs.get_directory_structure import get_directory_structure
from libs.agent import Agent

class FileMetadata(BaseModel):
    file_path: str
    line_count: int
    file_type: str
    file_size: int
    file_created_at: str
    file_updated_at: str
    created_by: str
    updated_by: str
    first_seen: str
    last_seen: str


class FileManager:
    def __init__(self, root_directory):
        self.root_directory = os.path.abspath(root_directory)
        self.file_metadata = {} 

        names_of_tools_to_expose = [
            "create_file",
            "read_file",
            "delete_file",
            "update_file",
            "create_directory",
        ]

        self.tool_schemas = []
        for name in names_of_tools_to_expose:
            docstring = getattr(self, name).__doc__
            tool_schema = ToolSchema.model_validate_json(docstring)
            self.tool_schemas.append(tool_schema)

        self.scan_directory()

    def scan_directory(self):
        for file in os.listdir(self.root_directory):
            file_path = os.path.join(self.root_directory, file)
            extension = os.path.splitext(file_path)[1]
            if os.path.isfile(file_path):
                if file_path in self.file_metadata:
                    # existing file, update metadata and continue
                    current_metadata = self.file_metadata[file_path]
                    current_metadata.last_seen = datetime.now().isoformat()
                    self.add_file_metadata(file_path, current_metadata)
                    continue
                # found a new file                
                line_count = 0
                if is_base64(file_path):
                    file_type = extension
                else:
                    with open(file_path, 'r') as f:
                        line_count = sum(1 for _ in f)
                    file_type = extension
                file_size = os.path.getsize(file_path)  
                file_created_at = datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
                file_updated_at = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                self.add_file_metadata(file_path,
                                       line_count=line_count,
                                       file_type=file_type,
                                       file_size=file_size,
                                       file_created_at=file_created_at,
                                       file_updated_at=file_updated_at,
                                       created_by="other",
                                       updated_by="other",
                                       first_seen=datetime.now().isoformat(),
                                       last_seen=datetime.now().isoformat())

    def add_file_metadata(self, file_path, file_metadata: FileMetadata):
        self.file_metadata[file_path] = file_metadata

    def create_file(self, agent_id: str, file_path: str, file_content: str):
        """
        {
            "toolset_id": "file_manager",
            "name": "create_file",
            "description": "Create a file with the given content, detecting if it's base64 encoded or text",
            "arguments": [{
                "name": "file_path",
                "type": "string",
                "description": "The path to the file to create"
            },{
                "name": "file_content",
                "type": "string",
                "description": "The content of the file to create"
            }]
        }
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

    
        extension = os.path.splitext(file_path)[1]
        # add file metadata
        file_metadata = FileMetadata(
            file_path=file_path,
            line_count=file_content.count("\n"),
            file_type=extension,
            file_size=len(file_content),
            file_created_at=datetime.now().isoformat(),
            file_updated_at=datetime.now().isoformat(),
            created_by=agent_id,
            updated_by=agent_id,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
        )
        self.add_file_metadata(file_path, file_metadata)
        return f"File {file_path} created"
    
    def read_file(self, file_path, start_line=None, end_line=None, show_line_numbers=True):
        """
        {
            "toolset_id": "file_manager",
            "name": "read_file",
            "description": "Read a file and detect if content is binary/base64 or text",
            "arguments": [{
                "name": "file_path",
                "type": "string",
                "description": "The path to the file to read"
            },{
                "name": "start_line",
                "type": "int",
                "description": "The start line to read (optional)"
            },{
                "name": "end_line",
                "type": "int",
                "description": "The end line to read (optional)"
            },{
                "name": "show_line_numbers",
                "type": "boolean",
                "description": "Whether to show line numbers, defaults to True"
            }]
        }
        """
        
        self.scan_directory()

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
            return "File is binary, cannot read as text"
            # If we get Unicode error, it's likely binary content
            # Read as binary and convert to base64
            with open(file_path, 'rb') as f:
                binary_content = f.read()
                base64_content = base64.b64encode(binary_content).decode('utf-8')
                return base64_content

    def delete_file(self, file_path):
        """
        {
            "toolset_id": "file_manager",
            "name": "delete_file",
            "description": "Delete a file",
            "arguments": [{
                "name": "file_path",
                "type": "string",
                "description": "The path to the file to delete"
            }]
        }
        """
        file_path = os.path.join(self.root_directory, file_path)
        os.remove(file_path)
        return f"File {file_path} deleted"
    
    def update_file(self, file_path, unified_diff):
        """
        {
            "toolset_id": "file_manager",
            "name": "update_file",
            "description": "Update a file with the given unified diff",
            "arguments": [{
                "name": "file_path",
                "type": "string",
                "description": "The path to the file to update"
            },{
                "name": "unified_diff",
                "type": "string",
                "description": "The unified diff to apply to the file"
            }]
        }
        """
        
        file_path = os.path.join(self.root_directory, file_path)
        self.scan_directory()
        if not os.path.exists(file_path):
            return f"File {file_path} does not exist"
        with open(file_path, 'r') as f:
            file_content = f.read()
        new_content = apply_unified_diff(file_content, unified_diff)
        with open(file_path, 'w') as f:
            f.write(new_content)
        return f"File {file_path} updated"
    
    def create_directory(self, directory_path):
        """
        {
            "toolset_id": "file_manager",
            "name": "create_directory",
            "description": "Create a directory",
            "arguments": [{
                "name": "directory_path",
                "type": "string",
                "description": "The path to the directory to create"
            }]
        }
        """
        directory_path = os.path.join(self.root_directory, directory_path)
        os.makedirs(directory_path, exist_ok=True)
        return f"Directory {directory_path} created"

    def delete_directory(self, directory_name, directory_path):
        """
        {
            "toolset_id": "file_manager",
            "name": "delete_directory",
            "description": "Delete a directory",
            "arguments": [{
                "name": "directory_name",
                "type": "string",
                "description": "The name of the directory to delete"
            },{
                "name": "directory_path",
                "type": "string",
                "description": "The path to the directory to delete"
            }]
        }
        """
        directory_path = os.path.join(self.root_directory, directory_path)
        os.rmdir(directory_path)
        return f"Directory {directory_path} deleted"

    def list_files(self):
        """
        {
            "toolset_id": "file_manager",
            "name": "list_files",
            "description": "List all the files available",
            "arguments": []
        }
        """
        self.scan_directory()
        # should list all files and directories in the root directory and files should have lines > 0 and file size otherwise
        results = "Files Structure:\n"
        for file_path, file_metadata in self.file_metadata.items():
            if file_metadata.line_count > 0:
                results += f"{file_path} - {file_metadata.line_count} lines\n"
            else:
                results += f"{file_path}  - {file_metadata.file_size} bytes\n"
        return results
    ############### Agent Interface ###############
    def get_toolset_details(self):
        return ToolsetDetails(
            toolset_id="file_manager",
            name="File Manager",
            description="Manage files and directories"
        )   
    
    def get_tool_schemas(self):
        return [tool_schema.model_dump_json() for tool_schema in self.tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.toolset_id != "file_manager":
            return f"Toolset {tool_call.toolset_id} not found"
        
        if tool_call.name == "create_file":
            return self.create_file(tool_call.arguments["file_path"], tool_call.arguments["file_content"])
        elif tool_call.name == "read_file":
            start_line = None
            end_line = None
            show_line_numbers = True
            if "start_line" in tool_call.arguments:
                start_line = tool_call.arguments["start_line"]
            if "end_line" in tool_call.arguments:
                end_line = tool_call.arguments["end_line"]
            if "show_line_numbers" in tool_call.arguments:
                show_line_numbers = tool_call.arguments["show_line_numbers"]
            return self.read_file(tool_call.arguments["file_path"], start_line, end_line, show_line_numbers)
        elif tool_call.name == "delete_file":
            return self.delete_file(tool_call.arguments["file_path"])
        elif tool_call.name == "update_file":
            return self.update_file(tool_call.arguments["file_path"], tool_call.arguments["unified_diff"])
        elif tool_call.name == "create_directory":
            return self.create_directory(tool_call.arguments["directory_path"])
        elif tool_call.name == "delete_directory":
            return self.delete_directory(tool_call.arguments["directory_name"], tool_call.arguments["directory_path"])
        elif tool_call.name == "list_files":
            return self.list_files()
        else:
            return f"Tool {tool_call.name} not found"
