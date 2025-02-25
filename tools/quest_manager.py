from pydantic import BaseModel, Field
from typing import Dict, List

from libs.common import call_ollama_chat, Message, apply_unified_diff, ToolSchema, ToolCall, ToolsetDetails
from libs.agent import Agent
import sqlite3

# TODO: figure out why these keep happening, looks like it's the new version of ollama
import warnings
warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)

class QuestStep(BaseModel):
    title: str = Field(description="The title of the step.")
    description: str = Field(description="A description of the step.")
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

class Quest(BaseModel):
    quest_outline: List[str] = Field(description="A detailed outline of the quest.")
    quest_details: str = Field(description="A detailed description of the quest.")
    status: str = Field(description="The status of the quest.")
    title: str = Field(description="The title of the quest.")
    description: str = Field(description="A description of the quest.")
    overall_goal: str = Field(description="The overall goal of the quest.")
    current_step: str = Field(description="The title of the current step of the quest.")
    steps: List[QuestStep] = Field(description="An ordered list of steps that are designed to be completed in a specific order to complete the quest. Leave out step numbers as these can be adjusted.")
    notes: List[str] = Field(description="A list of notes about the quest.")

class QuestSubmission(BaseModel):
    quest_title: str = Field(description="The title of the quest.")
    submission_notes: str = Field(description="The notes for the submission.")

class QuestReview(BaseModel):
    quest_title: str = Field(description="The title of the quest.")
    review_notes: str = Field(description="The notes for the review.")
    accepted: bool = Field(description="Whether the quest was accepted.")

class QuestDBObject(BaseModel):
    quest_id: str = Field(description="The id of the quest.")
    agent_id: str = Field(description="The id of the agent.")
    quest_title: str = Field(description="The title of the quest.")
    quest: str = Field(description="Quest object as a json string")
    
class QuestSubmissionDBObject(BaseModel):
    submission_id: str = Field(description="The id of the submission.")
    quest_id: str = Field(description="The id of the quest.")
    submitter_id: str = Field(description="The id of the agent.")
    quest_title: str = Field(description="The title of the quest.")
    submission_notes: str = Field(description="The notes for the submission.")
    submission_date: str = Field(description="The date of the submission.")

class QuestReviewDBObject(BaseModel):
    review_id: str = Field(description="The id of the review.")
    quest_id: str = Field(description="The id of the quest.")
    quest_submission_id: str = Field(description="The id of the quest submission.")
    reviewer_id: str = Field(description="The id of the agent.")
    quest_title: str = Field(description="The title of the quest.")
    review_notes: str = Field(description="The notes for the review.")
    accepted: bool = Field(description="Whether the quest was accepted.")
    exp_awarded: int = Field(description="The amount of experience awarded for the quest.")
    review_date: str = Field(description="The date of the review.")

