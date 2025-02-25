try:
    from .agent import Agent
except ImportError:
    from agent import Agent

class AdminAgent(Agent):
    def __init__(self):
        super().__init__()