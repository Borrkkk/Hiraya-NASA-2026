"""A tiny in-memory job runner for the slow calls (motion, verify).

POST starts a job and returns {"jobId"}; the page polls GET /explore/jobs/{id}
and shows `step` as the progress message. Jobs live in memory only.
"""
import asyncio
import uuid
from collections.abc import Awaitable, Callable

JOBS: dict[str, dict] = {}
_TASKS: set = set()  # keeps running tasks alive
MAX_JOBS = 200


def start(work: Callable[[Callable[[str], None]], Awaitable[dict]]) -> str:
    if len(JOBS) >= MAX_JOBS:
        for key in list(JOBS)[: MAX_JOBS // 2]:
            JOBS.pop(key, None)
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "running", "step": "Getting started…"}

    def step(message: str):
        JOBS[job_id]["step"] = message

    async def run():
        try:
            result = await work(step)
            JOBS[job_id] = {"status": "done", "result": result}
        except Exception as exc:  # reported to the page as a plain failure
            JOBS[job_id] = {"status": "failed", "message": str(exc) or "The analysis failed."}

    task = asyncio.get_running_loop().create_task(run())
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return job_id


def get(job_id: str) -> dict | None:
    return JOBS.get(job_id)
