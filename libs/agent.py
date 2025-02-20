try:
    from .common import call_ollama_chat, embed_with_ollama, convert_file, chunk_text, Message, ToolCall
except ImportError:
    from common import call_ollama_chat, embed_with_ollama, convert_file, chunk_text, Message, ToolCall
from datetime import datetime
from typing import List, Optional, Callable
from pydantic import BaseModel, Field
import hashlib
import json

import warnings
warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)


class AgentOutputSchema(BaseModel):
    thoughts: List[str] = Field(description="string array of thoughts. These thoughts are not visible to others. This is your chain of thought process.")
    notes: List[str] = Field(description="string array of notes. These notes are not visible to others. and are persistent across runs.")
    tool_calls: List[ToolCall] = Field(description="The tools to call. dict contains name and arguments. The results of these calls will be available to you in the next pass, if should_continue is True. You can call multiple tools in one pass.")
    instructions_for_next_pass: str = Field(description="This is the prompt you will receive in the next pass as a user message.")
    actions_taken: List[str] = Field(description="A list of actions taken, including what was thought and what was done.")
    clear_message_buffer: bool = Field(description="Whether your message buffer should be cleared, your instructions will be passed into the next pass, and your notes will be preserved. Do this when changing topic.")
    delete_notes: List[int] = Field(description="A list of notes to delete. The notes will be deleted from the persistent notes, as seen in your system prompt.")
    clear_all_notes: bool = Field(description="Whether all notes should be deleted, your instructions will be passed into the next pass, and your message buffer will be preserved.")
    clear_all_actions: bool = Field(description="Whether your recent action list should be cleared.")
    should_continue: bool = Field(description="Whether you should continue running, if False, you will stop running.")

class Agent:
    def __init__(self, default_llm_url: str, name: str, private_key: str, persona: str, initial_instructions: str, initial_notes: List[str], buffer_size: int = 20, running: bool = True, standing_tool_calls: List[ToolCall] = []):
        self.default_llm_url = default_llm_url
        self.name = name
        self.private_key = private_key
        self.persona = persona
        self.notes = initial_notes
        self.running = running
        self.buffer_size = buffer_size
        self.message_buffer = []
        self.standing_tool_calls = standing_tool_calls
        self.message_buffer.append(Message(role="user", content=initial_instructions))
        # agent id is deterministic hash of private key
        self.id = hashlib.sha256(private_key.encode()).hexdigest()

        self.tools = []
        self.recent_actions = []
        
    def add_message(self, message: Message):
        self.message_buffer.append(message)
        self.message_buffer = self.message_buffer[-self.buffer_size:]
        
    def get_system_prompt(self, tool_schemas: List[dict], standing_tool_results: str):
        # TODO add goals and requirements
        note_string = ""

        tool_schemas_json = json.dumps(tool_schemas)

        if len(self.notes) > 0:
            note_string = f"Persistent notes: { "\n".join([f"{i}: {note}" for i, note in enumerate(self.notes)]) }"

        return f"""You are an advanced synthetic being. You are in an internal monologue loop, you can only interact with the world through tool calls.

Your name is {self.name}.
Persona: {self.persona}.
{note_string}

You have access to the following tools:
{tool_schemas_json}

Current context:
{standing_tool_results}

Current local time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Recent actions:
{ "\n".join([f"{i}: {action}" for i, action in enumerate(self.recent_actions)]) }

Please respond in the following JSON format:
{AgentOutputSchema.model_json_schema()}
"""

    def call_tools(self, tool_calls: List[ToolCall], tool_callback: Callable):
        for tool_call in tool_calls:
            tool_results = tool_callback(self, tool_call)
            if tool_results is not None:
                
                if type(tool_results) == str:
                    self.add_message(Message(role="tool", content=tool_results))
                elif type(tool_results) == dict:
                    self.add_message(Message(role="tool", content=json.dumps(tool_results)))
                elif type(tool_results) == int:
                    self.add_message(Message(role="tool", content=str(tool_results)))
                elif type(tool_results) == list:
                    result_string = ""
                    for result in tool_results:
                        if type(result) == BaseModel:
                            result_string += result.model_dump_json()
                        else:
                            result_string += str(result)
                    self.add_message(Message(role="tool", content=result_string))
                else:
                    print("~"*100)
                    print("~"*100)
                    print("########################UNKNOWN TOOL RESULT########################")
                    print(type(tool_results))
                    print("Tool call:")
                    print(f"Tool call: {tool_call}")
                    print("~"*100)
                    print(f"Tool results: {tool_results}")
                    print("~"*100)
                    print("~"*100)
                    print("~"*100)

    def call_standing_tool_calls(self, tool_callback: Callable):
        # calls standing tools and concatenates results as a single string
        result = ""
        print("Standing tool calls:")
        for tool_call in self.standing_tool_calls:
            tool_result = tool_callback(self, tool_call)            
            if tool_result is not None:
                result += tool_result
        return result

    def run(self, server_url: str, model: str, tool_schemas: List[dict], tool_callback: Callable):
        if not self.running:
            print(f"Agent {self.name} is not running")
            return
        
        # perform standing tool calls
        standing_tool_results = self.call_standing_tool_calls(tool_callback)

        system_prompt = self.get_system_prompt(tool_schemas, standing_tool_results)

        final_message_buffer = [Message(role="system", content=system_prompt)] + self.message_buffer

        response = call_ollama_chat(server_url, model, final_message_buffer, AgentOutputSchema.model_json_schema())
        response = AgentOutputSchema.model_validate_json(response)
        print()
        print(f"{self.name}:")
        print(f"Thoughts:")
        for thought in response.thoughts:
            print(f"  - {thought}")
        print(f"Actions taken:")
        for action in response.actions_taken:
            print(f"  - {action}")
        print(f"Calling tools:")

        self.recent_actions.extend(response.actions_taken)
        # limit recent actions to 30
        self.recent_actions = self.recent_actions[-30:]

        if response.clear_message_buffer:
            self.message_buffer = []

        if response.clear_all_actions:
            self.recent_actions = []

        if response.clear_all_notes:
            self.notes = []
        elif response.delete_notes:
            self.notes = [self.notes[i] for i in range(len(self.notes)) if i not in response.delete_notes]
        self.add_message(Message(role="assistant", content= "Actions taken in previous pass: " +"\n".join(response.actions_taken)))
        
        if response.should_continue:    
            self.notes.extend(response.notes)
        else:
            self.running = False

        self.call_tools(response.tool_calls, tool_callback)
        
        self.add_message(Message(role="user", content= "Instructions from you on your last pass: " + response.instructions_for_next_pass))
