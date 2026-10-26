from .config import get_settings
from .jobs import generate_aggregate_report
from .llm import LLMService
from .supabase import Supabase


def main() -> None:
    settings = get_settings()
    row = generate_aggregate_report(Supabase(settings), LLMService(settings))
    print(f"created aggregate report {row['id']}")


if __name__ == "__main__":
    main()
