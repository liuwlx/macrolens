"""Worker task modules.

Tasks are imported explicitly by the runner so optional integrations (OpenAI, PDF parsing)
do not become hard import-time requirements for calendar or provider tooling.
"""
