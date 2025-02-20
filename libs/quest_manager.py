from pydantic import BaseModel, Field
from typing import Dict, List
try:
    from .common import call_ollama_chat, Message, apply_unified_diff, ToolSchema, ToolCall
    from .agent import Agent
except ImportError:
    from common import call_ollama_chat, Message, apply_unified_diff, ToolSchema, ToolCall
    from agent import Agent

# TODO: figure out why these keep happening, looks like it's the new version of ollama
import warnings
warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)

class QuestStep(BaseModel):
    title: str = Field(description="The title of the step.")
    description: str = Field(description="A description of the step.")
    notes: List[str] = Field(description="A list of notes about the step.")
    completion_criteria: str = Field(description="A description of the criteria for completing the step.")  

class QuestGenerationOutput(BaseModel):
    thoughts: str = Field(description="A place to gather thoughts about the quest.")
    outline_of_approach: str = Field(description="A your overall initial approach to the quest.")
    thoughts_on_approach: str = Field(description="A place to gather thoughts about initial approach")
    quest_outline: List[str] = Field(description="A detailed outline of the quest.")
    quest_details: str = Field(description="A detailed description of the quest.")
    title: str = Field(description="The title of the quest.")
    description: str = Field(description="A description of the quest.")
    overall_goal: str = Field(description="The overall goal of the quest.")
    steps: List[QuestStep] = Field(description="An ordered list of steps that are designed to be completed in a specific order to complete the quest.")

class QuestFile(BaseModel):
    file_name: str = Field(description="The name of the file.")
    file_content: str = Field(description="The content of the file.")
    file_description: str = Field(description="A description of the file.")
    notes: List[str] = Field(description="A list of notes about the file.")

class Quest(BaseModel):
    quest_outline: List[str] = Field(description="A detailed outline of the quest.")
    quest_details: str = Field(description="A detailed description of the quest.")
    status: str = Field(description="The status of the quest.")
    title: str = Field(description="The title of the quest.")
    description: str = Field(description="A description of the quest.")
    overall_goal: str = Field(description="The overall goal of the quest.")
    current_step: str = Field(description="The title of the current step of the quest.")
    steps: List[QuestStep] = Field(description="An ordered list of steps that are designed to be completed in a specific order to complete the quest. Leave out step numbers as these can be adjusted.")
    files: List[QuestFile] = Field(description="A list of files that are associated with the quest.")

class QuestSubmission(BaseModel):
    quest_title: str = Field(description="The title of the quest.")
    submission_notes: str = Field(description="The notes for the submission.")

class QuestReview(BaseModel):
    quest_title: str = Field(description="The title of the quest.")
    review_notes: str = Field(description="The notes for the review.")
    accepted: bool = Field(description="Whether the quest was accepted.")

