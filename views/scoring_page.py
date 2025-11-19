import streamlit as st
from db import get_judges, get_competitors, replace_scores_for_judge, get_scores_for_judge

def show():
    st.header("Enter Scores")

    # Load judges and competitors
    judges = get_judges()
    competitors = get_competitors()

    if not judges:
        st.warning("Add judges first.")
        return
    if not competitors:
        st.warning("Add competitors first.")
        return

    # Dropdown for selecting judge
    judge_map = {f"{j['name']} ({j['email']})": j["id"] for j in judges}
    selected = st.selectbox("Select judge", list(judge_map.keys()))
    judge_id = judge_map[selected]

    # Fetch this judge's existing scores
    existing_scores = get_scores_for_judge(judge_id)

    st.write("---")
    st.write("Enter scores for each competitor:")

    scores = {}

    # Form to submit all scores at once
    with st.form("score_form"):
        for c in competitors:
            col1, col2 = st.columns([2, 1])

            # Competitor info
            with col1:
                st.write(f"**{c['name']}**")

            # Score input, pre-filled with existing score if available
            with col2:
                value = st.number_input(
                    f"Score (ID {c['id']})",
                    min_value=0.0,
                    max_value=100.0,
                    step=0.5,
                    value=float(existing_scores.get(c["id"], 0.0)),
                    # key includes judge_id so each judge gets independent widgets
                    key=f"score_{judge_id}_{c['id']}"
                )
                scores[c["id"]] = value

        submitted = st.form_submit_button("Save scores")

        if submitted:
            # Only save non-zero scores
            cleaned = {cid: val for cid, val in scores.items() if val > 0}
            replace_scores_for_judge(judge_id, cleaned)
            st.success("Scores saved!")
