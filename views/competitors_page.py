import streamlit as st
from db import get_competitors, insert_competitor

def show():
    st.header("Manage Competitors")

    # Form to add a new competitor
    with st.form("add_competitor"):
        name = st.text_input("Competitor name")
        submitted = st.form_submit_button("Add competitor")

        if submitted:
            if not name.strip():
                st.error("Name is required.")
            else:
                insert_competitor(name.strip())
                st.success(f"Added competitor: {name}")

    st.subheader("Current competitors")

    # Load and display competitor list
    competitors = get_competitors()
    if competitors:
        st.table([dict(row) for row in competitors])
    else:
        st.info("No competitors yet.")
