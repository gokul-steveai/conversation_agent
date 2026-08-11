import asyncio

from dotenv import load_dotenv

load_dotenv()

from graph.workflow import graph


async def main():
    print("==========================================")
    print("  🚀 Starting Interactive Onboarding Session")
    print("==========================================")

    result = await graph.ainvoke({})

    print("------------------------------------------")
    print("📋 Collected Profile Summary:")
    print(f"  • Name:     {result.get('name')}")
    print(f"  • Location: {result.get('location')}")
    print(f"  • Topics:   {', '.join(result.get('topic_preferences', []))}")
    print("==========================================")


if __name__ == "__main__":
    asyncio.run(main())
