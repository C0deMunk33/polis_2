from libs.agent import Agent
from libs.common import ToolCall, ToolsetDetails, Message
from libs.app_manager import AppManager
from typing import List, Callable

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

    def run(self, tool_callback: Callable, app_managers: List[AppManager]):
        while self.running:
            for agent in self.agents:
                print("~"*100)
                print(f"Running agent: {agent.name} \n")

                post_system_messages = []
                # make assistant messages for loaded apps
                agent_app_manager = app_managers[agent.id]
                get_loaded_apps_tool_call = ToolCall(
                    toolset_id="app_manager",
                    name="get_loaded_apps",
                    arguments={}
                )
                get_loaded_apps_tool_call_result = agent_app_manager.agent_tool_callback(agent, get_loaded_apps_tool_call)
                
                post_system_messages.append(Message(role="assistant", tool_calls=[get_loaded_apps_tool_call]))
                post_system_messages.append(Message(role="tool", content=get_loaded_apps_tool_call_result))

                agent.run(self.server_url, self.model, post_system_messages, tool_callback)

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
    
    ############### Agent Interface ###############
    def get_toolset_details(self):
        return ToolsetDetails(
            toolset_id="agent_tool",
            name="Agent Orchestrator",
            description="Orchestrates agents"
        )

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
        }]
        return tool_schemas
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.name == "set_name":
            agent.name = tool_call.arguments["name"]
            return f"Name set to {tool_call.arguments['name']}"

def main():
    from tools.forum import Directory
    from tools.code_isolation import SafeCodeExecutor
    from tools.quest_manager import QuestManager
    from tools.wikisearch import WikiSearch
    from libs.common import MultiWriter
    from tools.file_manager import FileManager
    from tools.persona import PersonaManager
    from tools.notes import NotesManager
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
    persona_managers = {}
    app_managers = {}
    notes_managers = {}
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
                tool_results = shared_code_runner.agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "wiki_toolset":
                tool_results = wiki_search.agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "quest_manager":
                tool_results = quest_managers[agent.id].agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "app_manager":
                tool_results = app_managers[agent.id].agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "file_manager":
                tool_results = file_manager.agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "persona":
                tool_results = persona_managers[agent.id].agent_tool_callback(agent, tool_call)
            elif tool_call.toolset_id == "notes_manager":
                tool_results = notes_managers[agent.id].agent_tool_callback(agent, tool_call)
            else:
                print(f"APP NOT FOUND - toolset_id: {tool_call.toolset_id} not found")
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

    # create initial quest

    #orchestrator_quest_manager = QuestManager() # create quest manager for this orchestrator
    overall_goal = "research Monty Python as a group, and their impact on comedy and culture as both a troupe and as individual members. I would like a detailed report on the impact of Monty Python on comedy and culture."
    details = """
    Wikepedia has a lot of information about Monty Python, and their individual members. They were super popular, so I am wondering what their larger impact on comedy and culture was.
    """
    context = "you have tools available to you to help you complete the quest"
    
    #print("Creating initial quest...")
    #quest = orchestrator_quest_manager.create_quest(orchestrator.server_url, overall_goal, context, details)
    #print(f"Initial quest created: {quest.model_dump_json(indent=4)}")
    #orchestrator_quest_manager.set_current_quest(quest.title)

    shared_file_directory = "shared_files"
    if os.path.exists(shared_file_directory):
        shutil.rmtree(shared_file_directory)
    os.makedirs(shared_file_directory)

    shared_code_runner = SafeCodeExecutor(allowed_directory=shared_file_directory, debug=False)
    file_manager = FileManager(shared_file_directory)

   
    for i in range(10): 
        
        standing_tool_calls = [
            ToolCall(
                toolset_id="persona",
                name="get_current_persona",
                arguments={}
            ),
            ToolCall(
                toolset_id="notes_manager",
                name="get_notes",
                arguments={}
            ),
            ToolCall(
                toolset_id="quest_manager",
                name="get_quest_list",
                arguments={}
            ),
            ToolCall(
                toolset_id="quest_manager",
                name="get_current_quest",
                arguments={}
            ),
            ToolCall(
                toolset_id="app_manager",
                name="list_apps",
                arguments={}
            )
        ]

        agent = Agent(  default_llm_url=orchestrator.server_url,
                        name=f"agent{i}", 
                        private_key=f"{i}asdasdasdasd", 
                        initial_instructions="This is the beginning of your journey. You can use any tools available to you.", 
                        initial_notes=[],
                        standing_tool_calls=standing_tool_calls)
        
        app_manager = AppManager()


        persona_manager = PersonaManager()
        persona_managers[agent.id] = persona_manager

        notes_manager = NotesManager()
        notes_managers[agent.id] = notes_manager

        quest_manager = QuestManager()
        quest_managers[agent.id] = quest_manager


        app_manager.add_app(persona_manager.get_toolset_details(), persona_manager.get_tool_schemas())
        app_manager.add_app(orchestrator.get_toolset_details(), orchestrator.get_tool_schemas())
        app_manager.add_app(shared_code_runner.get_toolset_details(), shared_code_runner.get_tool_schemas())
        app_manager.add_app(quest_manager.get_toolset_details(), quest_manager.get_tool_schemas())
        app_manager.load_app(quest_manager.get_toolset_details().toolset_id)
        app_manager.add_app(wiki_search.get_toolset_details(), wiki_search.get_tool_schemas())
        app_manager.add_app(forum_directory.get_toolset_details(), forum_directory.get_tool_schemas())
        app_manager.add_app(file_manager.get_toolset_details(), file_manager.get_tool_schemas())
        app_manager.add_app(notes_manager.get_toolset_details(), notes_manager.get_tool_schemas())
        app_manager.load_app(notes_manager.get_toolset_details().toolset_id)
        app_managers[agent.id] = app_manager
        orchestrator.add_agent(agent)




    orchestrator.run(tool_callback=tool_callback, app_managers=app_managers)

if __name__ == "__main__":
    main()
