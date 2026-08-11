from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config.constants import DEFAULT_GREETING, SYSTEM_PROMPT_PERSONAL_INFO
from core.llm_factory import llm
from schemas.schemas import PersonalInformationResponse
from schemas.state import OnboardingState
from utils.console import ConsoleUI


async def personal_information_agent(state: OnboardingState):
    current_name = state.get("name")
    current_location = state.get("location")

    if current_name and current_location:
        return {"name": current_name, "location": current_location}

    structured_llm = llm.with_structured_output(PersonalInformationResponse)

    ConsoleUI.agent_speak(DEFAULT_GREETING)

    messages = [
        SystemMessage(SYSTEM_PROMPT_PERSONAL_INFO),
        AIMessage(DEFAULT_GREETING),
    ]

    extracted_name = current_name
    extracted_location = current_location

    while True:
        user_input = await ConsoleUI.get_user_input()
        messages.append(HumanMessage(user_input))

        response: PersonalInformationResponse = await structured_llm.ainvoke(messages)

        if response.name:
            extracted_name = response.name
        if response.location:
            extracted_location = response.location

        if response.is_complete or (extracted_name and extracted_location):
            final_reply = (
                response.agent_response
                or f"Great to meet you, {extracted_name} from {extracted_location}!"
            )
            ConsoleUI.agent_speak(final_reply)
            return {
                "name": extracted_name,
                "location": extracted_location,
            }

        ConsoleUI.agent_speak(response.agent_response)
        messages.append(AIMessage(response.agent_response))
