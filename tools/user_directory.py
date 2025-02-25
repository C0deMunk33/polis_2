from pydantic import BaseModel, Field
from typing import List, Optional
from libs.agent import Agent
from libs.common import ToolsetDetails, ToolCall, ToolSchema
import uuid
import sqlite3
import json

class UserMessage(BaseModel):
    message_id: str = Field(description="The ID of the message.")
    from_user_id: str = Field(description="The ID of the user sending the message.")
    from_user_name: str = Field(description="The name of the user sending the message.")
    message: str = Field(description="The message to send to the user.")


class User(BaseModel):
    id: str = Field(description="The ID of the user.")
    name: str = Field(description="The name of the user.")
    messages: List[UserMessage] = Field(default_factory=list, description="The messages sent to the user.")
    new_messages: List[UserMessage] = Field(default_factory=list, description="The new messages for the user.")

class UserDirectory:
    def __init__(self, db_path: str = "user_directory.db"):
        self.db_path = db_path
        self._init_db()

        names_of_tools_to_expose = [
            "get_users",
            "send_message",
            "get_new_message_count",
            "get_new_messages",
            "get_messages"
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

    def _init_db(self):
        """Initialize the SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
        ''')
        
        # Create messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            from_user_id TEXT NOT NULL,
            from_user_name TEXT NOT NULL,
            to_user_id TEXT NOT NULL,
            message TEXT NOT NULL,
            is_new INTEGER DEFAULT 1,
            FOREIGN KEY (from_user_id) REFERENCES users(id),
            FOREIGN KEY (to_user_id) REFERENCES users(id)
        )
        ''')
        
        conn.commit()
        conn.close()

    def add_user(self, agent: Agent):
        """Add a user to the directory"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE id = ?", (agent.id,))
        if cursor.fetchone():
            conn.close()
            return f"User {agent.id} already exists."
        
        # Add user
        cursor.execute("INSERT INTO users (id, name) VALUES (?, ?)", 
                      (agent.id, agent.name))
        conn.commit()
        conn.close()
        
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name FROM users")
        users = cursor.fetchall()
        conn.close()
        
        results = "Users:\n"
        for user_id, name in users:
            results += f"    - {name} (user_id: {user_id})\n"
        
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if recipient exists
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not cursor.fetchone():
            conn.close()
            return f"User {user_id} does not exist."
        
        # Create and store message
        message_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO messages (message_id, from_user_id, from_user_name, to_user_id, message, is_new) VALUES (?, ?, ?, ?, ?, 1)",
            (message_id, agent.id, agent.name, user_id, message)
        )
        
        conn.commit()
        conn.close()
        
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM messages WHERE to_user_id = ? AND is_new = 1", (agent.id,))
        count = cursor.fetchone()[0]
        conn.close()
        
        if count == 0:
            return "Messages:\n    [No new messages]"
        return f"There are {count} new messages."

    def _get_messages_string(self, messages):
        results = "Messages:\n"
        if not messages:
            results += "    [No messages]\n"
            return results
            
        for message_id, from_user_id, from_user_name, message in messages:
            results += f"    - From {from_user_name}: {message}\n"
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT message_id, from_user_id, from_user_name, message FROM messages WHERE to_user_id = ? AND is_new = 1",
            (agent.id,)
        )
        messages = cursor.fetchall()
        
        # Mark messages as read
        cursor.execute(
            "UPDATE messages SET is_new = 0 WHERE to_user_id = ? AND is_new = 1",
            (agent.id,)
        )
        
        conn.commit()
        conn.close()
        
        return self._get_messages_string(messages)

    def get_messages(self, agent: Agent, sender_id: Optional[str] = None, limit: int = 10):
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if sender_id:
            cursor.execute(
                "SELECT message_id, from_user_id, from_user_name, message FROM messages "
                "WHERE to_user_id = ? AND from_user_id = ? ORDER BY rowid DESC LIMIT ?",
                (agent.id, sender_id, limit)
            )
        else:
            cursor.execute(
                "SELECT message_id, from_user_id, from_user_name, message FROM messages "
                "WHERE to_user_id = ? ORDER BY rowid DESC LIMIT ?",
                (agent.id, limit)
            )
            
        messages = cursor.fetchall()
        conn.close()
        
        return self._get_messages_string(messages)

    ############### Agent Interface ###############
    def get_toolset_details(self):
        return ToolsetDetails(
            toolset_id="messages",
            name="Messages",
            description="A toolset for sending and receiving messages between users."
        )
    
    def get_tool_schemas(self):
        return [tool_schema.model_dump_json() for tool_schema in self.tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.name == "send_message":
            return self.send_message(agent, tool_call.arguments["user_id"], tool_call.arguments["message"])
        elif tool_call.name == "get_messages":
            sender_id = tool_call.arguments.get("sender_id")
            limit = tool_call.arguments.get("limit", 10)
            return self.get_messages(agent, sender_id, limit)
        elif tool_call.name == "get_new_messages":
            return self.get_new_messages(agent)
        elif tool_call.name == "get_new_message_count":
            return self.get_new_message_count(agent)
        elif tool_call.name == "get_users":
            return self.get_users()
        else:
            return "Invalid tool call."
