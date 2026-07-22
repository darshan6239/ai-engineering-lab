from colorama import Fore, Style

from src.config import print_startup_report
from src.graph import Workflow
from src import db

config = {'recursion_limit': 100}


def main():
    db.init_db()
    problems = print_startup_report(require_gmail=True)
    if problems:
        print(Fore.YELLOW + "Continuing anyway — fix the above if something fails.\n" + Style.RESET_ALL)

    workflow = Workflow()
    app = workflow.app

    initial_state = {
        "emails": [],
        "current_email": {
            "id": "", "threadId": "", "messageId": "", "references": "",
            "sender": "", "subject": "", "body": ""
        },
        "email_category": "",
        "generated_email": "",
        "rag_queries": [],
        "retrieved_documents": "",
        "writer_messages": [],
        "sendable": False,
        "trials": 0,
        "_error": False,
    }

    print(Fore.GREEN + "Starting workflow..." + Style.RESET_ALL)
    for output in app.stream(initial_state, config):
        for key, value in output.items():
            print(Fore.CYAN + f"Finished running: {key}:" + Style.RESET_ALL)


if __name__ == "__main__":
    main()
