# Project 3: the harness.

import os
import sys
from dotenv import load_dotenv
import requests
import json
import re
import subprocess
from jsonschema import validate, ValidationError

load_dotenv()

API_KEY = os.getenv("LITELLM_API_KEY")
BASE_URL = os.getenv("LITELLM_BASE_URL")
MODEL = os.getenv("LITELLM_MODEL")

# Read system prompt from file
SYSTEM = open("systemprompt.md", encoding="utf-8").read()

# Read skills and extract name/description from SKILL.md files
skills = []
skills_context = ""
skills_dir = "skills"
if os.path.isdir(skills_dir):
    skill_folders = sorted([d for d in os.listdir(skills_dir) 
                           if os.path.isdir(os.path.join(skills_dir, d))])
    for skill_folder in skill_folders:
        skill_file = os.path.join(skills_dir, skill_folder, "SKILL.md")
        if os.path.isfile(skill_file):
            with open(skill_file, encoding="utf-8") as f:
                full_content = f.read()
            # Extract YAML frontmatter
            lines = full_content.split("\n")
            if lines[0].strip() == "---":
                name = None
                description = None
                for line in lines[1:]:
                    if line.strip() == "---":
                        break
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        description = line.split(":", 1)[1].strip()
                if name and description:
                    skills.append({
                        "name": name,
                        "description": description,
                        "full_content": full_content
                    })
                    skills_context += f"- {name}: {description}\n"
    
    if skills_context:
        SYSTEM += "\n\n=== Available Skills ===\n" + skills_context

# Add tool instructions to system message
SYSTEM += """\n\n=== IMPORTANT: Tool Commands ===

You MUST use tool commands for file operations. Send exactly ONE command per reply.

All paths are relative to the project folder.

1. To CREATE or CHANGE a file, reply with ONLY this JSON (never paste code in plain text):
{"command": "write_file", "path": "stats.js", "content": "file contents here"}

2. To RUN a Python file, reply with ONLY this JSON (never paste code in plain text):
{"command": "execute_file", "path": "untangle/solve.py", "args": ["arg1", "arg2"]}
(args is optional)

3. To READ a file:
{"command": "read_file", "path": "utils.py"}

CRITICAL: When you need to create, modify, or run code, you MUST use write_file or execute_file commands with only the JSON object. Do NOT paste code or scripts in plain text responses. The harness will handle file creation and execution for you."""

# JSON schema for tool calls
TOOL_CALL_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "enum": ["read_file", "write_file", "execute_file"]
        },
        "path": {
            "type": "string"
        },
        "content": {
            "type": "string"
        },
        "args": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["command", "path"],
    "additionalProperties": False
}

