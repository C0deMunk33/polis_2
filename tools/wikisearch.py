import json
import wikipedia
import bs4
import traceback

from libs.common import ToolCall, ToolsetDetails
from libs.agent import Agent

########################
# Monkey patch section #
########################
_original_bs4_init = bs4.BeautifulSoup.__init__

def _monkey_patched_init(self, markup="", *args, **kwargs):
    """
    A replacement for BeautifulSoup.__init__ that enforces a specific parser.
    """
    # If the 'features' argument is not set, force the html.parser
    if 'features' not in kwargs or not kwargs['features']:
        kwargs['features'] = 'html.parser'
    _original_bs4_init(self, markup, *args, **kwargs)

# Apply the monkey patch
bs4.BeautifulSoup.__init__ = _monkey_patched_init


class WikiSearch:
    def get_toolset_details(self):
        return ToolsetDetails(
            toolset_id="wiki_toolset",
            name="Wiki Search",
            description="Searches Wikipedia"
        )

    def get_tool_schemas(self):
        return [{
            "toolset_id": "wiki_toolset",
            "name": "get_wikipedia_text",
            "arguments": {
                "title": {
                    "type": "string",
                    "description": "Title of the Wikipedia page to retrieve"
                }
            },
            "description": "Fetches Wikipedia text, title, and url. only call one of these per pass as to not overwhelm the API and your context.",
        }]
    
    def agent_tool_callback(self, agent: Agent, tool_call: ToolCall):
        tool_results = None
        try:
            if tool_call.toolset_id != "wiki_toolset":
                return f"Error: Toolset ID {tool_call.toolset_id} not found"
            
            if tool_call.name == "get_wikipedia_text":
                tool_results = self.get_wikipedia_text(tool_call.arguments["title"])
            else:
                return f"Error: Tool {tool_call.name} not found"
        except Exception as e:
            print(f"Error: {e}")
            print(f"Tool call: {tool_call}")
            print()
            print(traceback.format_exc())
            return str(e)
        return tool_results

    def get_wikipedia_text(self, title):
        # Set user agent and language (optional but recommended)
        wikipedia.set_user_agent("WikipediaResearchScript/1.0")
        wikipedia.set_lang("en")
        
        try:
            page = wikipedia.page(title, auto_suggest=False)
            return json.dumps({
                'title': page.title,
                'text': page.content,
                'url': page.url
            })
        except wikipedia.PageError:
            # Page does not exist
            return f"Error: Could not find Wikipedia page with title '{title}'"
        except wikipedia.DisambiguationError as e:
            # Title is a disambiguation page; return possible options
            return f"Error: The title '{title}' is ambiguous. Possible options include: {e.options}"
        except wikipedia.WikipediaException as we:
            # Catch-all for other Wikipedia library exceptions
            return f"Error: An unexpected error occurred. Details: {str(we)}"


def main():
    wiki_search = WikiSearch()
    result = wiki_search.get_wikipedia_text("cat")
    print(result)

if __name__ == "__main__":
    main()
