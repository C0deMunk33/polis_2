from pydantic import BaseModel, Field
from typing import List
from libs.agent import Agent
from libs.common import ToolsetDetails, ToolCall, ToolSchema
import uuid
class UserMessage(BaseModel):
    message_id: str = Field(description="The ID of the message.")
    from_user_id: str = Field(description="The ID of the user sending the message.")
    message: str = Field(description="The message to send to the user.")


class User(BaseModel):
    id: str = Field(description="The ID of the user.")
    name: str = Field(description="The name of the user.")
    messages: List[UserMessage] = Field(description="The messages sent to the user.")
    new_messages: List[UserMessage] = Field(description="The new messages for the user.")

class UserDirectory:
    def __init__(self):
        self.users = {}
        self.new_message_buffer = {}

        names_of_tools_to_expose = [
            "get_users",
            "send_message",
            "get_new_message_count",
            "get_new_messages",
        ]

        self.tool_schemas = []
        for name in names_of_tools_to_expose:
            docstring = getattr(self, name).__doc__
            try:
                tool_schema = ToolSchema.model_validate_json(docstring)
                self.tool_schemas.append(tool_schema)
            except Exception as e:
                print(f"Error validating tool schema for {name}: {e}")
                print(f"Docstring: {docstring}")
                raise e

    def add_user(self, agent: Agent):
        if agent.id in self.users:
            return f"User {agent.id} already exists."
        
        self.users[agent.id] = User(id=agent.id, name=agent.name, messages=[], new_messages=[])
        return f"User {agent.id} added."
    
    def get_users(self):
        """
        {
            "toolset_id": "messages",
            "name": "get_users",
            "description": "Get a list of users.",
            "arguments": []
        }
        """
        results = "Users: "
        for user in self.users.values():
            results += f"    - {user.name} (user_id: {user.id})\n "
        return results

    def send_message(self, agent: Agent, user_id: str, message: str):
        """
        {
            "toolset_id": "messages",
            "name": "send_message",
            "description": "Send a message to a user.",
            "arguments": [
                {"name": "user_id", "type": "str", "description": "The ID of the user to message."},
                {"name": "message", "type": "str", "description": "The message to send to the user."}
            ]
        }
        """
        if user_id not in self.users:
            return f"User {user_id} does not exist."
        
        if user_id not in self.new_message_buffer:
            self.new_message_buffer[user_id] = []
        user_message = UserMessage(message_id=str(uuid.uuid4()), from_user_name=agent.name, from_user_id=agent.id, message=message) 
        self.new_message_buffer[user_id].append(user_message)
        self.users[user_id].messages.extend(user_message)
        return f"Message sent to {user_id}:\n    {message}"

    def get_new_message_count(self, agent: Agent):
        """
        {
            "toolset_id": "messages",
            "name": "get_new_message_count",
            "description": "Get the number of new messages",
            "arguments": []
        }
        """
        if agent.id not in self.new_message_buffer:
            return "No new messages."
        return f"There are {len(self.new_message_buffer[agent.id])} new messages."

    def _get_messages_string(self, messages: List[UserMessage]):
        results = "Messages:\n"
        for message in messages:
            results += f"    - {message.message}\n"
        return results

    def get_new_messages(self, agent: Agent):
        """
        {
            "toolset_id": "messages",
            "name": "get_new_messages",
            "description": "Get the new messages",
            "arguments": []
        }
        """
        if agent.id not in self.new_message_buffer:
            return "No new messages."
        messages = self.new_message_buffer[agent.id]
        self.new_message_buffer[agent.id] = []
        return self._get_messages_string(messages)

    def get_messages(self, agent: Agent, sender_id: str, limit: int = 10):
        """
        {
            "toolset_id": "messages",
            "name": "get_messages",
            "description": "Get a list of messages filtered by sender (optional).",
            "arguments": [
                {"name": "sender_id", "type": "str", "description": "The ID of the sender to filter messages by. (optional)"},
                {"name": "limit", "type": "int", "description": "The number of messages to return. (optional)"}
            ]
        }
        """
        messages = self.users[agent.id]["messages"]
        self.users[agent.id]["messages"] = []
        messages = messages[-limit:]
        if sender_id:
            messages = [message for message in messages if message.from_user_id == sender_id]
        return self._get_messages_string(messages)

    ############### Agent Interface ###############
    def get_toolset_details(self):
        return ToolsetDetails(
            toolset_id="messages",
            name="Messages",
            description="A toolset for sending and receiving messages between users."
        )
    
    def get_tool_schemas(self):
        return [ToolSchema.model_dump_json() for ToolSchema in self.tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.name == "send_message":
            return self.send_message(agent, tool_call.arguments["user_id"], tool_call.arguments["message"])
        elif tool_call.name == "get_messages":
            return self.get_messages(agent, tool_call.arguments["sender_id"], tool_call.arguments["limit"])
        elif tool_call.name == "get_new_messages":
            return self.get_new_messages(agent)
        elif tool_call.name == "get_new_message_count":
            return self.get_new_message_count(agent)
        elif tool_call.name == "get_users":
            return self.get_users()
        else:
            return "Invalid tool call."
