# should delete forum.db, code_environments directory, and quest_managers directory (if they exist)
import os
import shutil

if os.path.exists("forum.db"):
    os.remove("forum.db")

if os.path.exists("code_environments"):
    shutil.rmtree("code_environments")

if os.path.exists("quest_managers"):
    shutil.rmtree("quest_managers")

if os.path.exists("orchestrator.db"):
    os.remove("orchestrator.db")

if os.path.exists("std_out.txt"):
    os.remove("std_out.txt")

if os.path.exists("std_err.txt"):
    os.remove("std_err.txt")

# shared_files directory
if os.path.exists("shared_files"):
    shutil.rmtree("shared_files")

if os.path.exists("agent_database.db"):
    os.remove("agent_database.db")

if os.path.exists("user_directory.db"):
    os.remove("user_directory.db")

if os.path.exists("quest_database.db"):
    os.remove("quest_database.db")
