# Claude / AI / Tool calling


import anthropic
from dotenv import load_dotenv

from backend.project_service import (
    get_project_by_id,
    get_critical_rfis
)

import json

load_dotenv()

client = anthropic.Anthropic()


tools = [
    {
        "name": "get_critical_rfis",
        "description": (
            "Get the critical RFIs for a construction project. "
            "Use this when the user asks which RFIs are critical, urgent, "
            "or need immediate attention."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "The numeric ID of the construction project."
                }
            },
            "required": ["project_id"]
        }
    }
]


def execute_tool(tool_use):
    if tool_use.name == "get_critical_rfis":
        project_id = tool_use.input["project_id"]

        project = get_project_by_id(project_id)

        if project is None:
            return {
                "error": "Project not found"
            }

        critical_rfis = get_critical_rfis(project["rfis"])

        return {
            "project_id": project["id"],
            "project_name": project["name"],
            "critical_rfis": critical_rfis
        }

    return {
        "error": f"Unknown tool: {tool_use.name}"
    }

def send_tool_result(
    original_message: str,
    response,
    tool_use,
    result
):
    followup_response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        thinking={"type": "disabled"},
        system=(
            "You are BuildFlow AI, an assistant for construction project management. "
            "Help users understand project information, RFIs, project risks, and "
            "construction workflows. Be concise and do not invent project data. "
            "Use available tools when project-specific information is required."
        ),
        tools=tools,
        messages=[
            {
                "role": "user",
                "content": original_message
            },
            {
                "role": "assistant",
                "content": response.content
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result)
                    }
                ]
            }
        ]
    )

    return followup_response

def ask_claude(message: str):
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        thinking={"type": "disabled"},
        system=(
            "You are BuildFlow AI, an assistant for construction project management. "
            "Help users understand project information, RFIs, project risks, and "
            "construction workflows. Be concise and do not invent project data. "
            "Use available tools when project-specific information is required."
        ),
        tools=tools,
        messages=[
            {
                "role": "user",
                "content": message
            }
        ]
    )

    return response


def chat_with_buildflow(message: str) -> str:
    response = ask_claude(message)

    if response.stop_reason == "end_turn":
        return response.content[0].text

    if response.stop_reason == "tool_use":
        tool_use = None

        for block in response.content:
            if block.type == "tool_use":
                tool_use = block
                break

        if tool_use is None:
            return "BuildFlow could not determine which tool to use."

        result = execute_tool(tool_use)

        final_response = send_tool_result(
            message,
            response,
            tool_use,
            result
        )

        return final_response.content[0].text

    return "BuildFlow could not complete the request."


if __name__ == "__main__":
    user_message = "Which RFIs are critical for project 101?"

    response = ask_claude(user_message)

    print("First stop reason:", response.stop_reason)

    if response.stop_reason == "tool_use":
        tool_use = response.content[0]

        result = execute_tool(tool_use)

        print("Tool requested:", tool_use.name)
        print("Tool input:", tool_use.input)
        print("Tool result:", result)

        final_response = send_tool_result(
            user_message,
            response,
            tool_use,
            result
        )

        print("Final stop reason:", final_response.stop_reason)
        print("Final answer:", final_response.content[0].text)