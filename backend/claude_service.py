import json

import anthropic
from dotenv import load_dotenv

from backend.project_service import (
    get_project_by_id,
    get_critical_rfis,
    get_project_summary,
    get_project_rfis,
)


load_dotenv()

client = anthropic.Anthropic()


SYSTEM_PROMPT = (
    "You are BuildFlow AI, an assistant for construction project management. "
    "Help users understand project information, RFIs, project risks, and "
    "construction workflows. Be concise and do not invent project data. "
    "Use available tools when project-specific information is required."
)


tools = [
    {
        "name": "get_critical_rfis",
        "description": (
            "Get the critical RFIs for a construction project. "
            "Use this when the user asks which RFIs are critical, urgent, "
            "blocking, or need immediate attention."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "The numeric ID of the construction project.",
                }
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_project_summary",
        "description": (
            "Get a summary of a construction project, including the project name, "
            "total number of RFIs, number of critical RFIs, and number of blocking RFIs. "
            "Use this when the user asks for a project overview, summary, status, "
            "or general RFI counts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "The numeric ID of the construction project.",
                }
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_project_rfis",
        "description": (
            "Get all RFIs for a construction project. "
            "Use this when the user asks to see, list, review, or inspect "
            "all RFIs for a specific project."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "The numeric ID of the construction project.",
                }
            },
            "required": ["project_id"],
        },
    },
]


def ask_claude(message: str):
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT,
        tools=tools,
        messages=[
            {
                "role": "user",
                "content": message,
            }
        ],
    )

    return response


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
            "critical_rfis": critical_rfis,
        }

    if tool_use.name == "get_project_summary":
        project_id = tool_use.input["project_id"]

        project = get_project_by_id(project_id)

        if project is None:
            return {
                "error": "Project not found"
            }

        return get_project_summary(project)

    if tool_use.name == "get_project_rfis":
        project_id = tool_use.input["project_id"]

        project = get_project_by_id(project_id)

        if project is None:
            return {
                "error": "Project not found"
            }

        return {
            "project_id": project["id"],
            "project_name": project["name"],
            "rfis": get_project_rfis(project),
        }

    return {
        "error": f"Unknown tool: {tool_use.name}"
    }


def send_tool_result(
    original_message: str,
    response,
    tool_use,
    result,
):
    followup_response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT,
        tools=tools,
        messages=[
            {
                "role": "user",
                "content": original_message,
            },
            {
                "role": "assistant",
                "content": response.content,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result),
                    }
                ],
            },
        ],
    )

    return followup_response


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
            result,
        )

        return final_response.content[0].text

    return "BuildFlow could not complete the request."


if __name__ == "__main__":
    user_message = "Give me a summary of project 101."

    answer = chat_with_buildflow(user_message)

    print(answer)