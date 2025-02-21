try:
    from .common import call_ollama_chat, embed_with_ollama, convert_file, chunk_text, Message, ToolCall
except ImportError:
    from common import call_ollama_chat, embed_with_ollama, convert_file, chunk_text, Message, ToolCall
    
from datetime import datetime
from typing import List, Optional, Callable
from pydantic import BaseModel, Field
import hashlib
import json
import traceback
import warnings
warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)

   

class AgentOutputSchema(BaseModel):
    thoughts: str = Field(description="your thoughts. This is part of your chain of thought process.")
    followup_thoughts: str = Field(description="your followup thoughts. This is part of your chain of thought process.")
    tool_calls: List[ToolCall] = Field(description="The tools to call. dict contains name and arguments. You can call up to 5 tools in one pass.")
    should_continue: bool = Field(description="Whether you should continue running, if False, you will stop running.")

class AgentSummarySchema(BaseModel):
    thoughts: str = Field(description="string of thoughts. These thoughts are not visible to others. This is your chain of thought process.")
    actions_taken: List[str] = Field(description="A list of actions taken in the given pass.")
    notes: List[str] = Field(description="string array of notes. These notes are not visible to others. and are persistent across runs.")
    summary: str = Field(description="string of summary. This is a summary of the actions taken, including what was thought and what was done.")
    instructions_for_next_pass: str = Field(description="This is the prompt you will receive in the next pass as a user message.")

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
        self.pass_summaries = []
        self.latest_pass_tool_call_results = []

    def add_message(self, message: Message):
        self.message_buffer.append(message)
        self.message_buffer = self.message_buffer[-self.buffer_size:]
        
    def get_system_prompt(self, standing_tool_results: str):
        return f"""You are an advanced synthetic being. You are in an internal monologue loop, you can only interact with the world through the available apps.

{standing_tool_results}

Current local time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Please respond in the following JSON format:
{AgentOutputSchema.model_json_schema()}
"""

    def call_tools(self, tool_calls: List[ToolCall], tool_callback: Callable):
        
        self.latest_pass_tool_call_results = []
        for tool_call in tool_calls:
            tool_results = tool_callback(self, tool_call)
            if tool_results is not None:
                if type(tool_results) == str:
                    self.add_message(Message(role="tool", content=tool_results))
                    self.latest_pass_tool_call_results.append(tool_results)
                elif type(tool_results) == dict:
                    self.add_message(Message(role="tool", content=json.dumps(tool_results)))
                    self.latest_pass_tool_call_results.append(json.dumps(tool_results))
                elif type(tool_results) == int:
                    self.add_message(Message(role="tool", content=str(tool_results)))
                    self.latest_pass_tool_call_results.append(str(tool_results))
                elif type(tool_results) == list:
                    result_string = ""
                    for result in tool_results:
                        if type(result) == BaseModel:
                            result_string += result.model_dump_json()
                        else:
                            result_string += str(result)
                    self.add_message(Message(role="tool", content=result_string))
                    self.latest_pass_tool_call_results.append(result_string)
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
        tool_results = []
        for tool_call in self.standing_tool_calls:
            tool_result = tool_callback(self, tool_call)            
            if tool_result is not None:
                tool_results.append(tool_result)
        return "\n".join(tool_results)

    def get_pass_summary(self, llm_url: str, response: AgentOutputSchema):
        summary_system_prompt = f"""your task is to list the actions taken, list any notes to save for later and summarize what happened in the most recent pass of the agent, then you need to write an instruction for the next pass of the agent."""
        summary_user_prompt = f"""Given the following recent agent pass output, summarize the pass in the following JSON format:

Recent Summary:
{ "\n".join([f"{i}: {summary.summary}" for i, summary in enumerate(self.pass_summaries[-10:])]) }

Most Recent Pass Output:
    Thoughts:
        {response.thoughts}

        {response.followup_thoughts}

    Tools Called:
        {"\n".join([f"{i}: {tool_call.name} with arguments: {tool_call.arguments}" for i, tool_call in enumerate(response.tool_calls)])}

Please summarize the pass in the following JSON format:
{AgentSummarySchema.model_json_schema()}
"""
        
        messages = [Message(role="system", content=summary_system_prompt)]
        
        for tool_result in self.latest_pass_tool_call_results:
            messages.append(Message(role="tool", content=tool_result))

        messages.append(Message(role="user", content=summary_user_prompt))

        summary_response = call_ollama_chat(llm_url, "llama3.1:8b", messages, AgentSummarySchema.model_json_schema())
        return AgentSummarySchema.model_validate_json(summary_response)
    
    def run(self, llm_url: str, model: str, tool_callback: Callable):
        if not self.running:
            print(f"Agent {self.name} is not running")
            return
        
        # perform standing tool calls
        standing_tool_results = self.call_standing_tool_calls(tool_callback)

        system_prompt = self.get_system_prompt(standing_tool_results)

        print()
        print("System prompt:")
        print(system_prompt)
        print()
        final_message_buffer = [Message(role="system", content=system_prompt)] + self.message_buffer

        response = call_ollama_chat(llm_url, model, final_message_buffer, AgentOutputSchema.model_json_schema())
        try:
            response = AgentOutputSchema.model_validate_json(response)
        except Exception as e:
            print(f"Error validating response: {e}")
            print(f"Response: {response}")
            print(f"Stack trace: {traceback.format_exc()}")
            raise e
        print()
        print(f"Thoughts:")
        print(response.thoughts)
        print(f"Followup thoughts:")
        print(response.followup_thoughts)
        print(f"Calling tools:")

        if not response.should_continue:    
            self.running = False

        self.call_tools(response.tool_calls, tool_callback)
        
        summary = self.get_pass_summary(llm_url, response)
        
        self.pass_summaries.append(summary)
        self.notes.extend(summary.notes)

        summary_string = "Summary of the last pass: " + summary.summary + "\n\n" + "Instructions: " + summary.instructions_for_next_pass

        self.add_message(Message(role="user", content= summary_string))
