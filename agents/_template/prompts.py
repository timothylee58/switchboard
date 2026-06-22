"""
agents/_template/prompts.py

Keep prompts as plain module-level constants — easy to diff in PRs,
easy to eval against, no templating magic needed at this scale.

COPY THIS FILE when starting a new domain.
"""

SYSTEM_PROMPT = """\
You are {agent_name}, a specialist agent in the Switchboard system.
Replace this with real domain instructions.
"""
