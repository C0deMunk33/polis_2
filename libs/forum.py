
try:
    from .common import ToolCall, ToolSchema
    from .agent import Agent
except ImportError:
    from common import ToolCall, ToolSchema
    from agent import Agent
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import random

import uuid
import sqlite3
import json

class ForumUser(BaseModel):
    user_id: str
    name: str
    persona: str
    created_at: datetime
    subscribed_forums: List[str] # forum ids of the forums the user is subscribed to
    current_forums: List[str] # forum ids of the forums the user is currently active in

class ForumPost(BaseModel):
    forum_id: str
    post_id: str
    content: str
    author_id: str
    created_at: datetime

    title: Optional[str] = None
    parent_id: Optional[str] = None
    files: List[str]
    flags: List[str]

class Forum(BaseModel):
    forum_id: str
    creator_id: str
    title: str
    description: str
    flags: List[str]
    posts: List[ForumPost]

class Directory:
    """This is the directory of forums"""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.tool_schemas = []
        self._init_db()
        
        names_of_tools_to_expose = [
            "get_user_by_id",
            "get_user_by_name",
            "get_users",
            "get_user_count",
            "search_users",
            "create_forum",
            "delete_forum",
            "search_forums",
            "get_forum_by_id",
            "get_forum_by_title",
            "get_random_forum",
            "get_subscribed_forums",
            "get_current_forums",
            "subscribe_to_forum",
            "unsubscribe_from_forum",
            "join_forum",
            "leave_forum",
            "create_post",
            "delete_post",
            "get_post_by_id",
            "get_posts_by_author",
            "get_posts_by_forum",
            "get_subscribed_posts",
            "get_current_posts",
            "reply_to_post",
            "set_forum_name",
            "set_forum_persona"
        ]

        for name in names_of_tools_to_expose:
            docstring = getattr(self, name).__doc__
            tool_schema = ToolSchema.model_validate_json(docstring)
            self.tool_schemas.append(tool_schema)

    def _init_db(self):
        """Initialize the SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    subscribed_forums TEXT NOT NULL,
                    current_forums TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forums (
                    forum_id TEXT PRIMARY KEY,
                    creator_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    flags TEXT NOT NULL,
                    FOREIGN KEY (creator_id) REFERENCES users (user_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    post_id TEXT PRIMARY KEY,
                    forum_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    title TEXT,
                    parent_id TEXT,
                    files TEXT NOT NULL,
                    flags TEXT NOT NULL,
                    FOREIGN KEY (forum_id) REFERENCES forums (forum_id),
                    FOREIGN KEY (author_id) REFERENCES users (user_id),
                    FOREIGN KEY (parent_id) REFERENCES posts (post_id)
                )
            """)

    def _list_to_json(self, lst: List) -> str:
        """Convert a list to JSON string for storage"""
        return json.dumps(lst)

    def _json_to_list(self, json_str: str) -> List:
        """Convert a JSON string back to list"""
        return json.loads(json_str)

    ############### USER FUNCTIONS ###############

    def get_user_by_id(self, user_id: str) -> Optional[ForumUser]:
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_user_by_id",
            "description": "Gets a user by id",
            "arguments": [{
                "name": "user_id",
                "type": "str",
                "description": "The id of the user to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", 
                (user_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return ForumUser(
                user_id=row[0],
                name=row[1],
                persona=row[2],
                created_at=datetime.fromisoformat(row[3]),
                subscribed_forums=self._json_to_list(row[4]),
                current_forums=self._json_to_list(row[5])
            )
    
    def get_user_by_name(self, name: str) -> Optional[ForumUser]:
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_user_by_name",
            "description": "Gets a user by name",
            "arguments": [{
                "name": "name",
                "type": "str",
                "description": "The name of the user to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return ForumUser(
                user_id=row[0],
                name=row[1],
                persona=row[2],
                created_at=datetime.fromisoformat(row[3]),
                subscribed_forums=self._json_to_list(row[4]),
                current_forums=self._json_to_list(row[5])
            )
    
    def get_users(self, limit: int = 10, offset: int = 0) -> List[ForumUser]:
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_users",
            "description": "Gets users",
            "arguments": [{
                "name": "limit",
                "type": "int",
                "description": "The number of users to get"
            }, {
                "name": "offset",
                "type": "int",
                "description": "The offset of the users to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM users LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [
                ForumUser(
                    user_id=row[0],
                    name=row[1],
                    persona=row[2],
                    created_at=datetime.fromisoformat(row[3]),
                    subscribed_forums=self._json_to_list(row[4]),
                    current_forums=self._json_to_list(row[5])
                )
                for row in cursor.fetchall()
            ]
    
    def get_user_count(self) -> int:
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_user_count",
            "description": "Gets the number of users",
            "arguments": []
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]
    
    def search_users(self, query: str, limit: int = 20) -> List[ForumUser]:
        """
        {
            "toolset_id": "forum_toolset",
            "name": "search_users",
            "description": "Searches for users",
            "arguments": [{
                "name": "query",
                "type": "str",
                "description": "The query to search for"
            }, {
                "name": "limit",
                "type": "int",
                "description": "The number of users to return"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE name LIKE ? LIMIT ?",
                (f"%{query}%", limit)
            )
            return [
                ForumUser(
                    user_id=row[0],
                    name=row[1],
                    persona=row[2],
                    created_at=datetime.fromisoformat(row[3]),
                    subscribed_forums=self._json_to_list(row[4]),
                    current_forums=self._json_to_list(row[5])
                )
                for row in cursor.fetchall()
            ]

    def create_user(self, user_id: str, name: str, persona: str) -> ForumUser:
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.now()
            conn.execute(
                """
                INSERT INTO users (user_id, name, persona, created_at, subscribed_forums, current_forums)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, name, persona, now.isoformat(), "[]", "[]")
            )
            return self.get_user_by_id(user_id)
    
    def delete_user(self, user_id: str) -> str:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM posts WHERE author_id = ?", (user_id,))
            return "User deleted"

    ############### FORUM FUNCTIONS ###############

    def create_forum(self, creator_id: str, title: str, description: str, flags: List[str]):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "create_forum",
            "description": "Creates a forum",
            "arguments": [{
                "name": "title",
                "type": "str",
                "description": "The title of the forum"
            }, {
                "name": "description",
                "type": "str",
                "description": "The description of the forum"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            forum_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO forums (forum_id, creator_id, title, description, flags)
                VALUES (?, ?, ?, ?, ?)
                """,
                (forum_id, creator_id, title, description, self._list_to_json(flags))
            )
            conn.commit()
            
            return Forum(
                forum_id=forum_id,
                creator_id=creator_id,
                title=title,
                description=description,
                flags=flags,
                posts=[]  # New forum has no posts yet
            )
    
    def delete_forum(self, forum_id: str, agent_id: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "delete_forum",
            "description": "Deletes a forum",
            "arguments": [{
                "name": "forum_id",
                "type": "str",
                "description": "The id of the forum to delete"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM forums WHERE forum_id = ? AND creator_id = ?", (forum_id, agent_id))
            conn.execute("DELETE FROM posts WHERE forum_id = ?", (forum_id,))
        return "Forum deleted"

    def search_forums(self, query: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "search_forums",
            "description": "Searches for forums",
            "arguments": [{
                "name": "query",
                "type": "str",
                "description": "The query to search for"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM forums WHERE title LIKE ?",
                (f"%{query}%",)
            )
            return [
                Forum(
                    forum_id=row[0],
                    creator_id=row[1],
                    title=row[2],
                    description=row[3],
                    flags=self._json_to_list(row[4]),
                    posts=[]
                )
                for row in cursor.fetchall()
            ]

    def get_forum_count(self):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_forum_count",
            "description": "Gets the number of forums",
            "arguments": []
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM forums")
            return cursor.fetchone()[0]

    def get_forums(self, limit: int = 10, offset: int = 0):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_forums",
            "description": "Gets forums",
            "arguments": [{
                "name": "limit",
                "type": "int",
                "description": "The number of forums to get"
            }, {
                "name": "offset",
                "type": "int",
                "description": "The offset of the forums to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM forums LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [
                Forum(
                    forum_id=row[0],
                    creator_id=row[1],
                    title=row[2],
                    description=row[3],
                    flags=self._json_to_list(row[4]),
                    posts=[]
                )
                for row in cursor.fetchall()
            ]
     
    def get_forum_by_title(self, title: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_forum_by_title",
            "description": "Gets a forum by title",
            "arguments": [{
                "name": "title",
                "type": "str",
                "description": "The title of the forum to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM forums WHERE title = ?",
                (title,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Forum(
                forum_id=row[0],
                creator_id=row[1],
                title=row[2],
                description=row[3],
                flags=self._json_to_list(row[4]),
                posts=[]
            )
    
    def get_forum_by_id(self, forum_id: str) -> Optional[Forum]:
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_forum_by_id",
            "description": "Gets a forum by id",
            "arguments": [{
                "name": "forum_id",
                "type": "str",
                "description": "The id of the forum to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            # First get the forum
            cursor = conn.execute(
                "SELECT * FROM forums WHERE forum_id = ?",
                (forum_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
                
            # Then get all posts for this forum
            posts_cursor = conn.execute(
                "SELECT * FROM posts WHERE forum_id = ?",
                (forum_id,)
            )
            posts = [
                ForumPost(
                    forum_id=post_row[1],
                    post_id=post_row[0],
                    content=post_row[3],
                    author_id=post_row[2],
                    created_at=datetime.fromisoformat(post_row[4]),
                    title=post_row[5],
                    parent_id=post_row[6],
                    files=self._json_to_list(post_row[7]),
                    flags=self._json_to_list(post_row[8])
                )
                for post_row in posts_cursor.fetchall()
            ]
            
            return Forum(
                forum_id=row[0],
                creator_id=row[1],
                title=row[2],
                description=row[3],
                flags=self._json_to_list(row[4]),
                posts=posts
            )
    
    def get_random_forum(self):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_random_forum",
            "description": "Gets a random forum",
            "arguments": []
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM forums ORDER BY RANDOM() LIMIT 1")
            row = cursor.fetchone()
            if row is None:
                return None
            return Forum(
                forum_id=row[0],
                creator_id=row[1],
                title=row[2],
                description=row[3],
                flags=self._json_to_list(row[4]),
                posts=[]
            )
    
    def get_subscribed_forums(self, user_id: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_subscribed_forums",
            "description": "Gets the forums a user is subscribed to",
            "arguments": [{
                "name": "user_id",
                "type": "str",
                "description": "The id of the user to get subscribed forums for"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            # First get the user's subscribed forums list
            cursor = conn.execute(
                "SELECT subscribed_forums FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return "User not found"
            
            # Get the list of forum IDs
            forum_ids = self._json_to_list(row[0])
            if not forum_ids:
                return []
            
            # Now get the forums
            placeholders = ','.join('?' * len(forum_ids))
            cursor = conn.execute(
                f"SELECT * FROM forums WHERE forum_id IN ({placeholders})",
                forum_ids
            )
            return [
                Forum(
                    forum_id=row[0],
                    creator_id=row[1],
                    title=row[2],
                    description=row[3],
                    flags=self._json_to_list(row[4]),
                    posts=[]
                )
                for row in cursor.fetchall()
            ]
    
    def get_current_forums(self, user_id: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_current_forums",
            "description": "Gets the forums you are currently active in",
            "arguments": []
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            # First get the user's current forums list
            cursor = conn.execute(
                "SELECT current_forums FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return "User not found"
            
            # Get the list of forum IDs
            forum_ids = self._json_to_list(row[0])
            if not forum_ids:
                return []
            
            # Now get the forums
            placeholders = ','.join('?' * len(forum_ids))
            cursor = conn.execute(
                f"SELECT * FROM forums WHERE forum_id IN ({placeholders})",
                forum_ids
            )
            return [
                Forum(
                    forum_id=row[0],
                    creator_id=row[1],
                    title=row[2],
                    description=row[3],
                    flags=self._json_to_list(row[4]),
                    posts=[]
                )
                for row in cursor.fetchall()
            ]
    
    def subscribe_to_forum(self, user_id: str, forum_id: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "subscribe_to_forum",
            "description": "Subscribe to a forum",
            "arguments": [{
                "name": "forum_id",
                "type": "str",
                "description": "The id of the forum to subscribe to"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            # First get current subscribed forums
            cursor = conn.execute(
                "SELECT subscribed_forums FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return "User not found"
            
            # check that forum exists
            cursor = conn.execute(
                "SELECT * FROM forums WHERE forum_id = ?",
                (forum_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return "Forum not found"
            # Update the list
            current_forums = self._json_to_list(row[0])
            if forum_id not in current_forums:
                current_forums.append(forum_id)
            
            # Save back to database
            conn.execute(
                "UPDATE users SET subscribed_forums = ? WHERE user_id = ?",
                (self._list_to_json(current_forums), user_id)
            )
            return f"Subscribed to forum {forum_id}: {self.get_forum_by_id(forum_id).title}"
    
    def unsubscribe_from_forum(self, user_id: str, forum_id: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "unsubscribe_from_forum",
            "description": "Unsubscribe from a forum",
            "arguments": [{
                "name": "forum_id",
                "type": "str",
                "description": "The id of the forum to unsubscribe from"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            # First get current subscribed forums
            cursor = conn.execute(
                "SELECT subscribed_forums FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return "User not found"
            
            # Update the list
            current_forums = self._json_to_list(row[0])
            if forum_id in current_forums:
                current_forums.remove(forum_id)
            
            # Save back to database
            conn.execute(
                "UPDATE users SET subscribed_forums = ? WHERE user_id = ?",
                (self._list_to_json(current_forums), user_id)
            )
            return f"Unsubscribed from forum {forum_id}: {self.get_forum_by_id(forum_id).title}"

    def join_forum(self, user_id: str, forum_id: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "join_forum",
            "description": "Join a forum",
            "arguments": [{
                "name": "forum_id",
                "type": "str",
                "description": "The id of the forum to join"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:

            # check that forum exists
            cursor = conn.execute(
                "SELECT * FROM forums WHERE forum_id = ?",
                (forum_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return "Forum not found"
            # First get current forums
            cursor = conn.execute(
                "SELECT current_forums FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return "User not found"
            
            # Update the list
            current_forums = self._json_to_list(row[0])
            if forum_id not in current_forums:
                current_forums.append(forum_id)
            
            # Save back to database
            conn.execute(
                "UPDATE users SET current_forums = ? WHERE user_id = ?",
                (self._list_to_json(current_forums), user_id)
            )
            return f"Joined forum {forum_id}: {self.get_forum_by_id(forum_id).title}"
        
    def leave_forum(self, user_id: str, forum_id: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "leave_forum",
            "description": "Leave a forum",
            "arguments": [{
                "name": "forum_id",
                "type": "str",
                "description": "The id of the forum to leave"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            # First get current forums
            cursor = conn.execute(
                "SELECT current_forums FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return "User not found"
            
            # Update the list
            current_forums = self._json_to_list(row[0])
            if forum_id in current_forums:
                current_forums.remove(forum_id)
            
            # Save back to database
            conn.execute(
                "UPDATE users SET current_forums = ? WHERE user_id = ?",
                (self._list_to_json(current_forums), user_id)
            )
            return f"Left forum {forum_id}: {self.get_forum_by_id(forum_id).title}"
    
    ############### Post Functions ###############
    
    def create_post(self, forum_id: str, author_id: str, content: str, title: Optional[str] = None, parent_id: Optional[str] = None, files: List[str] = [], flags: List[str] = []):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "create_post",
            "description": "Creates a post",
            "arguments": [{
                "name": "forum_id",
                "type": "str",
                "description": "The id of the forum to create the post in"
            },{ 
                "name" : "content",
                "type" : "str",
                "description" : "The content of the post"
            },{
                "name": "title",
                "type": "str",
                "description": "The title of the post"
            }]
        }
        """
        post_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO posts (post_id, forum_id, author_id, content, created_at, title, parent_id, files, flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (post_id, forum_id, author_id, content, datetime.now().isoformat(), title, parent_id, self._list_to_json(files), self._list_to_json(flags))
            )
        post = self.get_post_by_id(post_id)
        return post
    
    def delete_post(self, agent_id: str, post_id: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "delete_post",
            "description": "Deletes a post",
            "arguments": [{
                "name": "post_id",
                "type": "str",
                "description": "The id of the post to delete"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM posts WHERE post_id = ? AND author_id = ?", (post_id, agent_id))
        return "Post deleted"
    
    def get_post_by_id(self, post_id: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_post_by_id",
            "description": "Gets a post by id",
            "arguments": [{
                "name": "post_id",
                "type": "str",
                "description": "The id of the post to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM posts WHERE post_id = ?",
                (post_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return ForumPost(
                forum_id=row[1],
                post_id=row[0],
                content=row[3],
                author_id=row[2],
                created_at=datetime.fromisoformat(row[4]),
                title=row[5],
                parent_id=row[6],
                files=self._json_to_list(row[7]),
                flags=self._json_to_list(row[8])
            )
     
    def get_posts_by_author(self, author_id: str, limit: int = 10, offset: int = 0):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_posts_by_author",
            "description": "Gets posts by author",
            "arguments": [{
                "name": "author_id",
                "type": "str",
                "description": "The id of the author to get posts by"
            }, {
                "name": "limit",
                "type": "int",
                "description": "The number of posts to get"
            }, {
                "name": "offset",
                "type": "int",
                "description": "The offset of the posts to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM posts WHERE author_id = ? ORDER BY created_at LIMIT ? OFFSET ?",
                (author_id, limit, offset)
            )
            rows = cursor.fetchall()
            if rows is None:
                return []
            return [
                ForumPost(
                    forum_id=row[1],
                    post_id=row[0],
                    content=row[3],
                    author_id=row[2],
                    created_at=datetime.fromisoformat(row[4]),
                    title=row[5],
                    parent_id=row[6],
                    files=self._json_to_list(row[7]),
                    flags=self._json_to_list(row[8])
                )
                for row in rows
            ]
    
    def get_posts_by_forum(self, forum_id: str, limit: int = 10, offset: int = 0):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_posts_by_forum",
            "description": "Gets posts by forum",
            "arguments": [{
                "name": "forum_id",
                "type": "str",
                "description": "The id of the forum to get posts by"
            }, {
                "name": "limit",
                "type": "int",
                "description": "The number of posts to get"
            }, {
                "name": "offset",
                "type": "int",
                "description": "The offset of the posts to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM posts WHERE forum_id = ? ORDER BY created_at LIMIT ? OFFSET ?",
                (forum_id, limit, offset)
            )
            rows = cursor.fetchall()
            if rows is None:
                return []
            return [
                ForumPost(
                    forum_id=row[1],
                    post_id=row[0],
                    content=row[3],
                    author_id=row[2],
                    created_at=datetime.fromisoformat(row[4]),
                    title=row[5],
                    parent_id=row[6],
                    files=self._json_to_list(row[7]),
                    flags=self._json_to_list(row[8])
                )
                for row in rows
            ]

    def get_subscribed_posts(self, user_id: str, limit: int = 10, offset: int = 0):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_subscribed_posts",
            "description": "Gets time-ordered posts from the forums a user is subscribed to",
            "arguments": [{
                "name": "limit",
                "type": "int",
                "description": "The number of posts to get"
            }, {
                "name": "offset",
                "type": "int",
                "description": "The offset of the posts to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM posts WHERE forum_id IN (SELECT forum_id FROM users WHERE user_id = ? AND ? IN (SELECT * FROM json_each(subscribed_forums))) ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, user_id, limit, offset)
            )
            rows = cursor.fetchall()
            if rows is None:
                return []
            return [
                ForumPost(
                    forum_id=row[1],
                    post_id=row[0],
                    content=row[3],
                    author_id=row[2],
                    created_at=datetime.fromisoformat(row[4]),
                    title=row[5],
                    parent_id=row[6],
                    files=self._json_to_list(row[7]),
                    flags=self._json_to_list(row[8])
                )
                for row in rows
            ]
        
    def get_current_posts(self, user_id: str, limit: int = 10, offset: int = 0):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "get_current_posts",
            "description": "Gets time-ordered posts from the forums a user is currently active in",
            "arguments": [{
                "name": "limit",
                "type": "int",
                "description": "The number of posts to get"
            }, {
                "name": "offset",
                "type": "int",
                "description": "The offset of the posts to get"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM posts WHERE forum_id IN (SELECT forum_id FROM users WHERE user_id = ? AND ? IN (SELECT * FROM json_each(current_forums))) ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, user_id, limit, offset)
            )
            rows = cursor.fetchall()
            if rows is None:
                return []
            return [
                ForumPost(
                    forum_id=row[1],
                    post_id=row[0],
                    content=row[3],
                    author_id=row[2],
                    created_at=datetime.fromisoformat(row[4]),
                    title=row[5],
                    parent_id=row[6],
                    files=self._json_to_list(row[7]),
                    flags=self._json_to_list(row[8])
                )
                for row in rows
            ]
        
    def reply_to_post(self, user_id: str, post_id: str, content: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "reply_to_post",
            "description": "Reply to a post",
            "arguments": [{
                "name": "post_id",
                "type": "str",
                "description": "The id of the post to reply to"
            },{
                "name": "content",
                "type": "str",
                "description": "The content of the reply"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM posts WHERE post_id = ?",
                (post_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return "Post not found"
            reply_post = self.create_post(row[1], user_id, content, row[5], row[0], self._json_to_list(row[7]), self._json_to_list(row[8]))
            return reply_post
    
    ################## User Functions ##################
    def set_forum_name(self, user_id: str, name: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "set_forum_name",
            "description": "Set your name in the forum",
            "arguments": [{
                "name": "name",
                "type": "str",
                "description": "your new name for the forum"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET name = ? WHERE user_id = ?",
                (name, user_id)
            )
            return f"Name set to {name}"
    
    def set_forum_persona(self, user_id: str, persona: str):
        """
        {
            "toolset_id": "forum_toolset",
            "name": "set_forum_persona",
            "description": "Set your persona in the forum",
            "arguments": [{
                "name": "persona",
                "type": "str",
                "description": "your new persona for the forum"
            }]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET persona = ? WHERE user_id = ?",
                (persona, user_id)
            )
            return f"Persona set to {persona}"

    ############### Agent Interface ###############
    def get_tool_schemas(self):
        return [tool_schema.model_dump_json() for tool_schema in self.tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.toolset_id != "forum_toolset":
            raise ValueError(f"Toolset {tool_call.toolset_id} not found")
        
        # check that agent has a user, otherwise create one (they share ids)
        agent_user = next((user for user in self.get_users() if user.user_id == agent.id), None)
        if agent_user is None:
            agent_user = self.create_user(agent.id, agent.name, agent.persona)

        if tool_call.name == "get_user_by_id":
            return self.get_user_by_id(tool_call.arguments["user_id"]).model_dump_json()
        elif tool_call.name == "get_user_by_name":
            return self.get_user_by_name(tool_call.arguments["name"]).model_dump_json()
        elif tool_call.name == "get_users":
            offset = tool_call.arguments["offset"] if "offset" in tool_call.arguments else 0
            limit = tool_call.arguments["limit"] if "limit" in tool_call.arguments else 10
            return [user.model_dump_json() for user in self.get_users(limit, offset)]
        elif tool_call.name == "get_user_count":
            return self.get_user_count()
        elif tool_call.name == "search_users":
            return [user.model_dump_json() for user in self.search_users(tool_call.arguments["query"], tool_call.arguments["limit"])]   
        elif tool_call.name == "delete_user":
            if agent.id != tool_call.arguments["user_id"]:
                return "You cannot delete other users"
            return self.delete_user(tool_call.arguments["user_id"])
        elif tool_call.name == "create_forum":
            return self.create_forum(agent.id, tool_call.arguments["title"], tool_call.arguments["description"], []).model_dump_json()
        elif tool_call.name == "delete_forum":
            return self.delete_forum(agent.id, tool_call.arguments["forum_id"])
        elif tool_call.name == "search_forums":
            return [forum.model_dump_json() for forum in self.search_forums(tool_call.arguments["query"])]
        elif tool_call.name == "get_forum_count":
            return self.get_forum_count()
        elif tool_call.name == "get_forums":
            return [forum.model_dump_json() for forum in self.get_forums(tool_call.arguments["limit"], tool_call.arguments["offset"])]
        elif tool_call.name == "get_forum_by_title":
            result = self.get_forum_by_title(tool_call.arguments["title"])
            if result is None:
                return "Forum not found"
            return result.model_dump_json()
        elif tool_call.name == "get_forum_by_id":
            result = self.get_forum_by_id(tool_call.arguments["forum_id"])
            if result is None:
                return "Forum not found"
            return result.model_dump_json()
        elif tool_call.name == "get_random_forum":
            return self.get_random_forum().model_dump_json()
        elif tool_call.name == "create_post":
            return self.create_post(tool_call.arguments["forum_id"], agent.id, tool_call.arguments["content"], tool_call.arguments["title"], None, [], []).model_dump_json()
        elif tool_call.name == "delete_post":
            return self.delete_post(agent.id, tool_call.arguments["post_id"])
        elif tool_call.name == "get_post_by_id":
            return self.get_post_by_id(tool_call.arguments["post_id"]).model_dump_json()
        elif tool_call.name == "get_posts_by_forum":
            limit = tool_call.arguments["limit"] if "limit" in tool_call.arguments else 10
            offset = tool_call.arguments["offset"] if "offset" in tool_call.arguments else 0
            return [post.model_dump_json() for post in self.get_posts_by_forum(tool_call.arguments["forum_id"], limit, offset)]
        elif tool_call.name == "get_posts_by_author":
            return [post.model_dump_json() for post in self.get_posts_by_author(tool_call.arguments["author_id"], tool_call.arguments["limit"], tool_call.arguments["offset"])]
        elif tool_call.name == "get_subscribed_posts":
            return [post.model_dump_json() for post in self.get_subscribed_posts(tool_call.arguments["user_id"], tool_call.arguments["limit"], tool_call.arguments["offset"])]
        elif tool_call.name == "get_current_posts":
            return [post.model_dump_json() for post in self.get_current_posts(agent.id, tool_call.arguments["limit"], tool_call.arguments["offset"])]
        elif tool_call.name == "reply_to_post":
            return self.reply_to_post(agent.id, tool_call.arguments["post_id"], tool_call.arguments["content"]).model_dump_json()
        elif tool_call.name == "get_subscribed_forums":
            return [forum.model_dump_json() for forum in self.get_subscribed_forums(tool_call.arguments["user_id"])]
        elif tool_call.name == "get_current_forums":
            return [forum.model_dump_json() for forum in self.get_current_forums(agent.id)]
        elif tool_call.name == "subscribe_to_forum":
            return self.subscribe_to_forum(agent.id, tool_call.arguments["forum_id"])
        elif tool_call.name == "unsubscribe_from_forum":
            return self.unsubscribe_from_forum(agent.id, tool_call.arguments["forum_id"])
        elif tool_call.name == "join_forum":
            return self.join_forum(agent.id, tool_call.arguments["forum_id"])
        elif tool_call.name == "leave_forum":
            return self.leave_forum(agent.id, tool_call.arguments["forum_id"])
        elif tool_call.name == "set_forum_name":
            return self.set_forum_name(agent.id, tool_call.arguments["name"])
        elif tool_call.name == "set_forum_persona":
            return self.set_forum_persona(agent.id, tool_call.arguments["persona"])
        else:
            raise ValueError(f"Tool {tool_call.name} not found")
 


