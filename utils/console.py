import asyncio


class ConsoleUI:
    @staticmethod
    def agent_speak(message: str) -> None:
        print(f"\n🤖 Agent: {message}")

    @staticmethod
    async def get_user_input(prompt_prefix: str = "👤 You: ") -> str:
        return await asyncio.to_thread(input, prompt_prefix)

    @staticmethod
    def print_tool_call(tool_name: str, description: str) -> None:
        print(f"🔍 [Tool: {tool_name}] {description}")

    @staticmethod
    def print_header(title: str) -> None:
        print("\n==========================================")
        print(f"  🚀 {title}")
        print("==========================================")

    @staticmethod
    def print_summary(name: str, location: str, topics: list[str]) -> None:
        print("\n------------------------------------------")
        print("📋 Collected Profile Summary:")
        print(f"  • Name:     {name or 'N/A'}")
        print(f"  • Location: {location or 'N/A'}")
        print(f"  • Topics:   {', '.join(topics) if topics else 'N/A'}")
        print("==========================================\n")