def strip_code_fences(text):
    """Remove markdown code fences from text."""
    text = re.sub(r'```(?:json)?\s*\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
    return text.strip()

def looks_like_tool_call(text):
    """Check if text looks like it's trying to be a tool call."""
    cleaned = strip_code_fences(text)
    return cleaned.startswith("{")

def validate_tool_call(reply):
    """Validate that the reply matches the tool call schema."""
    cleaned = strip_code_fences(reply)
    
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return False, None, "Reply is not valid JSON"
    
    try:
        validate(instance=data, schema=TOOL_CALL_SCHEMA)
        return True, data, None
    except ValidationError as e:
        return False, None, f"Schema validation error: {e.message}"

def ask_confirmation(command_dict):
    """Print command and ask for confirmation."""
    print(f"\n[Command] {json.dumps(command_dict, indent=2)}")
    response = input("Execute this command? (yes/no): ").strip().lower()
    return response == "yes"

def find_matching_skills(user_message):
    """Find skills whose descriptions match the user message."""
    stopwords = {
        "use", "when", "a", "an", "the", "or", "to", "of", "in", "on",
        "its", "that", "message", "messages", "asks", "decides", "job",
        "needs", "make", "skill", "starts", "with", "program"
    }
    
    # Extract keywords from user message
    user_words = set()
    for word in user_message.lower().split():
        clean_word = re.sub(r'[^\w]', '', word)
        if clean_word and clean_word not in stopwords:
            user_words.add(clean_word)
    
    matching = []
    for skill in skills:
        # Extract keywords from skill description
        skill_keywords = set()
        for word in skill["description"].lower().split():
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word and clean_word not in stopwords:
                skill_keywords.add(clean_word)
        
        # Check if at least one keyword matches
        if skill_keywords & user_words:
            matching.append(skill)
    
    return matching

def execute_command(tool_data, context):
    """Execute a tool command and return the result message."""
    command = tool_data["command"]
    path = tool_data["path"]
    
    if command == "read_file":
        try:
            with open(path, 'r', encoding='utf-8') as f:
                file_contents = f.read()
            return f"File contents of {path}:\n{file_contents}"
        except FileNotFoundError:
            return f"Error: File not found at {path}"
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    elif command == "write_file":
        try:
            content = tool_data.get("content", "")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"
    
    elif command == "execute_file":
        try:
            args = tool_data.get("args", [])
            cmd = [sys.executable, path] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return f"Execution output from {path}:\n{output}"
        except subprocess.TimeoutExpired:
            return f"Error: Execution of {path} timed out"
        except Exception as e:
            return f"Error executing file: {str(e)}"

def call_model(context):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = [{"role": "system", "content": SYSTEM}]
    
    # Process context - skip the first system message dict if present
    start_idx = 1 if (context and isinstance(context[0], dict) and context[0].get("role") == "system") else 0
    for i, item in enumerate(context[start_idx:]):
        if isinstance(item, dict):
            messages.append(item)
        else:
            # String items alternate between user and assistant
            if i % 2 == 0:
                messages.append({"role": "user", "content": item})
            else:
                messages.append({"role": "assistant", "content": item})
    
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 8000
    }
    
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=headers,
        json=payload
    )
    
    response.raise_for_status()
    data = response.json()
    
    reply = data["choices"][0]["message"]["content"]
    finish_reason = data["choices"][0].get("finish_reason")
    
    # Check if reply was cut off
    if finish_reason == "length":
        reply += "\n\n[Note from harness: Your reply was cut off due to length limit. Please retry your response.]"
    
    return reply

context = [{"role": "system", "content": SYSTEM}]

while True:
    user = input(">>> ")
    approved = (user == "approve")
    context.append(user)
    
    # Find matching skills and prepare skill injection for this turn
    matching_skills = find_matching_skills(user)
    skill_items = []
    if matching_skills:
        for skill in matching_skills:
            skill_items.append({
                "role": "user",
                "content": f"\n=== Injected Skill: {skill['name']} ===\n{skill['full_content']}"
            })
    
    # Keep calling model and handling tool calls until we get plain text
    while True:
        reply = call_model(context + skill_items)
        print(reply)
        
        # Check if reply looks like a tool call attempt
        if looks_like_tool_call(reply):
            is_valid, tool_data, error = validate_tool_call(reply)
            
            if is_valid:
                # PreToolUse hook: check if write_file needs approval
                if (tool_data["command"] == "write_file" and 
                    tool_data["path"] not in ("PLAN.md", "profile.json") and 
                    not approved):
                    context.append(reply)
                    context.append("harness: waiting for approve")
                    continue
                
                # Valid tool call - ask for confirmation
                if ask_confirmation(tool_data):
                    result = execute_command(tool_data, context)
                    
                    # PostToolUse hook: run CHECK if write_file
                    if tool_data["command"] == "write_file" and os.path.exists("CHECK"):
                        try:
                            check_script = open("CHECK").read()
                            proc = subprocess.run(
                                check_script,
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=120
                            )
                            result += "\nharness: " + proc.stdout + proc.stderr
                        except subprocess.TimeoutExpired:
                            result += "\nharness: check timed out"
                    
                    context.append(reply)
                    context.append(result)
                    # Continue looping to call the model again with the result
                else:
                    context.append(reply)
                    context.append("Command cancelled by user.")
                    break
            else:
                # Looks like tool call but invalid - report error and retry
                print(f"\n[Error] {error}")
                context.append(reply)
                context.append(f"Error: {error}")
                # Continue looping to call the model again
        else:
            # Plain text reply - break out
            context.append(reply)
            break
