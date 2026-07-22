from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from .structure_outputs import *
from .prompts import *
from .config import settings


class LLMUnavailableError(RuntimeError):
    """Raised when neither retries nor fallbacks can get a usable response
    from a model provider. Callers should catch this and mark the current
    email as failed rather than crashing the whole workflow."""


def _with_retry(fn):
    """Wrap a `.invoke`-style call with sane retries for transient network
    issues (Ollama cold-start, Groq rate limiting) without masking real
    programming errors."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(settings.llm_max_retries),
        wait=wait_exponential(multiplier=settings.llm_retry_base_seconds, min=1, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, ConnectionError, TimeoutError)),
    )(fn)


class Agents:
    """
    Model orchestration strategy:
      - Ollama (qwen2.5:1.5b, local & free) handles the cheap, high-volume,
        low-risk decisions: categorizing an email and drafting RAG search
        queries. These are short classification-style tasks where a small
        local model is plenty accurate and keeps hosted API costs down.
      - Groq (llama-3.3-70b-versatile, hosted) handles everything that is
        customer-facing or needs stronger reasoning: synthesizing the RAG
        answer, writing the draft reply, and proofreading it before send.
      - Ollama (nomic-embed-text) provides embeddings for the vector store,
        so the whole RAG pipeline runs locally with no per-query API cost.
    """

    def __init__(self):
        router_llm = ChatOllama(
            model=settings.ollama_llm_model,
            base_url=settings.ollama_base_url,
            temperature=0.1,
        )
        writer_llm = ChatGroq(
            model_name=settings.groq_model,
            temperature=0.1,
            api_key=settings.groq_api_key or None,
        )

        embeddings = OllamaEmbeddings(
            model=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
        )
        vectorstore = Chroma(
            persist_directory=settings.chroma_persist_dir,
            embedding_function=embeddings,
        )
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

        # --- Categorize email (Ollama: cheap classification) ---
        email_category_prompt = PromptTemplate(
            template=CATEGORIZE_EMAIL_PROMPT, input_variables=["email"]
        )
        categorize_chain = (
            email_category_prompt | router_llm.with_structured_output(CategorizeEmailOutput)
        )
        self.categorize_email = _with_retry(categorize_chain.invoke)

        # --- Design RAG queries (Ollama: cheap classification) ---
        generate_query_prompt = PromptTemplate(
            template=GENERATE_RAG_QUERIES_PROMPT, input_variables=["email"]
        )
        design_queries_chain = (
            generate_query_prompt | router_llm.with_structured_output(RAGQueriesOutput)
        )
        self.design_rag_queries = _with_retry(design_queries_chain.invoke)

        # --- Generate RAG answer (Groq: needs to be right, it's customer-facing) ---
        qa_prompt = ChatPromptTemplate.from_template(GENERATE_RAG_ANSWER_PROMPT)
        rag_answer_chain = (
            {"context": retriever, "question": RunnablePassthrough()}
            | qa_prompt
            | writer_llm
            | StrOutputParser()
        )
        self.generate_rag_answer = _with_retry(rag_answer_chain.invoke)

        # --- Write draft email (Groq: customer-facing writing) ---
        writer_prompt = ChatPromptTemplate.from_messages([
            ("system", EMAIL_WRITER_PROMPT),
            MessagesPlaceholder("history"),
            ("human", "{email_information}"),
        ])
        writer_chain = writer_prompt | writer_llm.with_structured_output(WriterOutput)
        self.email_writer = _with_retry(writer_chain.invoke)

        # --- Proofread email (Groq: quality gate before send) ---
        proofreader_prompt = PromptTemplate(
            template=EMAIL_PROOFREADER_PROMPT,
            input_variables=["initial_email", "generated_email"],
        )
        proofreader_chain = (
            proofreader_prompt | writer_llm.with_structured_output(ProofReaderOutput)
        )
        self.email_proofreader = _with_retry(proofreader_chain.invoke)
