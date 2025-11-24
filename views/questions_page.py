import streamlit as st
from db import get_questions, insert_question, update_question, delete_question


def show():
    # Admin gate
    user = st.session_state.get("user")
    if not user or user.get("role") != "admin":
        st.error("Admin access required.")
        st.stop()

    st.header("Manage Questions")

    render_add_form()
    render_question_list()


def render_add_form():
    st.subheader("Add a question")
    with st.form("add_question"):
        prompt = st.text_input("Question prompt")
        submitted = st.form_submit_button("Add question")
        if submitted:
            if not prompt.strip():
                st.error("Prompt is required.")
            else:
                insert_question(prompt.strip())
                st.success("Question added.")
                st.rerun()


def render_question_list():
    st.subheader("Current questions")
    questions = get_questions()
    if not questions:
        st.info("No questions yet.")
        return

    for q in questions:
        with st.expander(f"{q['prompt']}"):
            render_edit_form(q)
            render_delete_form(q)


def render_edit_form(question):
    with st.form(f"edit_q_{question['id']}"):
        prompt_val = st.text_input("Prompt", value=question["prompt"])
        save = st.form_submit_button("Save changes")
        if save:
            if not prompt_val.strip():
                st.error("Prompt is required.")
            else:
                update_question(question["id"], prompt_val.strip())
                st.success("Question updated.")
                st.rerun()


def render_delete_form(question):
    with st.form(f"delete_q_{question['id']}"):
        st.write("Delete this question and its answers?")
        delete_pressed = st.form_submit_button("Delete question")
        if delete_pressed:
            delete_question(question["id"])
            st.success("Question deleted.")
            st.rerun()
