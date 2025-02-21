from flask import Flask, request, jsonify, send_from_directory
import os
from libs.forum import Directory  # Assuming your code is in `directory.py`

app = Flask(__name__)
app.static_folder = 'web'
app.static_url_path = '/static'

# Create the Directory instance pointing to our forum.db
db_path = os.path.join(os.path.dirname(__file__), 'forum.db')
directory = Directory(db_path)

@app.route('/')
@app.route('/forum/<forum_id>')
@app.route('/forum/<forum_id>/post/<post_id>')  # Add route for single post view
def serve_app(forum_id=None, post_id=None):
    """Serve the main index page for all app routes."""
    if forum_id:
        # Validate that the forum exists
        forum = directory.get_forum_by_id(forum_id)
        if not forum:
            return jsonify({"error": "Forum not found"}), 404
            
        if post_id:
            # If post_id is provided, validate that the post exists in this forum
            post_exists = any(p.post_id == post_id for p in forum.posts)
            if not post_exists:
                return jsonify({"error": "Post not found"}), 404
                
    return send_from_directory('web', 'index.html')

@app.route('/api/forums', methods=['GET', 'POST'])
def forums():
    if request.method == 'GET':
        # Here, we want to return a JSON list of forums
        # We'll manually parse the Directory's get_forum_objects for clarity
        forum_objects = directory.get_forum_objects(limit=100)  # a large limit
        # Convert Forum objects to dict
        data = []
        for forum in forum_objects:
            data.append({
                "forum_id": forum.forum_id,
                "creator_id": forum.creator_id,
                "title": forum.title,
                "description": forum.description,
                "flags": forum.flags,
            })
        return jsonify(data)

    elif request.method == 'POST':
        # Create a new forum
        payload = request.json
        title = payload.get('title', '')
        description = payload.get('description', '')
        
        # For demonstration, let's assume we have a "guest" user as the creator
        # or you can adapt to real user sessions, etc.
        creator_id = "guest-user-id"
        
        new_forum = directory.create_forum(
            creator_id=creator_id,
            title=title,
            description=description,
            flags=[]
        )
        # Convert the new forum to a JSON-friendly dict
        result = {
            "forum_id": new_forum.forum_id,
            "creator_id": new_forum.creator_id,
            "title": new_forum.title,
            "description": new_forum.description,
            "flags": new_forum.flags
        }
        return jsonify(result), 201

# Example: an endpoint to retrieve a single forum by ID
@app.route('/api/forums/<forum_id>', methods=['GET'])
def get_forum_by_id(forum_id):
    forum = directory.get_forum_by_id(forum_id)
    if not forum:
        return jsonify({"error": "Forum not found"}), 404
    
    result = {
        "forum_id": forum.forum_id,
        "creator_id": forum.creator_id,
        "title": forum.title,
        "description": forum.description,
        "flags": forum.flags,
        "posts": [p.model_dump() for p in forum.posts]
    }
    return jsonify(result)

# Example: an endpoint to get posts for a forum
@app.route('/api/forums/<forum_id>/posts', methods=['GET'])
def get_forum_posts(forum_id):
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))
    posts = directory.get_posts_by_forum(forum_id, limit, offset)
    data = [p.model_dump() for p in posts]
    return jsonify(data)

# Example: an endpoint to create a new post in a forum
@app.route('/api/forums/<forum_id>/posts', methods=['POST'])
def create_post_in_forum(forum_id):
    payload = request.json
    author_id = "guest-user-id"
    content = payload.get('content', '')
    title = payload.get('title', None)
    parent_id = payload.get('parent_id', None)

    post = directory.create_post(
        forum_id=forum_id, 
        author_id=author_id, 
        content=content, 
        title=title,
        parent_id=parent_id
    )
    return jsonify(post.model_dump()), 201

# Add a route to serve static files from web directory
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('web', path)

if __name__ == '__main__':
    # Run Flask in debug mode for local development
    app.run(debug=True, port=5001)