class QuestManager:
    def __init__(self):
        self.quests = {}
        self.current_quest_name = None
        self.quest_files = {}
        self.quest_submissions = []
        names_of_tools_to_expose = [
            "get_quest_list",
            "create_quest",
            "create_quest_file",
            "get_quest_file_details",
            "get_quest_file_content",
            "add_quest_file_note",
            "update_quest_file_description",
            "delete_quest_file_note",
            "update_quest_file_content",
            "get_quest",
            "get_quest_step",
            "get_current_quest",
            "get_current_quest_step",
            "add_quest_step_note",
            "insert_quest_step",
            "update_quest_step_description",
            "update_quest_step_completion_criteria",
            "delete_quest_step",
            "delete_quest_step_note",
            "set_current_quest",
            "set_current_quest_step",
            "submit_quest_for_review",
            "abandon_quest"
        ]

        self.tool_schemas = []
        for name in names_of_tools_to_expose:
            docstring = getattr(self, name).__doc__
            tool_schema = ToolSchema.model_validate_json(docstring)
            self.tool_schemas.append(tool_schema)

    def get_quest_by_title(self, title: str):
        """This is for the orchestator, do not expose"""
        return self.quests[title]
    
    def add_quest(self, quest: Quest):
        """This is for the orchestator, do not expose"""
        self.quests[quest.title] = quest

    def get_quest_list(self):
        """{
            "toolset_id": "quest_manager",
            "name": "get_quest_list",
            "description": "Get the list of active quests.",
            "arguments": []
        }"""
        # get quests where status is not "abandoned" or "submitted for review"
        result = "Quest List:\n"
        if len(self.quests) == 0:
            result += "No quests found"
        else:
            for quest in self.quests.values():
                if quest.status not in ["abandoned", "submitted for review"]:
                    if quest.title == self.current_quest_name:
                        result += f"[current] {quest.title}\n"
                    else:
                        result += f"{quest.title}\n"
        return result

    def create_quest(self, llm_url: str, overall_goal: str, context: str, details: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "create_quest", 
            "description": "Create a quest based on the provided information.",
            "arguments": [
                {
                    "name": "overall_goal",
                    "type": "str",
                    "description": "The overall goal of the quest."
                },
                {
                    "name": "details",
                    "type": "str",
                    "description": "The details of the quest."  
                },
                {
                    "name": "context",
                    "type": "str",
                    "description": "The context of the quest."
                }]
        }
        """
        quest_system_prompt = f"""You are a tasked with creating a quest based on the provided information. A quest is a collection of steps that are designed to be completed in a specific order to complete a larger goal."""

        user_prompt = f"""
Create a quest based on the following information:

Overall Goal: {overall_goal}

Details:
{details}

Context:
{context}

