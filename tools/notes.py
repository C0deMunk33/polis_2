from pydantic import BaseModel, Field
from libs.common import ToolSchema, ToolsetDetails, ToolCall
from libs.agent import Agent

class Note(BaseModel):
    title: str = Field(description="The title of the note.")
    content: str = Field(description="The content of the note.")
    
class NotesManager:
    def __init__(self):
        self.notes = []

        names_of_tools_to_expose = [
            "add_note",
            "get_notes",
            "delete_note"
        ]

        self.tool_schemas = []
        for name in names_of_tools_to_expose:
            docstring = getattr(self, name).__doc__
            tool_schema = ToolSchema.model_validate_json(docstring)
            self.tool_schemas.append(tool_schema)
        

    def add_note(self, title: str, content: str):
        """
        {
            "toolset_id": "notes_manager",
            "name": "add_note",
            "description": "Add a note to the notes manager.",
            "arguments": [{"name": "title", "type": "str", "description": "The title of the note."}, {"name": "content", "type": "str", "description": "The content of the note."}]
        }
        """
        self.notes.append(Note(title=title, content=content))
        return f"Note {title} added"
    
    def get_notes(self):
        """
        {
            "toolset_id": "notes_manager",
            "name": "get_notes",
            "description": "Get all notes from the notes manager.",
            "arguments": []
        }
        """
        result = "Notes:\n"
        if len(self.notes) == 0:
            result += "    [No notes found]"
        else:
            for i, note in enumerate(self.notes):
                result += f"    [{i+1}] {note.title}\n{note.content}\n\n"
        return result
    
    def delete_note(self, index: int):
        """ 
        {
            "toolset_id": "notes_manager",
            "name": "delete_note",
            "description": "Delete a note from the notes manager.",
            "arguments": [{"name": "index", "type": "int", "description": "The index of the note."}]
        }
        """
        self.notes.pop(index)
        return f"Note {index} deleted"
    
    ############### Agent Interface ###############
    def get_toolset_details(self):
        return ToolsetDetails(
            toolset_id="notes_manager",
            name="Notes Manager",
            description="Manages notes"
        )
    
    def get_tool_schemas(self):
        return [tool_schema.model_dump_json() for tool_schema in self.tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.toolset_id != "notes_manager":
            raise ValueError(f"Toolset {tool_call.toolset_id} not found")

        if tool_call.name == "add_note":
            return self.add_note(tool_call.arguments["title"], tool_call.arguments["content"])
        elif tool_call.name == "get_notes":
            return self.get_notes()
        elif tool_call.name == "delete_note":
            return self.delete_note(tool_call.arguments["index"])