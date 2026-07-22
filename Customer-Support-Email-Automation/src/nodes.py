from colorama import Fore, Style
from .agents import Agents
from .tools.GmailTools import GmailToolsClass
from .state import GraphState, Email
from .config import settings
from . import db


class Nodes:
    def __init__(self):
        self.agents = Agents()
        self.gmail_tools = GmailToolsClass()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fail_current_email(self, state: GraphState, node: str, error: Exception) -> GraphState:
        """Common handling for an unrecoverable error while processing the
        current email: log it, mark it failed in the DB, drop it from the
        queue so one bad email can't wedge the whole run, and clear the
        error flag for the next iteration."""
        current = state.get("current_email")
        msg = f"{type(error).__name__}: {error}"
        print(Fore.RED + f"[{node}] Error processing email, skipping it: {msg}" + Style.RESET_ALL)
        if current is not None:
            db.upsert_email(
                current.id, thread_id=current.threadId, sender=current.sender,
                subject=current.subject, body=current.body[:2000],
                status="failed", error=msg,
            )
            db.log_event(current.id, node, msg, level="error")
            if state["emails"] and state["emails"][-1].id == current.id:
                state["emails"].pop()
        state["writer_messages"] = []
        state["trials"] = 0
        state["_error"] = True
        return state

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------
    def load_new_emails(self, state: GraphState) -> GraphState:
        """Loads new emails from Gmail and updates the state."""
        print(Fore.YELLOW + "Loading new emails...\n" + Style.RESET_ALL)
        try:
            recent_emails = self.gmail_tools.fetch_unanswered_emails()
        except Exception as e:
            print(Fore.RED + f"Failed to fetch emails from Gmail: {e}" + Style.RESET_ALL)
            db.log_event(None, "load_new_emails", str(e), level="error")
            return {"emails": []}

        emails = []
        for raw in recent_emails:
            try:
                emails.append(Email(**raw))
            except Exception as e:
                # A single malformed message (missing headers, odd payload,
                # etc.) shouldn't take down the whole batch.
                print(Fore.RED + f"Skipping malformed email {raw.get('id', '?')}: {e}" + Style.RESET_ALL)
                db.log_event(raw.get("id"), "load_new_emails", f"Malformed email skipped: {e}", level="error")
        for email in emails:
            db.upsert_email(
                email.id, thread_id=email.threadId, sender=email.sender,
                subject=email.subject, body=email.body[:2000], status="queued",
            )
        return {"emails": emails}

    def check_new_emails(self, state: GraphState) -> str:
        """Checks if there are new emails to process."""
        if len(state['emails']) == 0:
            print(Fore.RED + "No new emails" + Style.RESET_ALL)
            return "empty"
        else:
            print(Fore.GREEN + "New emails to process" + Style.RESET_ALL)
            return "process"

    def is_email_inbox_empty(self, state: GraphState) -> GraphState:
        state["_error"] = False
        return state

    def categorize_email(self, state: GraphState) -> GraphState:
        """Categorizes the current email using the categorize_email agent."""
        print(Fore.YELLOW + "Checking email category...\n" + Style.RESET_ALL)
        current_email = state["emails"][-1]
        try:
            result = self.agents.categorize_email({"email": current_email.body})
        except Exception as e:
            return self._fail_current_email({**state, "current_email": current_email}, "categorize_email", e)

        print(Fore.MAGENTA + f"Email category: {result.category.value}" + Style.RESET_ALL)
        db.upsert_email(current_email.id, category=result.category.value, status="processing")
        db.log_event(current_email.id, "categorize_email", f"Category: {result.category.value}")

        return {
            "email_category": result.category.value,
            "current_email": current_email,
            "_error": False,
        }

    def route_email_based_on_category(self, state: GraphState) -> str:
        """Routes the email based on its category."""
        if state.get("_error"):
            return "error"
        print(Fore.YELLOW + "Routing email based on category...\n" + Style.RESET_ALL)
        category = state["email_category"]
        if category == "product_enquiry":
            return "product related"
        elif category == "unrelated":
            return "unrelated"
        else:
            return "not product related"

    def construct_rag_queries(self, state: GraphState) -> GraphState:
        """Constructs RAG queries based on the email content."""
        print(Fore.YELLOW + "Designing RAG query...\n" + Style.RESET_ALL)
        email_content = state["current_email"].body
        try:
            query_result = self.agents.design_rag_queries({"email": email_content})
        except Exception as e:
            return self._fail_current_email(state, "construct_rag_queries", e)

        db.log_event(state["current_email"].id, "construct_rag_queries",
                      f"{len(query_result.queries)} quer(y/ies) generated")
        return {"rag_queries": query_result.queries, "_error": False}

    def retrieve_from_rag(self, state: GraphState) -> GraphState:
        """Retrieves information from internal knowledge based on RAG questions."""
        print(Fore.YELLOW + "Retrieving information from internal knowledge...\n" + Style.RESET_ALL)
        final_answer = ""
        try:
            for query in state["rag_queries"]:
                rag_result = self.agents.generate_rag_answer(query)
                final_answer += query + "\n" + rag_result + "\n\n"
        except Exception as e:
            return self._fail_current_email(state, "retrieve_from_rag", e)

        db.log_event(state["current_email"].id, "retrieve_from_rag", "Context retrieved")
        return {"retrieved_documents": final_answer, "_error": False}

    def write_draft_email(self, state: GraphState) -> GraphState:
        """Writes a draft email based on the current email and retrieved information."""
        print(Fore.YELLOW + "Writing draft email...\n" + Style.RESET_ALL)

        inputs = (
            f'# **EMAIL CATEGORY:** {state["email_category"]}\n\n'
            f'# **EMAIL CONTENT:**\n{state["current_email"].body}\n\n'
            f'# **INFORMATION:**\n{state.get("retrieved_documents", "")}'
        )
        writer_messages = state.get('writer_messages', [])

        try:
            draft_result = self.agents.email_writer({
                "email_information": inputs,
                "history": writer_messages,
            })
        except Exception as e:
            return self._fail_current_email(state, "write_draft_email", e)

        email = draft_result.email
        trials = state.get('trials', 0) + 1
        writer_messages.append(f"**Draft {trials}:**\n{email}")

        db.upsert_email(state["current_email"].id, generated_email=email, trials=trials, status="drafting")
        db.append_writer_history(state["current_email"].id, f"Draft {trials}: {email}")
        db.log_event(state["current_email"].id, "write_draft_email", f"Draft {trials} written")

        return {
            "generated_email": email,
            "trials": trials,
            "writer_messages": writer_messages,
            "_error": False,
        }

    def verify_generated_email(self, state: GraphState) -> GraphState:
        """Verifies the generated email using the proofreader agent."""
        print(Fore.YELLOW + "Verifying generated email...\n" + Style.RESET_ALL)
        try:
            review = self.agents.email_proofreader({
                "initial_email": state["current_email"].body,
                "generated_email": state["generated_email"],
            })
        except Exception as e:
            return self._fail_current_email(state, "verify_generated_email", e)

        writer_messages = state.get('writer_messages', [])
        writer_messages.append(f"**Proofreader Feedback:**\n{review.feedback}")

        db.append_writer_history(state["current_email"].id, f"Feedback: {review.feedback}")
        db.log_event(state["current_email"].id, "verify_generated_email",
                      f"sendable={review.send} feedback={review.feedback[:200]}")

        return {
            "sendable": review.send,
            "writer_messages": writer_messages,
            "_error": False,
        }

    def must_rewrite(self, state: GraphState) -> str:
        """Determines if the email needs to be rewritten based on the review and trial count."""
        if state.get("_error"):
            return "stop"
        email_sendable = state["sendable"]
        if email_sendable:
            print(Fore.GREEN + "Email is good, ready to be sent!!!" + Style.RESET_ALL)
            state["emails"].pop()
            state["writer_messages"] = []
            return "send"
        elif state["trials"] >= settings.max_rewrite_trials:
            print(Fore.RED + "Email is not good, we reached max trials must stop!!!" + Style.RESET_ALL)
            db.upsert_email(state["current_email"].id, status="failed",
                             error=f"Max rewrite trials ({settings.max_rewrite_trials}) reached")
            db.log_event(state["current_email"].id, "must_rewrite", "Max trials reached, giving up", level="warn")
            state["emails"].pop()
            state["writer_messages"] = []
            return "stop"
        else:
            print(Fore.RED + "Email is not good, must rewrite it..." + Style.RESET_ALL)
            return "rewrite"

    def create_draft_response(self, state: GraphState) -> GraphState:
        """Creates a draft response in Gmail (does NOT send it — a human
        approves and sends from the dashboard)."""
        print(Fore.YELLOW + "Creating draft email...\n" + Style.RESET_ALL)
        try:
            self.gmail_tools.create_draft_reply(state["current_email"], state["generated_email"])
            db.upsert_email(state["current_email"].id, status="draft_created")
            db.log_event(state["current_email"].id, "create_draft_response", "Gmail draft created")
        except Exception as e:
            db.upsert_email(state["current_email"].id, status="failed", error=str(e))
            db.log_event(state["current_email"].id, "create_draft_response", str(e), level="error")

        return {"retrieved_documents": "", "trials": 0}

    def send_email_response(self, state: GraphState) -> GraphState:
        """Sends the email response directly using Gmail."""
        print(Fore.YELLOW + "Sending email...\n" + Style.RESET_ALL)
        try:
            self.gmail_tools.send_reply(state["current_email"], state["generated_email"])
            db.upsert_email(state["current_email"].id, status="sent")
            db.log_event(state["current_email"].id, "send_email_response", "Sent")
        except Exception as e:
            db.upsert_email(state["current_email"].id, status="failed", error=str(e))
            db.log_event(state["current_email"].id, "send_email_response", str(e), level="error")

        return {"retrieved_documents": "", "trials": 0}

    def skip_unrelated_email(self, state):
        """Skip unrelated email and remove from emails list."""
        print("Skipping unrelated email...\n")
        current = state["emails"][-1] if state["emails"] else state.get("current_email")
        if current is not None:
            db.upsert_email(current.id, status="skipped", category="unrelated")
            db.log_event(current.id, "skip_unrelated_email", "Unrelated, skipped")
        if state["emails"]:
            state["emails"].pop()
        state["_error"] = False
        return state

    def check_error(self, state: GraphState) -> str:
        """Generic router used after any fallible node: continue normally,
        or bail out to the error handler if that node just failed."""
        return "error" if state.get("_error") else "ok"

    def handle_processing_error(self, state: GraphState) -> GraphState:

        """No-op passthrough node used purely as a routing target after a
        failed processing step, so the graph can loop back to check the
        next email instead of crashing the whole run."""
        state["_error"] = False
        return state
