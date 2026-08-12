NODE_PERSONAL_INFO = "personal_information"
NODE_TOPIC_PREF = "topic_preferences"
NODE_ENGAGEMENT = "customer_engagement"
NODE_CHAT = "chat"
NODE_SUPERVISOR = "supervisor"
NODE_FINISH = "FINISH"

APP_TITLE = "AI Chat Assistant"
APP_SUBTITLE = "Powered by FastAPI REST Backend, Groq LLM & Real-Time Tavily Web Search"

DEFAULT_GREETING = "Hello! How can I assist you today? Feel free to ask any question, search the web, or write code."
DEFAULT_TOPIC_GREETING_TEMPLATE = (
    "Now, {name}, what topics or news categories are you interested in reading about?"
)
EXIT_KEYWORDS = ["done", "exit", "no", "bye", "quit", "thanks", "thank you"]

__all__ = [
    "NODE_PERSONAL_INFO",
    "NODE_TOPIC_PREF",
    "NODE_ENGAGEMENT",
    "NODE_CHAT",
    "NODE_SUPERVISOR",
    "NODE_FINISH",
    "APP_TITLE",
    "APP_SUBTITLE",
    "DEFAULT_GREETING",
    "DEFAULT_TOPIC_GREETING_TEMPLATE",
    "EXIT_KEYWORDS",
]
