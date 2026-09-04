"""AegisForge worker service (AF-003).

Executes one bounded job step for a coordinator. It owns no canonical state:
the coordinator persists the job, the worker runs an attempt and reports events.
"""
