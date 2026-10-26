import logging
import time

from .config import get_settings
from .jobs import process_pending_activity_runs, process_pending_model_jobs
from .llm import LLMService
from .supabase import Supabase


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def run_once() -> int:
    settings = get_settings()
    db = Supabase(settings)
    llm = LLMService(settings)
    count = process_pending_model_jobs(db, llm)
    count += process_pending_activity_runs(db, llm)
    return count


def main() -> None:
    while True:
        try:
            count = run_once()
            logging.info("worker cycle complete; processed=%s", count)
        except Exception:
            logging.exception("worker cycle failed")
        time.sleep(60)


if __name__ == "__main__":
    main()
