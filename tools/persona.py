from pydantic import BaseModel, Field
from typing import List
from libs.common import call_ollama_chat, Message, ToolSchema, ToolsetDetails, ToolCall
from libs.agent import Agent

class Persona(BaseModel):
    name: str = Field(description="The name of the persona.")
    description: str = Field(description="A description of the persona.")
    goals: List[str] = Field(description="A list of goals for the persona.")
    backstory: str = Field(description="A backstory for the persona.")
    personality: str = Field(description="A personality for the persona.")

class PersonaManager:
    def __init__(self):
        self.personas = {}
        self.current_persona_index = None
        self.persona_submissions = []
        names_of_tools_to_expose = [
            "get_persona_list",
            "create_persona",
            "get_persona",
            "remove_persona",
            "get_current_persona",
            "set_current_persona",
        ]

        self.tool_schemas = []
        for name in names_of_tools_to_expose:
            docstring = getattr(self, name).__doc__
            tool_schema = ToolSchema.model_validate_json(docstring)
            self.tool_schemas.append(tool_schema)
    
    def get_persona_list(self):
        """
        {
            "toolset_id": "persona",
            "name": "get_persona_list",
            "description": "Get an indexed list of all personas",
            "arguments": []
        }
        """
        result = "Personas:\n"
        for index, name in enumerate(self.personas.keys()):
            result += f"{index}: {name} - {self.personas[name].description}\n"
        return result
    
    def create_persona(self, llm_url: str, model: str, description: str = None, name: str = None):
        """
        {
            "toolset_id": "persona",
            "name": "create_persona",
            "description": "Create a persona",
            "arguments": [
                {"name": "description", "type": "str", "description": "The description of the persona (optional)"},
                {"name": "name", "type": "str", "description": "The name of the persona (optional)"}
            ]
        }
        """
        if description is None:
            description = "[No Description Provided, please create a persona based on the name or, if no name is provided, create a random persona]"
        if name is None:
            name = "[No Name Provided]"
        persona_creation_system_prompt = """
        You are a persona creation expert. You will be given a description of a persona and optional name and you will need to create a persona.
        """
        persona_creation_user_prompt = rf"""
Please create a persona based on the following description:
    Description: {description}
    Name: {name}

Respond in the following JSON format:
{Persona.model_json_schema()}
"""
        messages = [
            Message(role="system", content=persona_creation_system_prompt),
            Message(role="user", content=persona_creation_user_prompt)
        ]
        persona_output = call_ollama_chat(llm_url, model, messages, json_schema=Persona.model_json_schema())
        persona = Persona.model_validate_json(persona_output)
        self.personas[name] = persona
        return f"Persona {name} created: \n{persona}"
    
    def get_persona(self, index: int):
        """
        {
            "toolset_id": "persona",
            "name": "get_persona_by_index",
            "description": "Get a persona by index",
            "arguments": [
                {"name": "index", "type": "int", "description": "The index of the persona"}
            ]
        }
        """
        if index not in self.personas:
            return f"Persona with index {index} not found"
        persona_string = f"Persona {self.personas[index].name}:\n"
        persona_string += f"    Description: {self.personas[index].description}\n"
        persona_string += f"    Goals: {self.personas[index].goals}\n"
        persona_string += f"    Backstory: {self.personas[index].backstory}\n"
        persona_string += f"    Personality: {self.personas[index].personality}\n"
        return persona_string
    
    def remove_persona(self, index: int):
        """
        {
            "toolset_id": "persona",
            "name": "remove_persona",
            "description": "Remove a persona by index",
            "arguments": [
                {"name": "index", "type": "int", "description": "The index of the persona"}
            ]
        }
        """
        if index not in self.personas:
            return f"Persona with index {index} not found"
        del self.personas[index]
        return f"Persona with index {index} removed"
    
    def get_current_persona(self):
        """
        {
            "toolset_id": "persona",
            "name": "get_current_persona",
            "description": "Get the current persona",
            "arguments": []
        }
        """
        if self.current_persona_index is None:
            return "No current persona"
        return self.get_persona(self.current_persona_index)

    def set_current_persona(self, index: int):
        """
        {
            "toolset_id": "persona",
            "name": "set_current_persona",
            "description": "Set the current persona",
            "arguments": [
                {"name": "index", "type": "int", "description": "The index of the persona"}
            ]
        }
        """
        if index not in self.personas:
            return f"Persona with index {index} not found"
        self.current_persona_index = index
        return f"Current persona set to {self.personas[index].name}"
    
    ############### Agent Interface ###############
    def get_toolset_details(self):
        return ToolsetDetails(
            toolset_id="persona",
            name="Persona",
            description="Manage personas"
        )
    
    def get_tool_schemas(self):
        return [tool_schema.model_dump_json() for tool_schema in self.tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.toolset_id != "persona":
            raise ValueError(f"Toolset {tool_call.toolset_id} not found")

        if tool_call.name == "get_persona_list":
            return self.get_persona_list()
        elif tool_call.name == "create_persona":
            return self.create_persona(agent.default_llm_url, agent.model, tool_call.arguments["description"], tool_call.arguments["name"])
        elif tool_call.name == "get_persona":
            return self.get_persona(tool_call.arguments["index"])
        elif tool_call.name == "remove_persona":
            return self.remove_persona(tool_call.arguments["index"])
        elif tool_call.name == "get_current_persona":
            return self.get_current_persona()
        elif tool_call.name == "set_current_persona":
            return self.set_current_persona(tool_call.arguments["index"])
        else:
            raise ValueError(f"Tool {tool_call.name} not found")
