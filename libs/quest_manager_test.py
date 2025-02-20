from quest_manager import QuestManager

def main():
    # Initialize the Quest Manager
    qm = QuestManager()
    llm_url = "http://localhost:5000"
    
    # Example quest creation
    overall_goal = "research Monty Python as a group, and their impact on comedy and culture as both a troupe and as individual members. I would like a detailed report on the impact of Monty Python on comedy and culture."
    details = """
    Wikepedia has a lot of information about Monty Python, and their individual members. They were super popular, so I am wondering what their larger impact on comedy and culture was.
    """
    context = "you have tools available to you to help you complete the quest"
    
    try:
        # Create a new quest
        print("Creating new quest...")
        print(f"Overall Goal: {overall_goal}")
        print(f"Context: {context}")
        print(f"Details: {details}")
     
        new_quest = qm.create_quest(llm_url, overall_goal, context, details)
        print(f"New Quest: {new_quest.model_dump_json(indent=4)}")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()