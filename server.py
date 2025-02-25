from flask import Flask, request, jsonify, send_from_directory
import os
import json
import uuid

from libs.agent_database import AgentDatabase, AgentTable, AgentRunResultsTable
from libs.agent import AgentRunResult
from tools.user_directory import UserDirectory

app = Flask(__name__)
app.static_folder = 'web'
app.static_url_path = '/static'

# Create the Directory instance pointing to our forum.db
forum_db_path = os.path.join(os.path.dirname(__file__), 'forum.db')
agent_db_path = os.path.join(os.path.dirname(__file__), 'agent_database.db')
user_directory_db_path = os.path.join(os.path.dirname(__file__), 'user_directory.db')

agent_database = AgentDatabase(agent_db_path)
user_directory = UserDirectory(user_directory_db_path)

# Create a dummy admin agent for messaging
class AdminAgent:
    def __init__(self):
        self.id = "admin"
        self.name = "Admin"

admin_agent = AdminAgent()
# Ensure admin user exists in the directory
user_directory.add_user(admin_agent)

@app.route('/')
def serve_app(agent_id=None):
    return send_from_directory('web', 'index.html')

@app.route('/messaging')
def serve_messaging():
    return send_from_directory('web', 'messaging.html')

@app.route('/api/list_agents', methods=['GET'])
def list_agents():
    agent_list = agent_database.get_agent_list()
    # Convert the list of tuples to list of dicts
    formatted_list = [{"agent_id": row[0], "agent_name": row[1], "pass_number": row[2], "last_run_date": row[3]} for row in agent_list]
    return jsonify(formatted_list)

@app.route('/api/get_agent_run_results', methods=['GET'])
def get_agent_run_results():
    agent_id = request.args.get('agent_id')
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))
    
    if not agent_id:
        return jsonify({"error": "agent_id parameter is required"}), 400
        
    agent_run_results = agent_database.get_agent_run_results(agent_id, limit, offset)
    
    # Convert the database rows to AgentRunResultsTable objects
    run_results_table_rows = [
        AgentRunResultsTable(
            pass_id=row[0], 
            agent_id=row[1], 
            pass_number=row[2], 
            agent_run_result=row[3], 
            run_date=row[4]
        ) for row in agent_run_results
    ]
    
    # Return the JSON strings directly
    return jsonify([row.agent_run_result for row in run_results_table_rows])

# New messaging endpoints
@app.route('/api/get_users', methods=['GET'])
def get_users():
    users_text = user_directory.get_users()
    # Parse the text output into a structured format
    users = []
    for line in users_text.split('\n')[1:]:  # Skip the "Users:" header
        line = line.strip()
        if line:
            # Extract name and user_id from the line
            parts = line.split('(user_id: ')
            if len(parts) == 2:
                name = parts[0].strip('- ').strip()
                user_id = parts[1].strip(')')
                users.append({"user_id": user_id, "name": name})
    
    return jsonify(users)

@app.route('/api/send_message', methods=['POST'])
def send_message():
    data = request.json
    recipient_id = data.get('recipient_id')
    message = data.get('message')
    
    if not recipient_id or not message:
        return jsonify({"error": "recipient_id and message are required"}), 400
    
    result = user_directory.send_message(admin_agent, recipient_id, message)
    return jsonify({"result": result})

@app.route('/api/get_messages', methods=['GET'])
def get_messages():
    sender_id = request.args.get('sender_id')
    limit = int(request.args.get('limit', 10))
    
    messages_text = user_directory.get_messages(admin_agent, sender_id, limit)
    
    # Parse the text output into a structured format
    messages = []
    for line in messages_text.split('\n')[1:]:  # Skip the "Messages:" header
        line = line.strip()
        if line and not line == "[No messages]":
            # Extract sender and message from the line
            parts = line.split(': ', 1)
            if len(parts) == 2:
                sender = parts[0].strip('- From ')
                message_content = parts[1]
                messages.append({"sender": sender, "message": message_content})
    
    return jsonify(messages)

@app.route('/api/get_new_messages', methods=['GET'])
def get_new_messages():
    messages_text = user_directory.get_new_messages(admin_agent)
    
    # Parse the text output into a structured format
    messages = []
    for line in messages_text.split('\n')[1:]:  # Skip the "Messages:" header
        line = line.strip()
        if line and not line == "[No messages]":
            # Extract sender and message from the line
            parts = line.split(': ', 1)
            if len(parts) == 2:
                sender = parts[0].strip('- From ')
                message_content = parts[1]
                messages.append({"sender": sender, "message": message_content})
    
    return jsonify(messages)

# Add a route to serve static files from web directory
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('web', path)

if __name__ == '__main__':
    # Run Flask in debug mode for local development
    app.run(debug=True, port=5001)
