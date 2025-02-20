from flask import Flask, jsonify, request
from libs.forum import Directory
import os

# port 5001
app = Flask(__name__)

directory = Directory("forum.db")

@app.route('/')
def serve_index():
    with open('web/index.html', 'r') as f:
        return f.read()

@app.route('/api/forums')
def get_forums():
    page = int(request.args.get('page', 0))
    search = request.args.get('search', '')
    
    if search:
        forums = directory.search_forums(search)
    else:
        forums = directory.get_forum_objects(limit=10, offset=page * 10)
    
    return jsonify([{
        'forum_id': forum.forum_id,
        'creator_id': forum.creator_id,
        'title': forum.title,
        'description': forum.description,
        'flags': forum.flags
    } for forum in forums])

@app.route('/api/posts')
def get_posts():
    page = int(request.args.get('page', 0))
    search = request.args.get('search', '')
    
    # For simplicity, we'll just get posts from all forums
    # You might want to add more sophisticated search/filter logic
    posts = []
    forums = directory.get_forum_objects()
    
    for forum in forums:
        forum_posts = directory.get_posts_by_forum(forum.forum_id, limit=10, offset=page * 10)
        if search:
            forum_posts = [post for post in forum_posts if search.lower() in post.content.lower()]
        posts.extend(forum_posts)
    
    # Sort by created_at and take only the requested page
    posts.sort(key=lambda x: x.created_at, reverse=True)
    start = page * 10
    end = start + 10
    
    # Get user names for all posts
    user_names = {}
    # Get forum titles for all posts
    forum_titles = {}
    for post in posts:
        if post.author_id not in user_names:
            user = directory.get_user_by_id(post.author_id)
            user_names[post.author_id] = user.name if user else "Anonymous"
        if post.forum_id not in forum_titles:
            forum = directory.get_forum_by_id(post.forum_id)
            forum_titles[post.forum_id] = forum.title if forum else "Unknown Forum"
    
    return jsonify([{
        'post_id': post.post_id,
        'forum_id': post.forum_id,
        'forum_title': forum_titles[post.forum_id],
        'author_id': post.author_id,
        'author_name': user_names[post.author_id],
        'content': post.content,
        'created_at': post.created_at.isoformat(),
        'title': post.title,
        'parent_id': post.parent_id,
        'files': post.files,
        'flags': post.flags
    } for post in posts[start:end]])

@app.route('/api/users')
def get_users():
    page = int(request.args.get('page', 0))
    search = request.args.get('search', '')
    
    if search:
        users = directory.search_users(search)
    else:
        users = directory.get_users(limit=10, offset=page * 10)
    
    return jsonify([{
        'user_id': user.user_id,
        'name': user.name,
        'persona': user.persona,
        'created_at': user.created_at.isoformat(),
        'subscribed_forums': user.subscribed_forums,
        'current_forums': user.current_forums
    } for user in users])

@app.route('/api/forum/<forum_id>')
def get_forum_details(forum_id):
    forum = directory.get_forum_by_id(forum_id)
    if not forum:
        return jsonify({"error": "Forum not found"}), 404
        
    posts = directory.get_posts_by_forum(forum_id)
    
    # Get user names for all posts
    user_names = {}
    for post in posts:
        if post.author_id not in user_names:
            user = directory.get_user_by_id(post.author_id)
            user_names[post.author_id] = user.name if user else "Anonymous"
    
    return jsonify({
        'forum_id': forum.forum_id,
        'creator_id': forum.creator_id,
        'title': forum.title,
        'description': forum.description,
        'flags': forum.flags,
        'posts': [{
            'post_id': post.post_id,
            'author_name': user_names[post.author_id],
            'content': post.content,
            'created_at': post.created_at.isoformat(),
            'title': post.title,
            'parent_id': post.parent_id,
            'files': post.files,
            'flags': post.flags
        } for post in posts]
    })

@app.route('/api/post/<post_id>')
def get_post_details(post_id):
    post = directory.get_post_by_id(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
        
    # Get the forum
    forum = directory.get_forum_by_id(post.forum_id)
    
    # Get the author's name
    author = directory.get_user_by_id(post.author_id)
    author_name = author.name if author else "Anonymous"
    
    # Get all replies to this post
    replies = [p for p in directory.get_posts_by_forum(post.forum_id) if p.parent_id == post_id]
    
    # Get user names for all replies
    user_names = {}
    for reply in replies:
        if reply.author_id not in user_names:
            user = directory.get_user_by_id(reply.author_id)
            user_names[reply.author_id] = user.name if user else "Anonymous"
    
    return jsonify({
        'post_id': post.post_id,
        'forum_id': post.forum_id,
        'forum_title': forum.title if forum else "Unknown Forum",
        'author_name': author_name,
        'content': post.content,
        'created_at': post.created_at.isoformat(),
        'title': post.title,
        'files': post.files,
        'flags': post.flags,
        'replies': [{
            'post_id': reply.post_id,
            'author_name': user_names[reply.author_id],
            'content': reply.content,
            'created_at': reply.created_at.isoformat(),
            'title': reply.title,
            'files': reply.files,
            'flags': reply.flags
        } for reply in replies]
    })

@app.route('/api/forum/<forum_id>/post', methods=['POST'])
def create_post():
    data = request.json
    forum_id = data.get('forum_id')
    content = data.get('content')
    title = data.get('title', '')
    parent_id = data.get('parent_id', None)
    
    if not content:
        return jsonify({"error": "Content is required"}), 400
        
    # Create post as ADMIN
    post = directory.create_post(
        forum_id=forum_id,
        author_id="ADMIN",
        content=content,
        title=title,
        parent_id=parent_id
    )
    
    return jsonify({
        'post_id': post.post_id,
        'forum_id': post.forum_id,
        'author_id': post.author_id,
        'content': post.content,
        'created_at': post.created_at.isoformat(),
        'title': post.title,
        'parent_id': post.parent_id,
        'files': post.files,
        'flags': post.flags
    })

@app.route('/api/post/<post_id>/reply', methods=['POST'])
def create_reply(post_id):
    data = request.json
    content = data.get('content')
    title = data.get('title', '')
    
    if not content:
        return jsonify({"error": "Content is required"}), 400
        
    # Get original post to get forum_id
    original_post = directory.get_post_by_id(post_id)
    if not original_post:
        return jsonify({"error": "Original post not found"}), 404
        
    # Create reply as ADMIN
    reply = directory.create_post(
        forum_id=original_post.forum_id,
        author_id="ADMIN",
        content=content,
        title=title,
        parent_id=post_id
    )
    
    return jsonify({
        'post_id': reply.post_id,
        'forum_id': reply.forum_id,
        'author_id': reply.author_id,
        'content': reply.content,
        'created_at': reply.created_at.isoformat(),
        'title': reply.title,
        'parent_id': reply.parent_id,
        'files': reply.files,
        'flags': reply.flags
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)