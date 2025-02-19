import os
import sys
from io import StringIO
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import ast
import builtins
import importlib
import shutil
import hashlib
import matplotlib
from pydantic import BaseModel
from get_directory_structure import get_directory_structure
from datetime import datetime
from typing import Optional
try:
    from .common import ToolSchema, ToolCall
    from .agent import Agent
except ImportError:
    from common import ToolSchema, ToolCall
    from agent import Agent

class CodeFile(BaseModel):
    filename: str
    code: str
    code_intent: str

class CodeExecutionResult(BaseModel):
    success: bool
    code_hash: str
    code: str
    timestamp: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    code_intent: str

class SafeCodeExecutor:
    def __init__(self, allowed_directory, allowed_modules=None, debug=False):
        """
        Initialize the executor with a specific directory where file operations are allowed
        and a list of whitelisted modules.
        """
        # Convert to absolute path and ensure it exists with proper permissions
        self.allowed_directory = os.path.abspath(allowed_directory)
        self.backroom_directory = os.path.join(self.allowed_directory, ".backroom")
        self.debug = debug

        # return error if allowed_directory is not a directory
        if not os.path.isdir(self.allowed_directory):
            raise ValueError(f"Allowed directory {self.allowed_directory} is not a directory")

        # make backroom directory if it doesn't exist
        if not os.path.exists(os.path.join(self.allowed_directory, self.backroom_directory)):
            os.makedirs(os.path.join(self.allowed_directory, self.backroom_directory), mode=0o755)        
        
        # Default allowed modules for data analysis
        self.allowed_modules = allowed_modules or [
            'numpy',
            'pandas',
            'matplotlib',
            'seaborn',
            'scipy',
            'sklearn',
            'statsmodels'
        ]
        
        # Pre-import allowed modules to verify they're available
        self.imported_modules = {}
        for module_name in self.allowed_modules:
            try:
                self.imported_modules[module_name] = importlib.import_module(module_name)
                
            except ImportError as e:
                if self.debug:
                    print(f"Warning: Module {module_name} not available: {str(e)}")
        
        # Create a restricted version of open() that only works in the allowed directory
        def restricted_open(file, mode='r', *args, **kwargs):
            file_path = os.path.abspath(os.path.join(self.allowed_directory, file))
            if not file_path.startswith(self.allowed_directory):
                raise PermissionError(f"Access denied. Can only create/modify files in {self.allowed_directory}")
            return builtins.open(file_path, mode, *args, **kwargs)
        
        # Dictionary of allowed built-ins, should include make directory and make file, but only within the allowed directory
        self.safe_globals = {
            '__builtins__': {
                'os.makedirs': os.makedirs,
                'os.path': os.path,
                'os.path.join': os.path.join,
                'os.path.abspath': os.path.abspath,
                'os.path.exists': os.path.exists,
                'os.path.isfile': os.path.isfile,
                'print': print,
                'len': len,
                'range': range,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict,
                'set': set,
                'tuple': tuple,
                'min': min,
                'max': max,
                'sum': sum,
                'abs': abs,
                'round': round,
                'open': restricted_open,
                'TypeError': TypeError,
                'ValueError': ValueError,
                'ZeroDivisionError': ZeroDivisionError,
                'Exception': Exception,
                '__import__': lambda name, *args: self.safe_import(name),
            },
            '__name__': '__main__',
        }
        
        # Add imported modules to safe globals
        self.safe_globals.update(self.imported_modules)

        self.pinned_files = []

        names_of_tools_to_expose = [
            "execute",
            "clear_files",
            "get_environment",
            "pin_file",
            "unpin_file",
            "delete_file",
            "save_code_to_environment",
            "get_file",
            "get_pinned_files",
            "replace_file",
            "edit_file_with_diff"
        ]

        self.tool_schemas = []
        for name in names_of_tools_to_expose:
            docstring = getattr(self, name).__doc__
            tool_schema = ToolSchema.model_validate_json(docstring)
            self.tool_schemas.append(tool_schema)
        

    def safe_import(self, name):
        """
        Safely import a module if it's in the whitelist.
        """
        base_module = name.split('.')[0]
        if base_module not in self.allowed_modules and name not in self.allowed_modules:
            raise ImportError(f"Module '{name}' is not in the whitelist. Allowed modules: {', '.join(self.allowed_modules)}")
        
        try:
            if name in self.imported_modules:
                return self.imported_modules[name]
            
            # Special handling for matplotlib.pyplot
            if name == 'matplotlib.pyplot':
                import matplotlib.pyplot
                self.imported_modules[name] = matplotlib.pyplot
                return matplotlib.pyplot
            
            # For other modules
            module = importlib.import_module(name)
            self.imported_modules[name] = module
            return module
        except ImportError as e:
            raise ImportError(f"Failed to import '{name}': {str(e)}")

    def is_code_safe(self, code_string):
        """
        Check if the provided code contains potentially dangerous operations.
        """
        try:
            tree = ast.parse(code_string)
            
            for node in ast.walk(tree):
                # Check imports against whitelist
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name not in self.allowed_modules:
                            if self.debug:
                                print(f"Unauthorized import detected: {alias.name}")
                            return False
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module if node.module else ''
                    if module_name not in self.allowed_modules:
                        if self.debug:
                            print(f"Unauthorized from-import detected: {module_name}")
                            return False
                
                # Prevent direct attribute access
                if isinstance(node, ast.Attribute):
                    if node.attr.startswith('__'):
                        return False
                
                # Prevent exec/eval calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['exec', 'eval', 'compile']:
                            return False
            
            return True
        except SyntaxError:
            return False

    @contextmanager
    def capture_output(self):
        """Capture stdout and stderr"""
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            yield stdout, stderr

    def execute(self, code_string, code_intent):
        """
        {
            "toolset_id": "code_runner",
            "name": "execute",
            "description": "Execute the python code provided in a safe environment.",
            "arguments": [{
                "name": "code",
                "type": "string",
                "description": "The python code to execute"
            },{
                "name": "code_intent",
                "type": "string",
                "description": "The intent of the code to execute"
            }]
        }
        """
        error_msg = None
        if not self.is_code_safe(code_string):
            error_msg = "Code contains potentially unsafe operations or unauthorized imports"
            if self.debug:
                print(f"Available modules: {self.allowed_modules}")
                print(f"Attempting to execute:\n{code_string}")
               
        # sha256 hash of code
        code_hash = hashlib.sha256(code_string.encode()).hexdigest()

        try:
            with self.capture_output() as (stdout, stderr):
                # Compile and execute the code
                code = compile(code_string, '<string>', 'exec')
                exec(code, self.safe_globals, {})

                code_execution_result = CodeExecutionResult(success=True, 
                                                            code_hash=code_hash,
                                                            code=code_string,
                                                            timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
                                                            stdout=stdout.getvalue(),
                                                            stderr=stderr.getvalue(),
                                                            code_intent=code_intent)
                
                
                # save CodeExecutionResult to backroom directory
                with open(f'{self.backroom_directory}/code_execution_result_{code_hash}.json', 'w') as f:
                    f.write(code_execution_result.model_dump_json())

            
            if self.debug:
                print(code_execution_result.model_dump_json(indent=4))

            return code_execution_result
        
        except Exception as e:
            if self.debug:
                print(f"Error: {e}")
            error_msg = f"{str(e)}"

        return CodeExecutionResult(success=False, 
                                    stdout="", 
                                    stderr=error_msg, 
                                    code_hash=code_hash,
                                    code=code_string,
                                    timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
                                    code_intent=code_intent)

    def clear_files(self):
        """{
            "toolset_id": "code_runner",
            "name": "clear_files",
            "description": "Clear all files in the current environment.",
            "arguments": []
        }"""
        if os.path.exists(self.allowed_directory):
            for filename in os.listdir(self.allowed_directory):
                file_path = os.path.join(self.allowed_directory, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        return "Files cleared"
                except Exception as e:
                    return f"Error clearing files: {e}"

    def get_environment(self):
        """
        {
            "toolset_id": "code_runner",
            "name": "get_environment",
            "description": "Gets files directory structure of the current environment.",
            "arguments": []
        }
        """
        return get_directory_structure(self.allowed_directory)

    def pin_file(self, filename):
        """
        {
            "toolset_id": "code_runner",
            "name": "pin_file",
            "description": "Pins a file to the current environment.",
            "arguments": [{
                "name": "filename",
                "type": "string",
                "description": "The filename of the file to pin"
            }]
        }
        """
        # check that the file exists in the allowed directory
        if not os.path.exists(os.path.join(self.allowed_directory, filename)):
            return False, "File does not exist"
        self.pinned_files.append(filename)
        return f"File {filename} pinned"
    
    def unpin_file(self, filename):
        """
        {
            "toolset_id": "code_runner",
            "name": "unpin_file",
            "description": "Unpins a file from the current environment.",
            "arguments": [{
                "name": "filename",
                "type": "string",
                "description": "The filename of the file to unpin"
            }]
        }
        """
        if filename not in self.pinned_files:
            return False, "File is not pinned"
        self.pinned_files.remove(filename)
        return f"File {filename} unpinned"

    def delete_file(self, filename):
        """
        {
            "toolset_id": "code_runner",
            "name": "delete_file",
            "description": "Deletes a file from the current environment.",
            "arguments": [{
                "filename": {
                    "type": "string",
                    "description": "The filename of the file to delete"
                }
            }]
        }
        """
        if filename in self.pinned_files:
            self.unpin_file(filename)
        if os.path.exists(os.path.join(self.allowed_directory, filename)):
            os.unlink(os.path.join(self.allowed_directory, filename))
            return True, f"File {filename} deleted"
        
        # check if the file is in the backroom directory
        if os.path.exists(os.path.join(self.backroom_directory, filename)):
            # timestamp the filename to save as a backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy(os.path.join(self.backroom_directory, filename), os.path.join(self.backroom_directory, f"{filename}_{timestamp}"))
            os.unlink(os.path.join(self.backroom_directory, filename))
            return True, f"File {filename} deleted"

        return False, f"File {filename} does not exist"

    def save_code_to_environment(self, filename, code_string, code_intent):
        """
        {
            "toolset_id": "code_runner",
            "name": "save_code_to_environment",
            "description": "Saves the code to the environment.",
            "arguments": [{
                "name": "filename",
                "type": "string",
                "description": "The filename of the file to save the code to"
            },{
                "name": "code_string",
                "type": "string",
                "description": "The code to save to the file"
            },{
                "name": "code_intent",
                "type": "string",
                "description": "The intent of the code"
            }]
        }
        """
        with open(os.path.join(self.allowed_directory, filename), 'w') as f:
            f.write(code_string)

        code_file = CodeFile(filename=filename, code=code_string, code_intent=code_intent)
        with open(f'{self.backroom_directory}/{filename}.json', 'w') as f:
            f.write(code_file.model_dump_json())  

        return f"Code saved to {filename}"

    def cleanup(self):
        if os.path.exists(self.allowed_directory):
            try:
                shutil.rmtree(self.allowed_directory)
            except Exception as e:
                print(f"Error removing directory {self.allowed_directory}: {e}")

    def get_file(self, filename :str, show_line_numbers :bool = False):
        """
        {
            "toolset_id": "code_runner",
            "name": "get_file",
            "description": "Gets the text of a file in the current environment.",
            "arguments": [{
                "name": "filename",
                "type": "string",
                "description": "The filename of the file to get"
            }]
        }
        """
        output = ""
        with open(os.path.join(self.allowed_directory, filename), 'r') as f:
            if show_line_numbers:
                for line_number, line in enumerate(f, 1):
                    output += f"{line_number}: {line}"
            else:
                output = f.read()
        return output

    def get_pinned_files(self):
        """
        {
            "toolset_id": "code_runner",
            "name": "get_pinned_files",
            "description": "Gets text of pinned files in the current environment.",
            "arguments": []
        }
        """
        return "\n".join([f"### {filename}:\n{self.get_file(filename, show_line_numbers=True)}" for filename in self.pinned_files])

    def replace_file(self, filename, code_string, code_intent):
        """
        {
            "toolset_id": "code_runner",
            "name": "replace_file",
            "description": "Replaces a file in the current environment with new code.",
            "arguments": [{
                "name": "filename",
                "type": "string",
                "description": "The filename of the file to replace"
            },{
                "name": "code_string",
                "type": "string",
                "description": "The new code to replace the file with"
            },{
                "name": "code_intent",
                "type": "string",
                "description": "The intent of the new code"
            }]
        }
        """
        self.delete_file(filename)
        self.save_code_to_environment(filename, code_string, code_intent)
        return f"File {filename} replaced"
    
    def edit_file_with_diff(self, filename, diff):
        """
        {
            "toolset_id": "code_runner",
            "name": "edit_file_with_diff",
            "description": "Edits a file in the current environment with a diff.",
            "arguments": [{
                "name": "filename",
                "type": "string",
                "description": "The filename of the file to edit"
            },{
                "name": "diff",
                "type": "string",
                "description": "The diff to apply to the file, unified format"
            }]
        }
        """
        # read the file
        with open(os.path.join(self.allowed_directory, filename), 'r') as f:
            file_content = f.read()

        # apply the diff
        file_content = file_content.apply_patch(diff)

        # save the file
        with open(os.path.join(self.allowed_directory, filename), 'w') as f:
            f.write(file_content)

        return f"File {filename} edited with diff"

    ############ AGENT INTERFACE ############
    def get_tool_schemas(self):
        return [tool_schema.model_dump_json() for tool_schema in self.tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.toolset_id != "code_runner":
            return "Toolset not found"
        
        if tool_call.name == "execute":
            return self.execute(tool_call.arguments["code"], tool_call.arguments["code_intent"]).model_dump_json()
        
        if tool_call.name == "clear_files":
            return self.clear_files()
        
        if tool_call.name == "get_environment":
            return self.get_environment()
        
        if tool_call.name == "pin_file":
            return self.pin_file(tool_call.arguments["filename"])
        
        if tool_call.name == "unpin_file":
            return self.unpin_file(tool_call.arguments["filename"])
        
        if tool_call.name == "delete_file":
            return self.delete_file(tool_call.arguments["filename"])
        
        if tool_call.name == "save_code_to_environment":
            return self.save_code_to_environment(tool_call.arguments["filename"], tool_call.arguments["code_string"], tool_call.arguments["code_intent"])
        
        if tool_call.name == "get_file":
            return self.get_file(tool_call.arguments["filename"])
        
        if tool_call.name == "get_pinned_files":
            return self.get_pinned_files()
        
        if tool_call.name == "replace_file":
            return self.replace_file(tool_call.arguments["filename"], tool_call.arguments["code_string"], tool_call.arguments["code_intent"])
        
        if tool_call.name == "edit_file_with_diff":
            return self.edit_file_with_diff(tool_call.arguments["filename"], tool_call.arguments["diff"])
        
        return "Tool not found"
        
        
