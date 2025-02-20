from agent import Agent
from common import ToolCall
from typing import List, Callable
from forum import Directory
import os
import shutil
import traceback
import sys
#supress unclosed socket warnings
import warnings
import io

warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)


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
                print(f"Running agent: {agent.name} \n")
                
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
            agent.name = tool_call.arguments["name"]
            return f"Name set to {tool_call.arguments['name']}"
        elif tool_call.name == "set_persona":
            agent.persona = tool_call.arguments["persona"]
            return f"Persona set to {tool_call.arguments['persona']}"

def main():
    from forum import Directory
    from code_isolation import SafeCodeExecutor

    from quest_manager import QuestManager
    from wikisearch import WikiSearch
    from common import MultiWriter
    # delete out files if they exist
    if os.path.exists("std_out.txt"):
        os.remove("std_out.txt")
    if os.path.exists("std_err.txt"):
        os.remove("std_err.txt")

    # Open the files
    std_out_file = open("std_out.txt", "w", encoding="utf-8")
    std_err_file = open("std_err.txt", "w", encoding="utf-8")

    # Create writers that write to both console and file
    stdout_writer = MultiWriter(sys.stdout, std_out_file)
    stderr_writer = MultiWriter(sys.stderr, std_err_file)

    # Save original stdout/stderr for restoration if needed
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Redirect stdout and stderr
    sys.stdout = stdout_writer
    sys.stderr = stderr_writer


    forum_directory = Directory("forum.db")
    code_environments = {}
    quest_managers = {}
    orchestrator = AgentOrchestrator(server_url="http://localhost:5000", model="llama3.1:8b")
    wiki_search = WikiSearch()
    def tool_callback(agent: Agent, tool_call: ToolCall):
        tool_results = None
        print(f"  - {tool_call.toolset_id} - Tool call: {tool_call}")
        try:
            if tool_call.toolset_id == "forum_toolset":
                tool_results = forum_directory.agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "agent_tool":
                tool_results = orchestrator.agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "code_runner":
                tool_results = code_environments[agent.id].agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "wiki_toolset":
                tool_results = wiki_search.agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "quest_manager":
                tool_results = quest_managers[agent.id].agent_tool_callback(agent, tool_call)
        except Exception as e:
            print("########################ERROR CALLING TOOL########################")
            print(f"Error calling tool {tool_call.name}: {e}")
            print(f"Tool call: {tool_call}")
            print()
            print(traceback.format_exc())
            return str(e)
        
        #print(f"Tool results: {tool_results}")
        return tool_results
    
    #check if admin exists
    if not forum_directory.get_user_by_id("admin"):
        # create admin user
        forum_directory.create_user("admin", "admin", "admin")
        admin_user = forum_directory.get_user_by_id("admin")
        # create welcome to this experiment forum
        _forum = forum_directory.create_forum(
            admin_user.user_id,
            title="Welcome to this experiment",
            description="This whole interface is an experiment with agentic agents and agency in general. You are free to do as you please. Make it fun.",
            flags=[]
        )
        # create initial post in welcome to this experiment forum
        _post = forum_directory.create_post(
            _forum.forum_id,
            title="Welcome to this experiment",
            content="Welcome to this experiment! Please explore what you are able to do. You can also use the forum to discuss what you are able to do.",
            author_id=admin_user.user_id
        )
    
    # create empty code environments directory, erase if exists
    code_environments_directory = "code_environments"
    if os.path.exists(code_environments_directory):
        shutil.rmtree(code_environments_directory)

    os.makedirs(code_environments_directory)
    
    # create initial quest

    orchestrator_quest_manager = QuestManager() # create quest manager for this orchestrator
    overall_goal = "research Monty Python as a group, and their impact on comedy and culture as both a troupe and as individual members. I would like a detailed report on the impact of Monty Python on comedy and culture."
    details = """
    Wikepedia has a lot of information about Monty Python, and their individual members. They were super popular, so I am wondering what their larger impact on comedy and culture was.
    """
    context = "you have tools available to you to help you complete the quest"
    
    print("Creating initial quest...")
    quest = orchestrator_quest_manager.create_quest(orchestrator.server_url, overall_goal, context, details)
    print(f"Initial quest created: {quest.model_dump_json(indent=4)}")

    for i in range(4): 
        
        standing_tool_calls = [
            ToolCall(
                toolset_id="quest_manager",
                name="get_quest_list",
                arguments={}
            ),
            ToolCall(
                toolset_id="forum_toolset",
                name="get_forums",
                arguments={}
            ),
            ToolCall(
                toolset_id="forum_toolset",
                name="get_subscribed_forums",
                arguments={}
            ),
            ToolCall(
                toolset_id="forum_toolset",
                name="get_current_forums",
                arguments={}
            )
        ]

        agent = Agent(  default_llm_url=orchestrator.server_url,
                        name=f"agent{i}", 
                        private_key=f"{i}asdasdasdasd", 
                        persona="Default persona (please change): You are a are free to do as you please. you can use any tools available to you. Note that you do have an active quest, so you should try to complete it.", 
                        initial_instructions="You are a free to do as you please", 
                        initial_notes=[],
                        standing_tool_calls=standing_tool_calls)
        # create code environment directory
        code_environment_directory = f"{code_environments_directory}/code_environment_{agent.id}"
        if not os.path.exists(code_environment_directory):
            os.makedirs(code_environment_directory)
        code_executor = SafeCodeExecutor(allowed_directory=code_environment_directory, debug=False)
        code_environments[agent.id] = code_executor

        quest_manager = QuestManager()
        # add copy of quest to quest manager
        quest_manager.add_quest(quest.model_copy())
        quest_manager.set_current_quest(quest.title)
        quest_managers[agent.id] = quest_manager

        orchestrator.add_agent(agent)


    tool_schemas = orchestrator.get_tool_schemas()
    forum_schemas = forum_directory.get_tool_schemas()
    tool_schemas.extend(forum_schemas)    
    agent = orchestrator.get_agent_by_index(0)
    code_env_schemas = code_environments[agent.id].get_tool_schemas()
    #tool_schemas.extend(code_env_schemas)
    wiki_schemas = WikiSearch().get_tool_schemas()
    tool_schemas.extend(wiki_schemas)
    quest_schemas = orchestrator_quest_manager.get_tool_schemas()
    tool_schemas.extend(quest_schemas)

    orchestrator.run(tool_schemas=tool_schemas, tool_callback=tool_callback)

if __name__ == "__main__":
    main()
