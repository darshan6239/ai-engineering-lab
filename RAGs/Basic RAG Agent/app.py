import streamlit as st

from rag import ask_rag

st.set_page_config(
    page_title="Basic RAG Agent",
    page_icon="",
    layout="wide"
)

st.title("Basic RAG Agent")
question = st.text_input(
    "Ask a question about your documents"
)
if st.button("Ask"):

    if question.strip():

        with st.spinner("Searching..."):

            answer, sources = ask_rag(question)

        st.subheader("Answer")

        st.write(answer)

        st.subheader("Sources")

        for source in sources:
            st.write(source)