"""
Manual, human-readable run through common edge cases — using your REAL
Ollama + Groq models (mocked Gmail only, so it never touches a real inbox).

Unlike tests/, which mocks the LLMs for fast, offline, deterministic CI runs,
this script is meant to be run by hand after setup to sanity-check that your
actual models behave reasonably on tricky inputs.

Usage:
    python scripts/simulate_edge_cases.py

Requires: Ollama running with qwen2.5:1.5b + nomic-embed-text pulled, a
valid GROQ_API_KEY in .env, and a vector store already built
(`python create_index.py`).
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from colorama import Fore, Style

from src.config import print_startup_report, settings
from src.state import Email

SCENARIOS = [
    {
        "name": "Ordinary product question",
        "email": dict(id="s1", threadId="t1", messageId="<s1@x>", references="",
                      sender="buyer@example.com", subject="Pricing",
                      body="Hi, what pricing plans do you offer?"),
    },
    {
        "name": "Angry complaint",
        "email": dict(id="s2", threadId="t2", messageId="<s2@x>", references="",
                      sender="angry@example.com", subject="This is unacceptable",
                      body="Your service went down for 3 hours yesterday and nobody told me why. "
                           "I want an explanation and I want it now."),
    },
    {
        "name": "Clearly unrelated spam",
        "email": dict(id="s3", threadId="t3", messageId="<s3@x>", references="",
                      sender="spam@example.com", subject="You won!!!",
                      body="CLICK HERE to claim your free prize now!!!"),
    },
    {
        "name": "Question with NO answer in the knowledge base",
        "email": dict(id="s4", threadId="t4", messageId="<s4@x>", references="",
                      sender="curious@example.com", subject="Random question",
                      body="Do you support quantum computing integrations?"),
    },
    {
        "name": "Very short / low-context email",
        "email": dict(id="s5", threadId="t5", messageId="<s5@x>", references="",
                      sender="terse@example.com", subject="?", body="price?"),
    },
    {
        "name": "Non-English email",
        "email": dict(id="s6", threadId="t6", messageId="<s6@x>", references="",
                      sender="global@example.com", subject="Question",
                      body="Bonjour, quels sont vos tarifs ?"),
    },
    {
        "name": "Very long, rambling email",
        "email": dict(id="s7", threadId="t7", messageId="<s7@x>", references="",
                      sender="rambler@example.com", subject="A few things",
                      body=("So I've been a customer for a while now and I really like the "
                            "product but I had some issues last month and also I wanted to ask "
                            "about pricing for a bigger plan and also whether you support SSO "
                            "and also one more thing, do you have a referral program? ") * 5),
    },
]


def main():
    print(Fore.CYAN + "=== Pre-flight checks ===" + Style.RESET_ALL)
    problems = print_startup_report(require_gmail=False)
    if problems:
        print(Fore.RED + "Fix the above before running live scenarios. Aborting." + Style.RESET_ALL)
        sys.exit(1)

    from src.agents import Agents
    agents = Agents()

    print(Fore.CYAN + f"\nUsing Ollama ({settings.ollama_llm_model}) for routing, "
                       f"Groq ({settings.groq_model}) for writing.\n" + Style.RESET_ALL)

    results = []
    for scenario in SCENARIOS:
        name = scenario["name"]
        email = Email(**scenario["email"])
        print(Fore.YELLOW + f"\n--- {name} ---" + Style.RESET_ALL)
        try:
            category = agents.categorize_email({"email": email.body}).category.value
            print(f"  category: {category}")

            if category == "unrelated":
                print(Fore.GREEN + "  -> would be skipped (expected for spam)." + Style.RESET_ALL)
                results.append((name, "OK"))
                continue

            context = ""
            if category == "product_enquiry":
                queries = agents.design_rag_queries({"email": email.body}).queries
                print(f"  rag queries: {queries}")
                for q in queries:
                    answer = agents.generate_rag_answer(q)
                    context += f"{q}\n{answer}\n\n"
                    print(f"  rag answer ({q[:40]}...): {answer[:120]}...")

            draft = agents.email_writer({
                "email_information": f"# CATEGORY: {category}\n\n# EMAIL:\n{email.body}\n\n# INFO:\n{context}",
                "history": [],
            }).email
            print(f"  draft ({len(draft)} chars): {draft[:150]}...")

            review = agents.email_proofreader({
                "initial_email": email.body, "generated_email": draft,
            })
            print(f"  proofreader sendable={review.send}: {review.feedback[:150]}")

            results.append((name, "OK"))
        except Exception as e:
            print(Fore.RED + f"  FAILED: {type(e).__name__}: {e}" + Style.RESET_ALL)
            results.append((name, f"FAILED: {e}"))

    print(Fore.CYAN + "\n=== Summary ===" + Style.RESET_ALL)
    for name, outcome in results:
        color = Fore.GREEN if outcome == "OK" else Fore.RED
        print(color + f"  [{outcome}] {name}" + Style.RESET_ALL)


if __name__ == "__main__":
    main()
