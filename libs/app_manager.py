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
        self.pinned_app_ids = ["app_manager"] # these are the tools that are currently available to the agent, app manager is always pinned
        self.self_tool_schemas = []

        names_of_tools_to_expose = [
            "list_apps",
            "pin_app",
            "unpin_app",
            "get_pinned_apps",
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
            "description": "gets a list of all apps",
            "arguments": []
        }
        """
        result = "Available apps:\n"
        for app in self.apps.values():
            if app.toolset_id in self.pinned_app_ids:
                result += f"    [pinned] {app.toolset_id} - {app.name} - {app.description}\n"
            else:
                result += f"    {app.toolset_id} - {app.name} - {app.description}\n"
        return result
    
    def pin_app(self, app_id: str):
        """
        {
            "toolset_id": "app_manager",
            "name": "pin_app",
            "description": "pins an app, this makes their functions available to you.",
            "arguments": [{
                "name": "app_id",
                "type": "string",
                "description": "the id of the app to pin"
            }]
        }
        """
        if app_id not in self.apps:
            return f"App {app_id} not found"
        self.pinned_app_ids.append(app_id)
        return f"Pinned app {app_id} - {self.apps[app_id].name}"

    def unpin_app(self, app_id: str):
        """
        {
            "toolset_id": "app_manager",
            "name": "unpin_app",
            "description": "unpins an app.",
            "arguments": [{
                "name": "app_id",
                "type": "string",
                "description": "the id of the app to unpin"
            }]
        }
        """
        # cannot unpin the app manager
        if app_id == "app_manager":
            return "Cannot unpin the app manager"
        self.pinned_app_ids.remove(app_id)
        return f"Unpinned app {app_id}"

    def get_pinned_apps(self):
        """
        {
            "toolset_id": "app_manager",
            "name": "get_pinned_apps",
            "description": "gets details of currently pinned apps and their tools",
            "arguments": []
        }"""
        result = "Pinned Apps:\n"
        for app_id in self.pinned_app_ids:
            result += f"    App Name: {self.apps[app_id].name}\n"
            result += f"    - Toolset ID: {self.apps[app_id].toolset_id}\n"
            result += f"    - App Description: {self.apps[app_id].description}\n"
            result +=  "    - Tools:\n"
            for schema in self.schemas[app_id]:
                tool_schema = ToolSchema.model_validate_json(schema)
                arg_string = ""
                # arguments is a list of dictionaries
                result += f"        toolset_id='{tool_schema.toolset_id}' name='{tool_schema.name}' description='{tool_schema.description}' arguments='{tool_schema.arguments}'\n"
               
        return result
    
    ############### Agent Interface ###############
    def get_toolset_details(self):
        return ToolsetDetails(
            toolset_id="app_manager",
            name="App Manager",
            description="Manages apps"
        )
    
    def get_tool_schemas(self):
        return [tool_schema.model_dump_json() for tool_schema in self.self_tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.toolset_id != "app_manager":
            return f"Tool {tool_call.name} not found"
        if tool_call.name == "list_apps":
            return self.list_apps()
        elif tool_call.name == "pin_app":
            return self.pin_app(tool_call.arguments["app_id"])
        elif tool_call.name == "unpin_app":
            return self.unpin_app(tool_call.arguments["app_id"])
        elif tool_call.name == "get_pinned_apps":
            return self.get_pinned_apps()
        else:
            return f"Tool {tool_call.name} not found"