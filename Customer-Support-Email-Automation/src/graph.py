from langgraph.graph import END, StateGraph
from .state import GraphState
from .nodes import Nodes


class Workflow():
    def __init__(self):
        workflow = StateGraph(GraphState)
        nodes = Nodes()

        # graph nodes
        workflow.add_node("load_inbox_emails", nodes.load_new_emails)
        workflow.add_node("is_email_inbox_empty", nodes.is_email_inbox_empty)
        workflow.add_node("categorize_email", nodes.categorize_email)
        workflow.add_node("construct_rag_queries", nodes.construct_rag_queries)
        workflow.add_node("retrieve_from_rag", nodes.retrieve_from_rag)
        workflow.add_node("email_writer", nodes.write_draft_email)
        workflow.add_node("email_proofreader", nodes.verify_generated_email)
        workflow.add_node("send_email", nodes.create_draft_response)
        workflow.add_node("skip_unrelated_email", nodes.skip_unrelated_email)
        workflow.add_node("handle_processing_error", nodes.handle_processing_error)

        workflow.set_entry_point("load_inbox_emails")

        workflow.add_edge("load_inbox_emails", "is_email_inbox_empty")
        workflow.add_conditional_edges(
            "is_email_inbox_empty",
            nodes.check_new_emails,
            {"process": "categorize_email", "empty": END},
        )

        # route email based on category (or bail out if categorization itself failed)
        workflow.add_conditional_edges(
            "categorize_email",
            nodes.route_email_based_on_category,
            {
                "product related": "construct_rag_queries",
                "not product related": "email_writer",  # Feedback or Complaint
                "unrelated": "skip_unrelated_email",
                "error": "handle_processing_error",
            },
        )

        # every fallible step gets a conditional edge so a single bad email
        # (model timeout, malformed content, etc.) can't wedge the whole run
        workflow.add_conditional_edges(
            "construct_rag_queries",
            nodes.check_error,
            {"ok": "retrieve_from_rag", "error": "handle_processing_error"},
        )
        workflow.add_conditional_edges(
            "retrieve_from_rag",
            nodes.check_error,
            {"ok": "email_writer", "error": "handle_processing_error"},
        )
        workflow.add_conditional_edges(
            "email_writer",
            nodes.check_error,
            {"ok": "email_proofreader", "error": "handle_processing_error"},
        )

        # check if email is sendable, needs a rewrite, or ran out of trials
        workflow.add_conditional_edges(
            "email_proofreader",
            nodes.must_rewrite,
            {
                "send": "send_email",
                "rewrite": "email_writer",
                "stop": "handle_processing_error",
            },
        )

        workflow.add_edge("send_email", "is_email_inbox_empty")
        workflow.add_edge("skip_unrelated_email", "is_email_inbox_empty")
        workflow.add_edge("handle_processing_error", "is_email_inbox_empty")

        self.app = workflow.compile()