class QuestManager:
    def __init__(self, agent_id: str, db_path: str):
        self.quests = {}
        self.current_quest_name = None
        self.quest_submissions = []
        self.agent_id = agent_id
        self.db_path = db_path
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS quests (
            quest_id TEXT PRIMARY KEY,
            agent_id TEXT,
            quest_title TEXT,
            quest TEXT
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS quest_submissions (
            submission_id TEXT PRIMARY KEY,
            quest_id TEXT,
            submitter_id TEXT,
            quest_title TEXT,
            submission_notes TEXT,
            submission_date TEXT
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS quest_reviews (
            review_id TEXT PRIMARY KEY,
            quest_id TEXT,
            quest_submission_id TEXT,
            reviewer_id TEXT,
            quest_title TEXT,
            review_notes TEXT,
            accepted BOOLEAN,
            exp_awarded INTEGER,
            review_date TEXT
        )""")
        
        # Load quests from database
        self._load_quests_from_db()

        names_of_tools_to_expose = [
            "get_quest_list",
            "create_quest",
            "get_quest",
            "get_quest_step",
            "get_current_quest",
            "get_current_quest_step",
            "add_quest_note",
            "insert_quest_step",
            "update_quest_step_description",
            "update_quest_step_completion_criteria",
            "delete_quest_step",
            "delete_quest_note",
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

    def _load_quests_from_db(self):
        """Load quests from the database for this agent"""
        cursor = self.db.execute("SELECT * FROM quests WHERE agent_id = ?", (self.agent_id,))
        rows = cursor.fetchall()
        for row in rows:
            quest_data = row['quest']
            quest = Quest.model_validate_json(quest_data)
            self.quests[quest.title] = quest
            
    def _save_quest_to_db(self, quest: Quest):
        """Save a quest to the database"""
        import uuid
        quest_id = str(uuid.uuid4())
        
        # Check if quest already exists
        cursor = self.db.execute("SELECT quest_id FROM quests WHERE agent_id = ? AND quest_title = ?", 
                               (self.agent_id, quest.title))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing quest
            self.db.execute("UPDATE quests SET quest = ? WHERE quest_id = ?", 
                          (quest.model_dump_json(), existing['quest_id']))
        else:
            # Insert new quest
            self.db.execute("INSERT INTO quests (quest_id, agent_id, quest_title, quest) VALUES (?, ?, ?, ?)",
                          (quest_id, self.agent_id, quest.title, quest.model_dump_json()))
        
        self.db.commit()
        
    def _save_quest_submission_to_db(self, submission: QuestSubmission, quest_id: str):
        """Save a quest submission to the database"""
        import uuid
        import datetime
        
        submission_id = str(uuid.uuid4())
        submission_date = datetime.datetime.now().isoformat()
        
        self.db.execute("""
            INSERT INTO quest_submissions 
            (submission_id, quest_id, submitter_id, quest_title, submission_notes, submission_date) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (submission_id, quest_id, self.agent_id, submission.quest_title, 
              submission.submission_notes, submission_date))
        
        self.db.commit()
        return submission_id

    def get_quest_by_title(self, title: str):
        """This is for the orchestator, do not expose"""
        return self.quests.get(title)
    
    def add_quest(self, quest: Quest):
        """This is for the orchestator, do not expose"""
        self.quests[quest.title] = quest
        self._save_quest_to_db(quest)

    def get_quest_list(self):
        """
        {
            "toolset_id": "quest_manager",
            "name": "get_quest_list",
            "description": "Get the list of active quests.",
            "arguments": []
        }"""
        # get quests where status is not "abandoned" or "submitted for review"
        result = "Quest List:\n"
        if len(self.quests) == 0:
            result += "    [No quests found]"
        else:
            for quest in self.quests.values():
                if quest.status not in ["abandoned", "submitted for review"]:
                    if quest.title == self.current_quest_name:
                        result += f"    - [current] {quest.title}\n"
                    else:
                        result += f"    - {quest.title}\n"
        return result

    def create_quest(self, llm_url: str, agent: Agent, overall_goal: str, context: str, details: str):
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
                    "description": "The details of the quest. (optional)"  
                },
                {
                    "name": "context",
                    "type": "str",
                    "description": "The context of the quest. (optional)"
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

        messages = [Message(role="system", content=quest_system_prompt)]
        messages.extend(agent.latest_post_system_messages)
        # add last 4 summaries as user messages
        if len(agent.pass_summaries) > 0:
            summary_string = "Summary of recent passes:\n"
            for summary in agent.pass_summaries[-4:]:
                summary_string += f"    - {summary.summary}\n"
            messages.append(Message(role="user", content=summary_string))
        messages.append(Message(role="user", content=user_prompt))

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
            notes=[]
        )
        self.quests[quest.title] = quest
        self._save_quest_to_db(quest)
        return self.get_quest(quest.title)

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
        
        if title not in self.quests:
            return "    [No quest found]\n"
        
        quest = self.quests[title]
        
        result = "Current Quest\n"
        result += "    Title: " + quest.title + "\n"
        result += "    Description: " + quest.description + "\n"
        result += "    Overall Goal: " + quest.overall_goal + "\n"
        result += "    Status: " + quest.status + "\n"
        result += "    Notes: " + "\n".join([f"        [{index}]: {note}" for index, note in enumerate(quest.notes)]) + "\n"
        result += "    Steps:\n"
        for index, step in enumerate(quest.steps):
            result +=  f"        [{index}] " + step.title + "\n"                    
            if self.current_quest_name == quest.title and quest.current_step == step.title:
                result += "            [Current Step of Current Quest]\n"
                result += "            Description: " + step.description + "\n"
                result += "            Completion Criteria: " + step.completion_criteria + "\n"
            elif quest.current_step == step.title and self.current_quest_name != quest.title:
                result += "            [Current Step on non-current quest]\n"
                result += "            Description: " + step.description + "\n"
                result += "            Completion Criteria: " + step.completion_criteria + "\n"
        
        return result
    
    def get_quest_step(self, quest_title: str, step_index: int):
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
                "name": "step_index",
                "type": "int",
                "description": "The index of the step."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return f"Quest with title {quest_title} not found"
        result = f"Quest: {quest_title}\n"
        for index, step in enumerate(quest.steps):
            if index == step_index:
                result += f"[{index}] " + step.title + "\n"                    
                if self.current_quest_name == quest.title and quest.current_step == step.title:
                    result += "Current Step\n"
                    result += step.description + "\n"
                    result += "Completion Criteria: " + step.completion_criteria + "\n"
                return result
        return result

    def get_current_quest(self):
        """
        {
            "toolset_id": "quest_manager",
            "name": "get_current_quest",
            "description": "Get the current quest.",
            "arguments": []
        }
        """
        if self.current_quest_name is None:
            return "Quest:\n    [Current Quest not set]"
        quest = self.get_quest_by_title(self.current_quest_name)
        if quest is None:
            return "Quest:\n    [Current set quest not found]"
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
            return "Quest:\n    [Current Quest not set]"
        for index, step in enumerate(quest.steps):
            if step.title == quest.current_step:
                return self.get_quest_step(self.current_quest_name, index)
        return "Quest:\n    [Current step not found]"
    
    def add_quest_note(self, quest_title: str, note: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "add_quest_note",
            "description": "Add a note to a quest.",
            "arguments": [{
                "name": "quest_title", 
                "type": "str",
                "description": "The title of the quest."
            },{
                "name": "note",
                "type": "str",
                "description": "The note to add to the quest step."
            }]
        }
        """ 
        quest = self.quests[quest_title]
        if quest is None:
            return f"Quest with name {quest_title} not found \n"
        quest.notes.append(note)
        self._save_quest_to_db(quest)
        return f"Quest {quest_title} note added: {note}"
    
    def insert_quest_step(self, step_index: int, quest_title: str, step_title: str, step_description: str, step_completion_criteria: str):
        """
        {
            "toolset_id": "quest_manager",
            "name": "insert_quest_step",
            "description": "Insert a quest step.",
            "arguments": [{
                "name": "step_index",
                "type": "int",
                "description": "The index of the step."
            },{
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
        quest.steps.insert(step_index, QuestStep(title=step_title, description=step_description, completion_criteria=step_completion_criteria))
        self._save_quest_to_db(quest)
        return f"Quest {quest_title} step {step_title} inserted at index {step_index}"
    
    def update_quest_step_description(self, quest_title: str, step_index: int, step_description: str):
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
                "name": "step_index",
                "type": "int",
                "description": "The index of the step."
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
        quest.steps[step_index].description = step_description
        self._save_quest_to_db(quest)
        return f"Quest {quest_title} step {step_index} description updated"
    
    def update_quest_step_completion_criteria(self, quest_title: str, step_index: int, step_completion_criteria: str):
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
                "name": "step_index",
                "type": "int",
                "description": "The index of the step."
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
        if step_index < 0 or step_index >= len(quest.steps):
            return "Step index out of bounds"
        quest.steps[step_index].completion_criteria = step_completion_criteria
        self._save_quest_to_db(quest)
        return f"Quest {quest_title} step {step_index} completion criteria updated"
    
    def delete_quest_step(self, quest_title: str, step_index: int):
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
                "name": "step_index",
                "type": "int",
                "description": "The index of the step."
            }]
        }
        """
        quest = self.get_quest_by_title(quest_title)
        if quest is None:
            return "Quest not found"
        if step_index < 0 or step_index >= len(quest.steps):
            return "Step index out of bounds"
        quest.steps.pop(step_index)
        self._save_quest_to_db(quest)
        return f"Quest {quest_title} step {step_index} deleted"

    def delete_quest_note(self, quest_title: str, note_index: int):
        """
        {
            "toolset_id": "quest_manager",
            "name": "delete_quest_note",
            "description": "Delete a note from a quest.",
            "arguments": [{
                "name": "quest_title",
                "type": "str",
                "description": "The title of the quest."
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
        if note_index < 0 or note_index >= len(quest.notes):
            return "Note index out of bounds"
        quest.notes.pop(note_index)
        self._save_quest_to_db(quest)
        return f"Quest {quest_title} note {note_index} deleted"

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

    def set_current_quest_step(self, quest_title: str, step_index: int):
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
                "name": "step_index",
                "type": "int",
                "description": "The index of the step."
            }]
        }
        """
        quest = self.get_quest_by_title(self.current_quest_name)
        if quest is None:
            return "Quest not found"
        if step_index < 0 or step_index >= len(quest.steps):
            return "Step index out of bounds"
        if quest.status != "active":
            return "Quest is not active"
        quest.current_step = quest.steps[step_index].title
        self._save_quest_to_db(quest)
        return f"Current quest {self.current_quest_name} step set to {quest.steps[step_index].title}"

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
        self._save_quest_to_db(quest)
        
        quest_submission = QuestSubmission(
            quest_title=quest_title,
            submission_notes=submission_notes
        )
        self.quest_submissions.append(quest_submission)
        
        # Get quest_id from database
        cursor = self.db.execute("SELECT quest_id FROM quests WHERE agent_id = ? AND quest_title = ?", 
                               (self.agent_id, quest_title))
        row = cursor.fetchone()
        if row:
            quest_id = row['quest_id']
            self._save_quest_submission_to_db(quest_submission, quest_id)

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
        quest.notes.append(f"Abandonment note: {abandonment_notes}")
        self._save_quest_to_db(quest)
        return f"Quest {quest_title} abandoned"
    
    ############### Agent Interface ###############
    def get_toolset_details(self):
        return ToolsetDetails(
            toolset_id="quest_manager",
            name="Quest Manager",
            description="Manages quests"
        )
    
    def get_tool_schemas(self):
        return [tool_schema.model_dump_json() for tool_schema in self.tool_schemas]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        if tool_call.toolset_id != "quest_manager":
            raise ValueError(f"Toolset {tool_call.toolset_id} not found")

        if tool_call.name == "get_quest_list":
            return self.get_quest_list()
        elif tool_call.name == "create_quest":
            context = f"{agent.standing_tool_calls}"
            if "context" in tool_call.arguments:
                context = tool_call.arguments["context"]

            details = "[no details provided]"
            if "details" in tool_call.arguments:
                details = tool_call.arguments["details"]

            if "overall_goal" not in tool_call.arguments:
                return "Overall goal is required"

            return self.create_quest(agent.default_llm_url, agent, tool_call.arguments["overall_goal"], context, details)

        elif tool_call.name == "get_quest":
            return self.get_quest(tool_call.arguments["title"])
        elif tool_call.name == "get_quest_step":
            return self.get_quest_step(tool_call.arguments["quest_title"], tool_call.arguments["step_index"])
        elif tool_call.name == "get_current_quest":
            return self.get_current_quest()
        elif tool_call.name == "get_current_quest_step":
            return self.get_current_quest_step()
        elif tool_call.name == "add_quest_note":
            return self.add_quest_note(tool_call.arguments["quest_title"], tool_call.arguments["note"])
        elif tool_call.name == "insert_quest_step":
            return self.insert_quest_step(tool_call.arguments["step_index"], tool_call.arguments["quest_title"], tool_call.arguments["step_title"], tool_call.arguments["step_description"], tool_call.arguments["step_completion_criteria"])
        elif tool_call.name == "update_quest_step_description":
            return self.update_quest_step_description(tool_call.arguments["quest_title"], tool_call.arguments["step_index"], tool_call.arguments["step_description"])
        elif tool_call.name == "update_quest_step_completion_criteria":
            return self.update_quest_step_completion_criteria(tool_call.arguments["quest_title"], tool_call.arguments["step_index"], tool_call.arguments["step_completion_criteria"])
        elif tool_call.name == "delete_quest_step":
            return self.delete_quest_step(tool_call.arguments["quest_title"], tool_call.arguments["step_index"])
        elif tool_call.name == "delete_quest_note":
            return self.delete_quest_note(tool_call.arguments["quest_title"], tool_call.arguments["note_index"])
        elif tool_call.name == "set_current_quest":
            return self.set_current_quest(tool_call.arguments["name"])
        elif tool_call.name == "set_current_quest_step":
            return self.set_current_quest_step(tool_call.arguments["quest_title"], tool_call.arguments["step_index"])
        elif tool_call.name == "submit_quest_for_review":
            return self.submit_quest_for_review(tool_call.arguments["quest_title"], tool_call.arguments["submission_notes"])
        elif tool_call.name == "abandon_quest":
            return self.abandon_quest(tool_call.arguments["quest_title"], tool_call.arguments["abandonment_notes"])
