try:
    from .common import ToolSchema, ToolCall, ToolsetDetails
    from .agent import Agent
except ImportError:
    from common import ToolSchema, ToolCall, ToolsetDetails
    from agent import Agent

from typing import List

class AppManager:
    def __init__(self):
        self.apps = {}
        self.schemas = {}
        self.loaded_app_ids = ["app_manager"] # these are the tools that are currently available to the agent, app manager is always loaded
        self.self_tool_schemas = []

        names_of_tools_to_expose = [
            "load_app",
            "unload_app"
        ]

        for name in names_of_tools_to_expose:
            docstring = getattr(self, name).__doc__
            tool_schema = ToolSchema.model_validate_json(docstring)
            self.self_tool_schemas.append(tool_schema)

        self.add_app(self.get_toolset_details(), self.get_tool_schemas())

    def add_app(self, app: ToolsetDetails, tool_schemas: List[ToolSchema]):
        self.apps[app.toolset_id] = app
        self.schemas[app.toolset_id] = tool_schemas

    def remove_app(self, app_id: str):
        self.apps.pop(app_id)
        self.schemas.pop(app_id)

    def list_apps(self):
        """
        {
            "toolset_id": "app_manager",
            "name": "list_apps",
            "description": "gets a list of all apps, you can only call tools from loaded apps",
            "arguments": []
        }
        """
        result = "Available apps:\n"
        # sort apps by loaded status
        loaded_apps = []
        unloaded_apps = []
        for app in self.apps.values():
            if app.toolset_id in self.loaded_app_ids:
                loaded_apps.append(app)
            else:
                unloaded_apps.append(app)
        loaded_apps.sort(key=lambda x: x.name)
        unloaded_apps.sort(key=lambda x: x.name)
        for app in loaded_apps:
            result += f"    [loaded] {app.toolset_id} - {app.name} - {app.description}\n"
        for app in unloaded_apps:
            result += f"    [unloaded] {app.toolset_id} - {app.name} - {app.description}\n"

        result += "\nApp Manager Tools:\n"
        for tool_schema in self.self_tool_schemas:
            result += f"  (toolset_id: {tool_schema.toolset_id}) {tool_schema.name}({",".join([arg['name'] for arg in tool_schema.arguments])}) - description: {tool_schema.description}\n"
        print(result)
        return result
    
    def load_app(self, app_id: str):
        """
        {
            "toolset_id": "app_manager",
            "name": "load_app",
            "description": "loads an app, this makes their tools available to you to call.",
            "arguments": [{
                "name": "app_id",
                "type": "string",
                "description": "the toolset_id of the app to load"
            }]
        }
        """
        if app_id not in self.apps:
            return f"App {app_id} not found"
        self.loaded_app_ids.append(app_id)
        result = f"Loaded app {app_id} - {self.apps[app_id].name}\n{self.get_app_tool_list(app_id)}"
        return result

    def unload_app(self, app_id: str):
        """
        {
            "toolset_id": "app_manager",
            "name": "unload_app",
            "description": "unloads an app.",
            "arguments": [{
                "name": "app_id",
                "type": "string",
                "description": "the id of the app to unload"
            }]
        }
        """
        # cannot unload the app manager
        if app_id == "app_manager":
            return "Cannot unload the app manager"
        if app_id not in self.loaded_app_ids:
            return f"App {app_id} is not loaded"
        self.loaded_app_ids.remove(app_id)
        return f"Unloaded app {app_id}"

    def get_app_tool_list(self, app_id: str):
        """
        {
            "toolset_id": "app_manager",
            "name": "get_app_tool_list",
            "description": "gets a list of all tools available for an app",
            "arguments": [{
                "name": "app_id",
                "type": "string",
                "description": "the id of the app to get the tool list for"
            }]
        }
        """
        result = "Available Tools:\n"
        for schema in self.schemas[app_id]:
            tool_schema = ToolSchema.model_validate_json(schema)
            result += f"        toolset_id='{tool_schema.toolset_id}' name='{tool_schema.name}' description='{tool_schema.description}' arguments='{tool_schema.arguments}'\n"
        return result

    def get_loaded_apps(self):
        """
        {
            "toolset_id": "app_manager",
            "name": "get_loaded_apps",
            "description": "gets details of currently loaded apps and their tools",
            "arguments": []
        }"""
        result = "Available Tools:\n"
        result += "(note: these are the only tools available to you at this time)\n"
        for app_id in self.loaded_app_ids:
            for schema in self.schemas[app_id]:
                tool_schema = ToolSchema.model_validate_json(schema)
                # arguments is a list of dictionaries
                result += f"        toolset_id='{tool_schema.toolset_id}' name='{tool_schema.name}' description='{tool_schema.description}' arguments='{tool_schema.arguments}'\n"
               
        return result
    
    ############### Agent Interface ###############
    def get_toolset_details(self):
        return ToolsetDetails(
            toolset_id="app_manager",
            name="App Manager",
            description="Manages apps. Tools available are from loaded apps. An app must be loaded to be used."
        )
    
    def get_tool_schemas(self):
        return [tool_schema.model_dump_json() for tool_schema in self.self_tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.toolset_id != "app_manager":
            return f"Tool {tool_call.name} not found"
        if tool_call.name == "list_apps":
            return self.list_apps()
        elif tool_call.name == "load_app":
            #if app_name, use that as the app_id
            if "app_name" in tool_call.arguments:
                app_id = tool_call.arguments["app_name"]
            else:
                app_id = tool_call.arguments["app_id"]
            return self.load_app(app_id)
        elif tool_call.name == "unload_app":
            return self.unload_app(tool_call.arguments["app_id"])
        elif tool_call.name == "get_loaded_apps":
            return self.get_loaded_apps()
        elif tool_call.name == "get_app_tool_list":
            if "app_name" in tool_call.arguments:
                app_id = tool_call.arguments["app_name"]
            else:
                app_id = tool_call.arguments["app_id"]
            return self.get_app_tool_list(app_id)
        else:
            return f"Tool {tool_call.name} not found"