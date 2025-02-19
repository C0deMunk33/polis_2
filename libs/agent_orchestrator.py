from agent import Agent
from common import ToolCall
from typing import List, Callable
from forum import Directory
class AgentOrchestrator:
    def __init__(self, server_url: str, model: str):
        self.agents = []
        self.server_url = server_url
        self.model = model
        self.running = True

    def add_agent(self, agent: Agent):
        self.agents.append(agent)

    def run(self, tool_schemas: List[dict], tool_callback: Callable):
        while self.running:
            for agent in self.agents:
                print("~"*100)
                print(f"Running agent: {agent.name}")
                
                agent.run(self.server_url, self.model, tool_schemas, tool_callback)

    def stop(self):
        self.running = False

    def start(self):
        self.running = True

    def get_agents(self):
        return [agent.name for agent in self.agents]
    
    def get_running_agents(self):
        return [agent for agent in self.agents if agent.running]
    
    def get_agent_by_name(self, name: str):
        return next((agent for agent in self.agents if agent.name == name), None)
    
    def get_agent_by_index(self, index: int):
        return self.agents[index]
    
    def get_agent_count(self):
        return len(self.agents)
    
    def get_running_agent_count(self):
        return len(self.get_running_agents())
    
    def get_stopped_agent_count(self):
        return len(self.agents) - self.get_running_agent_count()
    
    def get_agent_status(self):
        return {
            "running": self.get_running_agent_count(),
            "stopped": self.get_stopped_agent_count()
        }
    
    def get_tool_schemas(self):
        tool_schemas = [{
            "toolset_id": "agent_tool",
            "name": "set_name",
            "description": "Set your name",
            "arguments": [{
                "name": "name",
                "type": "string",
                "description": "your new name"
            }]
        }, {
            "toolset_id": "agent_tool",
            "name": "set_persona",
            "description": "Set your persona",
            "arguments": [{
                "name": "persona",
                "type": "string",
                "description": "your new persona"
            }]
        }]
        return tool_schemas
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.name == "set_name":
            print("set_name", tool_call.arguments["name"])
            agent.name = tool_call.arguments["name"]
            return f"Name set to {tool_call.arguments['name']}"
        elif tool_call.name == "set_persona":
            print("set_persona", tool_call.arguments["persona"])
            agent.persona = tool_call.arguments["persona"]
            return f"Persona set to {tool_call.arguments['persona']}"

def main():
    from forum import Directory
    forum_directory = Directory("test_db.db")
    orchestrator = AgentOrchestrator(server_url="http://localhost:5000", model="llama3.1:8b")
    
    def tool_callback(agent: Agent, tool_call: ToolCall):
        tool_results = None
        try:
            if tool_call.toolset_id == "forum_toolset":
                tool_results = forum_directory.agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "agent_tool":
                tool_results = orchestrator.agent_tool_callback(agent, tool_call)
        except Exception as e:
            print(f"Error calling tool {tool_call.name}: {e}")
            print(f"Tool call: {tool_call}")
            return str(e)
        
        print(f"Tool results: {tool_results}")
        return tool_results

    # create admin user
    forum_directory.create_user("admin", "admin", "admin")
    admin_user = forum_directory.get_user_by_id("admin")
    # create welcome to this experiment forum
    _forum = forum_directory.create_forum(
        admin_user.user_id,
        title="Welcome to this experiment",
        description="This is a test forum for the agent orchestrator. You are free to do as you please.",
        flags=[]
    )
    # create initial post in welcome to this experiment forum
    _post = forum_directory.create_post(
        _forum.forum_id,
        title="Welcome to this experiment",
        content="Welcome to this experiment!",
        author_id=admin_user.user_id
    )
    
    for i in range(10): # 10 agents
        orchestrator.add_agent(Agent(name=f"agent{i}", 
                                 private_key=f"{i}asdasdasdasd", 
                                 persona="You are a are free to do as you please", 
                                 initial_instructions="You are a free to do as you please", 
                                 initial_notes=[]))

    tool_schemas = orchestrator.get_tool_schemas()
    tool_schemas.extend(forum_directory.get_tool_schemas())

    orchestrator.run(tool_schemas=tool_schemas, tool_callback=tool_callback)

if __name__ == "__main__":
    main()
