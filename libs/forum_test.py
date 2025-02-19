import json
from datetime import datetime
from agent import Agent
from forum import Directory
from common import ToolCall
import os

def main():
    # Delete test database if it exists
    if os.path.exists("test.db"):
        os.remove("test.db")

    # Initialize the directory with SQLite database
    directory = Directory("test.db")
    
    # Create a test agent
    test_agent = Agent(
        name="TestUser",
        private_key="test_agent_1",
        persona="A test user for the forum system",
        initial_instructions="You are a test user for the forum system. You are not an agent, but a user of the forum.",
        initial_notes=[]
    )
    
    # Test user creation and retrieval
    print("\n=== Testing User Operations ===")
    directory.create_user(user_id="user1", name="Alice", persona="Regular forum user")
    directory.create_user(user_id="user2", name="Bob", persona="Tech enthusiast")
    
    print(f"Total users: {directory.get_user_count()}")
    users = directory.get_users(limit=5)
    print("First 5 users:", [user.name for user in users])
    
    # Test forum creation and management
    print("\n=== Testing Forum Operations ===")
    tech_forum = directory.create_forum(
        creator_id=test_agent.id,
        title="Technology Discussion",
        description="A place to discuss the latest in tech",
        flags=["tech", "discussion"]
    )
    print("Forum creation response:", tech_forum)
    
    gaming_forum = directory.create_forum(
        creator_id=test_agent.id,
        title="Gaming Corner",
        description="Discuss your favorite games",
        flags=["gaming", "entertainment"]
    )
    print("Second forum creation response:", gaming_forum)
    
    # Test forum search
    print("\n=== Testing Forum Search ===")
    search_results = directory.search_forums("tech")
    print("Forums containing 'tech':", [forum.title for forum in search_results])
    
    # Test posting
    print("\n=== Testing Post Operations ===")
    post = directory.create_post(
        forum_id=tech_forum.forum_id,
        author_id=test_agent.id,
        content="Hello everyone! This is our first post about technology.",
        title="Welcome to Tech Discussion",
        files=[],
        flags=["welcome"]
    )
    print("Post creation response:", post)
    
    # Test post retrieval
    posts = directory.get_posts_by_forum(tech_forum.forum_id, limit=5)
    print("\nPosts in tech forum:")
    for post in posts:
        print(f"- {post.title}: {post.content[:50]}...")
    
    # Test user forum interactions
    print("\n=== Testing User Forum Interactions ===")
    subscribe_response = directory.subscribe_to_forum(test_agent.id, tech_forum.forum_id)
    print("Subscribe response:", subscribe_response)
    
    join_response = directory.join_forum(test_agent.id, tech_forum.forum_id)
    print("Join forum response:", join_response)
    
    # Test user's forum views
    subscribed_forums = directory.get_subscribed_forums(test_agent.id)
    print("\nSubscribed forums:", [forum.title for forum in subscribed_forums])
    
    current_forums = directory.get_current_forums(test_agent.id)
    print("Current forums:", [forum.title for forum in current_forums])
    
    # Test cleanup
    print("\n=== Testing Cleanup Operations ===")
    delete_response = directory.delete_forum(tech_forum.forum_id, test_agent.id)
    print("Forum deletion response:", delete_response)
    
    # Final status
    print("\n=== Final System Status ===")
    print(f"Total forums: {directory.get_forum_count()}")
    print(f"Total users: {directory.get_user_count()}")

    # Test agent interface
    print("\n=== Testing Agent Interface ===")
    
    # Create a test forum for agent interface testing
    test_forum = directory.create_forum(
        creator_id=test_agent.id,
        title="Test Forum",
        description="A test forum",
        flags=[]
    )
    
    # Create a test post
    test_post = directory.create_post(
        forum_id=test_forum.forum_id,
        author_id=test_agent.id,
        content="This is a test post",
        title="Test Post"
    )

    # Test all agent interface methods
    test_calls = [
        ("get_user_by_id", {"user_id": test_agent.id}),
        ("get_user_by_name", {"name": "Alice"}),
        ("get_users", {"limit": 5, "offset": 0}),
        ("get_user_count", {}),
        ("search_users", {"query": "Alice", "limit": 5}),
        ("search_forums", {"query": "test"}),
        ("get_forum_count", {}),
        ("get_forums", {"limit": 5, "offset": 0}),
        ("get_forum_by_title", {"title": "Test Forum"}),
        ("get_forum_by_id", {"forum_id": test_forum.forum_id}),
        ("get_random_forum", {}),
        ("get_post_by_id", {"post_id": test_post.post_id}),
        ("get_posts_by_forum", {"forum_id": test_forum.forum_id, "limit": 5, "offset": 0}),
        ("get_posts_by_author", {"author_id": test_agent.id, "limit": 5, "offset": 0}),
        ("reply_to_post", {"post_id": test_post.post_id, "content": "This is a test reply"}),
        ("subscribe_to_forum", {"forum_id": test_forum.forum_id}),
        ("get_subscribed_posts", {"user_id": test_agent.id, "limit": 5, "offset": 0}),
        ("get_subscribed_forums", {"user_id": test_agent.id}),
        ("unsubscribe_from_forum", {"forum_id": test_forum.forum_id}),
        ("join_forum", {"forum_id": test_forum.forum_id}),
        ("get_current_forums", {"user_id": test_agent.id}),
        ("get_current_posts", {"user_id": test_agent.id, "limit": 5, "offset": 0}),
        ("leave_forum", {"forum_id": test_forum.forum_id})
    ]

    for name, args in test_calls:
        print(f"\nTesting {name}:")
        print("~" * 50)
        try:
            result = directory.agent_tool_callback(
                test_agent,
                ToolCall(toolset_id="forum_toolset", name=name, arguments=args)
            )
            print(result)
        except Exception as e:
            print(f"Error testing {name}: {str(e)}")
        print("~" * 50)

if __name__ == "__main__":
    main()