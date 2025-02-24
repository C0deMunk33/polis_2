try:
    from .common import call_ollama_chat, embed_with_ollama, convert_file, chunk_text, Message, ToolCall
    from .agent_database import AgentDatabase
except ImportError:
    from common import call_ollama_chat, embed_with_ollama, convert_file, chunk_text, Message, ToolCall
    from agent_database import AgentDatabase
from datetime import datetime
from typing import List, Optional, Callable
from pydantic import BaseModel, Field
import hashlib
import json
import traceback
import warnings
warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)
import sqlite3
import uuid

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

class AgentRunResult(BaseModel): # TODO: generate and save this for each pass
    pass_id: str = Field(description="The id of the pass.")
    agent_id: str = Field(description="The id of the agent that ran.")
    pass_number: int = Field(description="The pass number of the agent run.")
    model: str = Field(description="The model used for the agent run.")
    run_messages: List[Message] = Field(description="The messages passed to the agent")
    agent_output: AgentOutputSchema = Field(description="The output of the agent run.")
    tool_results: List[Message]
    summary_messages: List[Message] = Field(description="The messages from the summary pass.")
    summary_output: AgentSummarySchema = Field(description="The output of the summary pass.")
    
class Agent:
    def __init__(self, default_llm_url: str, database_path: str, name: str, private_key: str, initial_instructions: str, initial_notes: List[str], buffer_size: int = 20, running: bool = True, standing_tool_calls: List[ToolCall] = []):
        self.default_llm_url = default_llm_url
        self.model = "TODO"
        self.name = name
        self.private_key = private_key
        self.notes = initial_notes
        self.running = running
        self.buffer_size = buffer_size
        self.message_buffer = []
        self.standing_tool_calls = standing_tool_calls
        self.latest_summary_messages = []
        self.latest_post_system_messages = []
        self.database_path = database_path
        self.message_buffer.append(Message(role="user", content=initial_instructions))
        # agent id is deterministic hash of private key
        self.id = hashlib.sha256(private_key.encode()).hexdigest()
        self.pass_number = 0
        self.tools = []
        self.pass_summaries = []
        self.latest_pass_tool_call_results = []

    def add_message(self, message: Message):
        self.message_buffer.append(message)
        self.message_buffer = self.message_buffer[-self.buffer_size:]
        
    def get_system_prompt(self, standing_tool_results: str):
        return f"""You are an advanced synthetic being. You are in an internal monologue loop, you can only interact with the world through the available apps.
Context:
{standing_tool_results}
* Current local time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
* Only tools from loaded apps can be called.
* You can only call up to 5 tools in one pass.
* If a tool call fails, ensure you have the appropriate tools to fix the issue.

You must respond in the following JSON format:
{AgentOutputSchema.model_json_schema()}
"""

    def call_tools(self, tool_calls: List[ToolCall], tool_callback: Callable):
        
        self.latest_pass_tool_call_results = []

        if len(tool_calls) == 0:
            return

        print(f"Calling tools:")
        # add assistant tool call message
        self.add_message(Message(role="assistant", tool_calls=tool_calls))
        self.latest_pass_tool_call_results.append(Message(role="assistant", tool_calls=tool_calls))

        for tool_call in tool_calls:
            tool_results = tool_callback(self, tool_call)
            if tool_results is not None:
                if type(tool_results) == str:
                    self.add_message(Message(role="tool", content=tool_results))
                    self.latest_pass_tool_call_results.append(Message(role="tool", content=tool_results))
                elif type(tool_results) == dict:
                    self.add_message(Message(role="tool", content=json.dumps(tool_results)))
                    self.latest_pass_tool_call_results.append(Message(role="tool", content=json.dumps(tool_results)))
                elif type(tool_results) == int:
                    self.add_message(Message(role="tool", content=str(tool_results)))
                    self.latest_pass_tool_call_results.append(Message(role="tool", content=str(tool_results)))
                elif type(tool_results) == list:
                    result_string = ""
                    for result in tool_results:
                        if type(result) == BaseModel:
                            result_string += result.model_dump_json()
                        else:
                            result_string += str(result)
                    self.add_message(Message(role="tool", content=result_string))
                    self.latest_pass_tool_call_results.append(Message(role="tool", content=result_string))
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
        result_string = ""
        print("Standing tool calls:")
        messages = []
        # create assistant message
        messages.append(Message(role="assistant", tool_calls=self.standing_tool_calls))
        tool_results = []
        for tool_call in self.standing_tool_calls:
            tool_result = tool_callback(self, tool_call)            
            if tool_result is not None:
                tool_results.append(tool_result)
                messages.append(Message(role="tool", content=tool_result))
        result_string = "\n".join(tool_results) + "\n"
        return result_string, messages

    def get_pass_summary(self, llm_url: str, response: AgentOutputSchema, standing_tool_results: str):
        
        last_pass_summary = ""
        if len(self.pass_summaries) > 0:
            last_pass_summary = f"Last Pass Summary:"

            for summary in self.pass_summaries[-3:]:
                last_pass_summary += f"    {summary.summary}\n"

        summary_system_prompt = f"""your task is to list the actions taken, list any notes to save for later and summarize what happened in the most recent pass of the agent, then you need to write an instruction for the next pass of the agent.

Agent Context:
{standing_tool_results}

What follows is the tool calls and results from the latest pass of the agent.
"""
        summary_user_prompt = f"""Given the following recent agent pass output, and all available context, summarize the pass in the following JSON format:
{last_pass_summary}

Most Recent Pass Output:
    Thoughts:
        {response.thoughts + response.followup_thoughts}

* If a tool call failed, ensure the agent has the oppropriate tools to fix the issue. That they have loaded the appropriate apps.

You must respond in the following JSON format:
{AgentSummarySchema.model_json_schema()}
"""
        
        messages = [Message(role="system", content=summary_system_prompt)]
        messages.extend(self.latest_post_system_messages)
        messages.extend(self.message_buffer[-20:])
        messages.append(Message(role="user", content=summary_user_prompt))


        try:    
            self.latest_summary_messages = messages
            summary_response = call_ollama_chat(llm_url, "llama3.1:8b", messages, AgentSummarySchema.model_json_schema())
            return AgentSummarySchema.model_validate_json(summary_response)
        except Exception as e:
            print("######################### Summary Messages #########################")
            for message in messages:
                if message.tool_calls is not None:
                    print(f"{message.role}: {message.tool_calls}")
                else:   
                    print(f"{message.role}: {message.content}")
            print("######################### Summary Messages #########################")
            print(f"Error validating summary response: {e}")
            print(f"Summary response: {summary_response}")
            print(f"Stack trace: {traceback.format_exc()}")
            raise e

    def run(self, llm_url: str, model: str, post_system_messages: List[Message], tool_callback: Callable):
        if not self.running:
            print(f"Agent {self.name} is not running")
            return
        
        # perform standing tool calls
        standing_tool_results, standing_tool_messages = self.call_standing_tool_calls(tool_callback)

        system_prompt = self.get_system_prompt(standing_tool_results)

        messages = [Message(role="system", content=system_prompt)]
        self.latest_post_system_messages = post_system_messages
        messages.extend(post_system_messages)
        messages.extend(self.message_buffer[-20:])
        # messages.extend(standing_tool_messages)
        
        if len(self.pass_summaries) > 0:
            prev_summary = self.pass_summaries[-1]
            prev_summary_string = "Summary of the last pass: " + prev_summary.summary + "\n\n" + "Instructions: " + prev_summary.instructions_for_next_pass
            messages.append(Message(role="user", content=prev_summary_string))
        
        """
        print("######################### Message Buffer #########################")
        for message in final_message_buffer:
            if message.tool_calls is not None:
                print(f"{message.role}: {message.tool_calls}")
            else:
                print(f"{message.role}: {message.content}")
        print("######################### Message Buffer #########################")
        """

        response = call_ollama_chat(llm_url, model, messages, AgentOutputSchema.model_json_schema())
        try:
            response = AgentOutputSchema.model_validate_json(response)
        except Exception as e:
            print(f"Error validating response: {e}")
            print(f"Response: {response}")
            print(f"Stack trace: {traceback.format_exc()}")
            raise e
        print()
        print(f"Thoughts:")
        print("    - " + response.thoughts)
        print("    - " + response.followup_thoughts)

        if not response.should_continue:    
            self.running = False

        self.call_tools(response.tool_calls, tool_callback)
        
        print("\n\nFull System Prompt:")
        print(system_prompt)
        summary = self.get_pass_summary(llm_url, response, standing_tool_results)
        print("\n\nFull Summary:")
        print(summary.model_dump_json(indent=4))

        self.pass_number += 1
        self.pass_summaries.append(summary)
        self.notes.extend(summary.notes)

        agent_run_result = AgentRunResult(
            pass_id=str(uuid.uuid4()),
            agent_id=self.id,
            pass_number=self.pass_number,
            model=model,
            run_messages=messages,
            agent_output=response,
            tool_results=self.latest_pass_tool_call_results,
            summary_messages=self.latest_summary_messages,
            summary_output=summary
        )

        # save the agent run result to database
        date_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        agent_database = AgentDatabase(self.database_path)
        agent_database.save_agent(self.id, self.name, self.pass_number, date_string)
        agent_database.save_agent_run_result(self.id, agent_run_result.pass_id, agent_run_result.pass_number, agent_run_result.model_dump_json(), date_string)


        
        
        