Please respond with JSON in the following format:
{Quest.model_json_schema()}
        """

        messages = [Message(role="system", content=quest_system_prompt), Message(role="user", content=user_prompt)]

        response = call_ollama_chat(llm_url, "a_model", messages, json_schema=QuestGenerationOutput.model_json_schema())
        quest_generation_output = QuestGenerationOutput.model_validate_json(response)

        # TODO: stash generation output to a file for debugging

        quest = Quest(
            quest_outline=quest_generation_output.quest_outline,
            quest_details=quest_generation_output.quest_details,
            status="active",
            title=quest_generation_output.title,
            description=quest_generation_output.description,
            overall_goal=quest_generation_output.overall_goal,
            steps=quest_generation_output.steps,
            current_step=quest_generation_output.steps[0].title,
            files=[]
        )
        self.quests[quest.title] = quest
        return quest
    
    def create_quest_file(self, llm_url: str, quest_title: str, file_name: str, file_content: str, file_description: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "create_quest_file",
            "description": "Create a file for a quest.",
            "arguments": [
                {
                    "name": "quest_title",
                    "type": "str",
                    "description": "The title of the quest."
                },
                {
                    "name": "file_name",
                    "type": "str",
                    "description": "The name of the file."
                },
                {
                    "name": "file_description",
                    "type": "str",
                    "description": "A description of the file."
                },
                {
                    "name": "file_content",
                    "type": "str",
                    "description": "The content of the file. must be a string of text."
                }
            ]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            raise ValueError(f"Quest with name {quest_title} not found")
        quest.files.append(QuestFile(file_name=file_name, file_content=file_content, file_description=file_description, notes=[]))
        return quest

    def get_quest_file_details(self, quest_title: str, file_name: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "get_quest_file_details",
            "description": "Get the details of a file.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },
            {
                "name": "file_name",
                "type": "str",
                "description": "The name of the file."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return "Quest not found"
        for file in quest.files:
            if file.file_name == file_name:
                result = f"Quest: {quest_title}\n"
                result = f"File: {file_name}\n"
                result += f"Description: {file.file_description}\n"
                result += f"Notes:\n {'\n'.join([f'{index}: {note}' for index, note in enumerate(file.notes)])}"
                return result
        return "File not found"
    
    def get_quest_file_content(self, quest_title: str, file_name: str, show_line_numbers: bool = False):
        """
        {
            "toolset_id": "quest_manager",
            "name": "get_quest_file_content",
            "description": "Get the content of a file.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },
            {
                "name": "file_name", 
                "type": "str",
                "description": "The name of the file."
            },
            {
                "name": "show_line_numbers",
                "type": "bool", 
                "description": "Whether to show line numbers in the content."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return "Quest not found"
        for file in quest.files:
            if file.file_name == file_name:
                if not show_line_numbers:
                    return file.file_content
                else:
                    return "\n".join([f"{index}: {line}" for index, line in enumerate(file.file_content.splitlines())])
            
        return "File not found"
               
    def add_quest_file_note(self, quest_title: str, file_name: str, note: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "add_quest_file_note",
            "description": "Add a note to a file.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },
            {
                "name": "file_name",
                "type": "str",
                "description": "The name of the file."
            },
            {
                "name": "note",
                "type": "str",
                "description": "The note to add to the file."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return None
        if file_name not in quest.files:
            return f"Quest {quest_title} does not have a file named {file_name}"
        quest.files[file_name].notes.append(note)
        return f"Note added to file {file_name}: {note}"
    
    def update_quest_file_description(self, quest_title: str, file_name: str, file_description: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "update_quest_file_description",
            "description": "Update the description of a file.",
            "arguments": [
                {
                    "name": "quest_title",
                    "type": "str",
                    "description": "The title of the quest."
                },
                {
                    "name": "file_name",
                    "type": "str",
                    "description": "The name of the file."
                },
                {
                    "name": "file_description",
                    "type": "str",
                    "description": "The new description of the file."
                }
            ]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return f"Quest {quest_title} not found"
        if file_name not in quest.files:
            return f"Quest {quest_title} does not have a file named {file_name}"
        
        quest.files[file_name].file_description = file_description
        return f"File description updated for {file_name}: {file_description}"
    
    def delete_quest_file_note(self, quest_title: str, file_name: str, note_index: int):
        """
        {
            "toolset_id": "quest_manager",
            "name": "delete_quest_file_note",
            "description": "Delete a note from a file.",
            "arguments": [
                {
                    "name": "quest_title",
                    "type": "str",
                    "description": "The title of the quest."
                },
                {
                    "name": "file_name",
                    "type": "str",
                    "description": "The name of the file."
                },
                {
                    "name": "note_index",
                    "type": "int",
                    "description": "The index of the note to delete."
                }
            ]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return f"Quest {quest_title} not found"
        if file_name not in quest.files:
            return f"Quest {quest_title} does not have a file named {file_name}"
        quest.files[file_name].notes.pop(note_index)
        return f"Quest {quest_title} file {file_name} note {note_index} deleted"
    
    def update_quest_file_content(self, quest_title: str, file_name: str, file_content_diff: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "update_quest_file_content",
            "description": "Update the content of a file.",
            "arguments": [
                {
                    "name": "quest_title",
                    "type": "str",
                    "description": "The title of the quest."
                },
                {
                    "name": "file_name",
                    "type": "str",
                    "description": "The name of the file."
                },
                {
                    "name": "file_content_diff",
                    "type": "str",
                    "description": "The diff of the file content. unified diff format."
                }
            ]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return "Quest not found"
        if file_name not in quest.files:
            return "File not found"
        file = quest.files[file_name]
        # apply unified diff to file content
        file.file_content = apply_unified_diff(file.file_content, file_content_diff)
        return f"Quest {quest_title} file {file_name} content updated"
  
    def get_quest(self, title: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "get_quest",
            "description": "Get a quest by title.",
            "arguments": [{
                "name": "title",
                "type": "str",
                "description": "The title of the quest."
            }]
        }
        """
        result = ""
        for quest in self.quests:
            if quest.title == title:
                if self.current_quest_name == quest.title:
                    result += "Current Quest\n"
                result += quest.title + "\n"
                result += quest.description + "\n"
                result += "Overall Goal: " + quest.overall_goal + "\n"
                result += "Status: " + quest.status + "\n"
                for index, step in enumerate(quest.steps):
                    result +=  f"[{index}] " + step.title + "\n"                    
                    if self.current_quest_name == quest.title and quest.current_step == step.title:
                        result += "Current Step of Current Quest\n"
                        result += step.description + "\n"
                        result += "Completion Criteria: " + step.completion_criteria + "\n"
                        result += "Notes: " + "\n".join([f"{index}: {note}" for index, note in enumerate(step.notes)]) + "\n"
                    elif quest.current_step == step.title and self.current_quest_name != quest.title:
                        result += "Current Step on non-current quest\n"
                        result += step.description + "\n"
                        result += "Completion Criteria: " + step.completion_criteria + "\n"
                        result += "Notes: " + "\n".join([f"{index}: {note}" for index, note in enumerate(step.notes)]) + "\n"
                        result += "Files:\n" + "\n".join([f"{file.file_name}: {file.file_description}" for file in quest.files]) + "\n"
        if result == "":
            return "No quest found"
        return result
    
    def get_quest_step(self, quest_title: str, step_title: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "get_quest_step",
            "description": "Get a quest step by title.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "step_title",
                "type": "str",
                "description": "The title of the step."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            raise ValueError(f"Quest with name {quest_title} not found")
        result = f"Quest: {quest_title}\n"
        for index, step in enumerate(quest.steps):
            if step.title == step_title:
                result += f"[{index}] " + step.title + "\n"                    
                if self.current_quest_name == quest.title and quest.current_step == step.title:
                    result += "Current Step\n"
                    result += step.description + "\n"
                    result += "Completion Criteria: " + step.completion_criteria + "\n"
                    result += "Notes: " + "\n".join([f"{index}: {note}" for index, note in enumerate(step.notes)]) + "\n"
                return result
        return None

    def get_current_quest(self):
        """
        {
            "toolset_id": "quest_manager",
            "name": "get_current_quest",
            "description": "Get the current quest.",
            "arguments": []
        }
        """
        return self.get_quest(self.current_quest_name)
    
    def get_current_quest_step(self):
        """
        {
            "toolset_id": "quest_manager",
            "name": "get_current_quest_step",
            "description": "Get the current quest step.",
            "arguments": []
        }
        """
        quest = self.get_quest_by_title(self.current_quest_name)
        if quest is None:
            return "Quest not found"
        for step in quest.steps:
            if step.title == quest.current_step:
                return self.get_quest_step(self.current_quest_name, step.title)
        return "Current step not found"
    
    def add_quest_step_note(self, quest_title: str, step_title: str, note: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "add_quest_step_note",
            "description": "Add a note to a quest step.",
            "arguments": [{
                "name": "quest_title", 
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "step_title",
                "type": "str",
                "description": "The title of the step."
            },{
                "name": "note",
                "type": "str",
                "description": "The note to add to the quest step."
            }]
        }
        """ 
        quest = self.quests[quest_title]
        if quest is None:
            raise ValueError(f"Quest with name {quest_title} not found")
        if step_title not in quest.steps:
            return f"Quest {quest_title} does not have a step named {step_title}"
        quest.steps[step_title].notes.append(note)
        return quest
    
    def insert_quest_step(self, index: int, quest_title: str, step_title: str, step_description: str, step_completion_criteria: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "insert_quest_step",
            "description": "Insert a quest step.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "step_title",
                "type": "str",
                "description": "The title of the step."
            },{
                "name": "step_description",
                "type": "str",
                "description": "The description of the step."
            },{
                "name": "step_completion_criteria",
                "type": "str",
                "description": "The completion criteria of the step."
            }]
        }
        """
        
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            raise ValueError(f"Quest with name {quest_title} not found")
        quest.steps.insert(index, QuestStep(title=step_title, description=step_description, completion_criteria=step_completion_criteria, notes=step_notes))
        return quest
    
    def update_quest_step_description(self, quest_title: str, step_title: str, step_description: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "update_quest_step_description",
            "description": "Update the description of a quest step.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "step_title",
                "type": "str",
                "description": "The title of the step."
            },{
                "name": "step_description",
                "type": "str",
                "description": "The new description of the step."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            raise ValueError(f"Quest with name {quest_title} not found")
        quest.steps[step_title].description = step_description
        return quest
    
    def update_quest_step_completion_criteria(self, quest_title: str, step_title: str, step_completion_criteria: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "update_quest_step_completion_criteria",
            "description": "Update the completion criteria of a quest step.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "step_title",
                "type": "str",
                "description": "The title of the step."
            },{
                "name": "step_completion_criteria",
                "type": "str",
                "description": "The new completion criteria of the step."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return "Quest not found"
        if step_title not in quest.steps:
            return "Step not found"
        quest.steps[step_title].completion_criteria = step_completion_criteria
        return f"Quest {quest_title} step {step_title} completion criteria updated"
    
    def delete_quest_step(self, quest_title: str, step_title: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "delete_quest_step",
            "description": "Delete a quest step.",
            "arguments": [{
                "name": "quest_title", 
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "step_title",
                "type": "str",
                "description": "The title of the step."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return "Quest not found"
        if step_title not in quest.steps:
            return "Step not found"
        quest.steps.pop(step_title)
        return f"Quest {quest_title} step {step_title} deleted"

    def delete_quest_step_note(self, quest_title: str, step_title: str, note_index: int):
        """
        {
            "toolset_id": "quest_manager",
            "name": "delete_quest_step_note",
            "description": "Delete a note from a quest step.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "step_title",
                "type": "str",
                "description": "The title of the step."
            },{
                "name": "note_index",
                "type": "int",
                "description": "The index of the note to delete."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return "Quest not found"
        if step_title not in quest.steps:
            return "Step not found"
        if note_index < 0 or note_index >= len(quest.steps[step_title].notes):
            return "Note index out of bounds"
        quest.steps[step_title].notes.pop(note_index)
        return f"Quest {quest_title} step {step_title} note {note_index} deleted"

    def set_current_quest(self, name: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "set_current_quest",
            "description": "Set the current quest.",
            "arguments": [{
                "name": "name",
                "type": "str",
                "description": "The title of the quest."
            }]
        }
        """
        if name not in self.quests:
            return "Quest not found"
        self.current_quest_name = name
        return f"Current quest set to {name}"

    def set_current_quest_step(self, step_title: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "set_current_quest_step",
            "description": "Set the current quest step.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "step_title",
                "type": "str",
                "description": "The title of the step."
            }]
        }
        """
        quest = self.get_quest_by_title(self.current_quest_name)
        if quest is None:
            return "Quest not found"
        if step_title not in quest.steps:
            return "Step not found"
        if quest.status != "active":
            return "Quest is not active"
        quest.current_step = step_title
        return f"Current quest {self.current_quest_name} step set to {step_title}"

    def submit_quest_for_review(self, quest_title: str, submission_notes: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "submit_quest_for_review",
            "description": "Submit a quest for review.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "submission_notes",
                "type": "str",
                "description": "The notes for the submission."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return "Quest not found"
        quest.status = "submitted for review"
        
        quest_submission = QuestSubmission(
            quest_title=quest_title,
            submission_notes=submission_notes
        )
        self.quest_submissions.append(quest_submission)

        return f"Quest {quest_title} submitted for review"

    def abandon_quest(self, quest_title: str, abandonment_notes: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "abandon_quest",
            "description": "Abandon a quest.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "abandonment_notes",
                "type": "str",
                "description": "The notes for the abandonment."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return "Quest not found"
        quest.status = "abandoned"
        quest.abandonment_notes = abandonment_notes
        return f"Quest {quest_title} abandoned"
    
    ############### Agent Interface ###############
    def get_tool_schemas(self):
        return [tool_schema.model_dump_json() for tool_schema in self.tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.toolset_id != "quest_manager":
            raise ValueError(f"Toolset {tool_call.toolset_id} not found")

        if tool_call.name == "get_quest_list":
            return self.get_quest_list()
        elif tool_call.name == "create_quest":
            return self.create_quest(agent.default_llm_url, tool_call.arguments["overall_goal"], tool_call.arguments["context"], tool_call.arguments["details"]).model_dump_json()
        elif tool_call.name == "create_quest_file":
            return self.create_quest_file(tool_call.arguments["quest_title"], tool_call.arguments["file_name"], tool_call.arguments["file_content"], tool_call.arguments["file_description"], tool_call.arguments["file_notes"])
        elif tool_call.name == "get_quest_file_details":
            return self.get_quest_file_details(tool_call.arguments["quest_title"], tool_call.arguments["file_name"])
        elif tool_call.name == "get_quest_file_content":
            return self.get_quest_file_content(tool_call.arguments["quest_title"], tool_call.arguments["file_name"], tool_call.arguments["show_line_numbers"])
        elif tool_call.name == "add_quest_file_note":
            return self.add_quest_file_note(tool_call.arguments["quest_title"], tool_call.arguments["file_name"], tool_call.arguments["note"])
        elif tool_call.name == "update_quest_file_description":
            return self.update_quest_file_description(tool_call.arguments["quest_title"], tool_call.arguments["file_name"], tool_call.arguments["file_description"])
        elif tool_call.name == "delete_quest_file_note":
            return self.delete_quest_file_note(tool_call.arguments["quest_title"], tool_call.arguments["file_name"], tool_call.arguments["note_index"])
        elif tool_call.name == "update_quest_file_content":
            return self.update_quest_file_content(tool_call.arguments["quest_title"], tool_call.arguments["file_name"], tool_call.arguments["file_content_diff"])
        elif tool_call.name == "get_quest":
            return self.get_quest(tool_call.arguments["title"])
        elif tool_call.name == "get_quest_step":
            return self.get_quest_step(tool_call.arguments["quest_title"], tool_call.arguments["step_title"])
        elif tool_call.name == "get_current_quest":
            return self.get_current_quest()
        elif tool_call.name == "get_current_quest_step":
            return self.get_current_quest_step()
        elif tool_call.name == "add_quest_step_note":
            return self.add_quest_step_note(tool_call.arguments["quest_title"], tool_call.arguments["step_title"], tool_call.arguments["note"])
        elif tool_call.name == "insert_quest_step":
            return self.insert_quest_step(tool_call.arguments["index"], tool_call.arguments["quest_title"], tool_call.arguments["step_title"], tool_call.arguments["step_description"], tool_call.arguments["step_completion_criteria"])
        elif tool_call.name == "update_quest_step_description":
            return self.update_quest_step_description(tool_call.arguments["quest_title"], tool_call.arguments["step_title"], tool_call.arguments["step_description"])
        elif tool_call.name == "update_quest_step_completion_criteria":
            return self.update_quest_step_completion_criteria(tool_call.arguments["quest_title"], tool_call.arguments["step_title"], tool_call.arguments["step_completion_criteria"])
        elif tool_call.name == "delete_quest_step":
            return self.delete_quest_step(tool_call.arguments["quest_title"], tool_call.arguments["step_title"])
        elif tool_call.name == "delete_quest_step_note":
            return self.delete_quest_step_note(tool_call.arguments["quest_title"], tool_call.arguments["step_title"], tool_call.arguments["note_index"])
        elif tool_call.name == "set_current_quest":
            return self.set_current_quest(tool_call.arguments["name"])
        elif tool_call.name == "set_current_quest_step":
            return self.set_current_quest_step(tool_call.arguments["quest_title"], tool_call.arguments["step_title"])
        elif tool_call.name == "submit_quest_for_review":
            return self.submit_quest_for_review(tool_call.arguments["quest_title"], tool_call.arguments["submission_notes"])
        elif tool_call.name == "abandon_quest":
            return self.abandon_quest(tool_call.arguments["quest_title"], tool_call.arguments["abandonment_notes"])
