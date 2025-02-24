from flask import Flask, request, jsonify, send_from_directory
import os
import json

from libs.agent_database import AgentDatabase, AgentTable, AgentRunResultsTable
from libs.agent import AgentRunResult

app = Flask(__name__)
app.static_folder = 'web'
app.static_url_path = '/static'

# Create the Directory instance pointing to our forum.db
forum_db_path = os.path.join(os.path.dirname(__file__), 'forum.db')
agent_db_path = os.path.join(os.path.dirname(__file__), 'agent_database.db')


agent_database = AgentDatabase(agent_db_path)

@app.route('/')
def serve_app(agent_id=None):
    return send_from_directory('web', 'index.html')

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


# Add a route to serve static files from web directory
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('web', path)

if __name__ == '__main__':
    # Run Flask in debug mode for local development
    app.run(debug=True, port=5001)
