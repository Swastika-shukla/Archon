import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1"
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "detect_duplicates",
            "description": "Scan a folder for duplicate files. Requires a real folder path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Full folder path to scan",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the user for missing information before proceeding. Use this when folder path is not provided.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Question to ask the user",
                    }
                },
                "required": ["question"],
            },
        },
    },
]

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {
            "role": "system",
            "content": """You are Archon, an AI file management agent for Windows.
            
Available folders: Downloads, Documents, Desktop.
Home directory: C:/Users/HP

IMPORTANT: If the user does not specify a folder, always call ask_user to ask which folder before proceeding. Never assume or guess a path.""",
        },
        {"role": "user", "content": "check for repeated files"},
    ],
    tools=tools,
    tool_choice="auto",
)

print(response.choices[0].message.tool_calls)
