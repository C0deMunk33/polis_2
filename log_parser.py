from pydantic import BaseModel

log_file = "std_out.txt"

class AgentRun(BaseModel):
    agent_id: str
    inner_text: str
    is_complete: bool

def parse_log_file(log_file: str):
    agent_runs = {} # key is the line after "###AGENT RUN STARTING###", looks like "###0###", array of runs

    with open(log_file, "r") as file:
        lines = file.readlines()

    previous_line = None
    current_agent_id = None
    for line in lines:
        if previous_line is not None and "###AGENT RUN STARTING###" in previous_line:
            current_agent_id = line.strip().split("###")[1]
            if agent_runs.get(current_agent_id) is None:
                agent_runs[current_agent_id] = []
            agent_runs[current_agent_id].append(AgentRun(agent_id=current_agent_id, inner_text="", is_complete=False))
        elif "###AGENT RUN COMPLETE###" in line:
            agent_runs[current_agent_id][-1].is_complete = True
            current_agent_id = None
        elif current_agent_id is not None and not agent_runs[current_agent_id][-1].is_complete:
            agent_runs[current_agent_id][-1].inner_text += line 

        previous_line = line
    return agent_runs

agent_runs = parse_log_file(log_file)

print(agent_runs["0"][-1].inner_text)