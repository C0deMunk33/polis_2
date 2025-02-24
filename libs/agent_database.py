from pydantic import BaseModel
import sqlite3

class AgentRunResultsTable(BaseModel):
    pass_id: str
    agent_id: str
    pass_number: int
    agent_run_result: str
    run_date: str

class AgentTable(BaseModel):
    agent_id: str
    agent_name: str
    pass_number: int
    last_run_date: str
    
class AgentDatabase:
    def __init__(self, database_path):
        self.database_path = database_path
        conn = sqlite3.connect(database_path)
        # create table from AgentRunResultsTable schema
        # create table
        conn.execute("CREATE TABLE IF NOT EXISTS agent_run_results (pass_id TEXT, agent_id TEXT, pass_number INTEGER, agent_run_result TEXT, run_date TEXT)")
        
        # Create agents table if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT UNIQUE, 
                agent_name TEXT, 
                pass_number INTEGER, 
                last_run_date TEXT
            )
        """)

        # create index on agent_id on both tables
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_id ON agent_run_results (agent_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_id ON agents (agent_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pass_number ON agents (pass_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_date ON agent_run_results (run_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_last_run_date ON agents (last_run_date)")
        conn.commit()
        conn.close()

    def get_agent_run_results(self, agent_id, limit=100, offset=0):
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute("""SELECT * FROM agent_run_results 
                        WHERE agent_run_results.agent_id = ? 
                        ORDER BY agent_run_results.pass_number DESC
                        LIMIT ? OFFSET ?""", (agent_id, limit, offset))
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_agent_list(self):
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        # Select all agents, ordered by agent_id
        cursor.execute("""
            SELECT * FROM agents 
            ORDER BY agent_id ASC
        """)
        results = cursor.fetchall()
        conn.close()
        return results
    
    def save_agent_run_result(self, agent_id, pass_id, pass_number, agent_run_result, run_date):
        conn = sqlite3.connect(self.database_path)
        conn.execute("INSERT INTO agent_run_results (agent_id, pass_id, pass_number, agent_run_result, run_date) VALUES (?, ?, ?, ?, ?)", (agent_id, pass_id, pass_number, agent_run_result, run_date))
        conn.commit()
        conn.close()

    def save_agent(self, agent_id, agent_name, pass_number, last_run_date):
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        # Use UPSERT syntax for cleaner handling of inserts/updates
        cursor.execute("""
            INSERT INTO agents (agent_id, agent_name, pass_number, last_run_date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(agent_id) 
            DO UPDATE SET
                agent_name = excluded.agent_name,
                pass_number = excluded.pass_number,
                last_run_date = excluded.last_run_date
        """, (agent_id, agent_name, pass_number, last_run_date))
        
        conn.commit()
        conn.close()
        
        