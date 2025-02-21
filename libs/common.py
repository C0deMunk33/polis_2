from ollama import Client
import random
from pydantic import BaseModel
from markitdown import MarkItDown
import semchunk
from typing import List
import difflib
import base64
import re

def call_ollama_chat(server_url, model, messages, json_schema=None, temperature=None, tools=None):
    try:
        client = Client(
            host=server_url
        )
        
        response = client.chat(
            #model='huggingface.co/unsloth/DeepSeek-R1-Distill-Qwen-14B-GGUF:Q8_0', 
            #model='MFDoom/deepseek-r1-tool-calling:14b',
            model='huggingface.co/bartowski/Qwen2.5-14B-Instruct-1M-GGUF',
            stream=False,
            messages=messages,
            format=json_schema,
            tools=tools,
            options={
                'num_ctx':100000,
                'seed': random.randint(0, 1000000)
            })

        return response.message.content

    except Exception as error:
        print("~~~~~~~~~~~~~~~~~~~~~~~")
        print("Error")
        print(error)
        print("~~~~~~~~~~~~~~~~~~~~~~~")
        return "error"
    
def embed_with_ollama(server_url, text, model="nomic-embed-text"):
    client = Client(
        host=server_url
    )

    results = client.embed(
        model=model,
        input=text
    )

    return results["embeddings"][0]

def convert_file(file_path):
    md = MarkItDown()
    result = md.convert(file_path)
    return result.text_content

def chunk_text(text, chunk_size, overlap=0):
    chunker = semchunk.chunkerify(lambda text: len(text.split()), chunk_size)
    res = chunker(text, overlap)
    return res

def apply_unified_diff(file_content, diff):
    return difflib.unified_diff(file_content.splitlines(), diff.splitlines())

class ToolCall(BaseModel):
    toolset_id: str
    name: str
    arguments: dict

class ToolSchema(BaseModel):
    toolset_id: str
    name: str
    description: str
    arguments: List[dict]

class ToolsetDetails(BaseModel):
    toolset_id: str
    name: str
    description: str

class Message(BaseModel):
    role: str
    content: str
    
    def chat_ml(self):
        return {
            "role": self.role,
            "content": self.content
        }
    
class MultiWriter:
    def __init__(self, *files):
        self.files = files

    def write(self, text):
        for file in self.files:
            file.write(text)
            file.flush()  # Ensure writing happens immediately

    def flush(self):
        for file in self.files:
            file.flush()

def is_base64(string):
    """
    Check if a string is base64 encoded by looking at:
    1. Character set (only valid base64 chars)
    2. Length (must be multiple of 4)
    3. Padding (proper = padding at end)
    4. Successful decode attempt
    """
    # Base64 pattern: letters, numbers, +, /, and = for padding
    base64_pattern = r'^[A-Za-z0-9+/]*={0,2}$'
    
    try:
        # Check if string matches base64 pattern
        if not re.match(base64_pattern, string):
            return False
            
        # Check if length is multiple of 4 (base64 requirement)
        if len(string) % 4 != 0:
            return False
            
        # Try to decode - if successful, likely base64
        base64.b64decode(string)
        return True
        
    except Exception:
        return False




