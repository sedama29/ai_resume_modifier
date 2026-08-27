import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

import db.repository as repo
from app.auth import authz
from app.state import get_db, render_user_badge, require_superuser, require_user
from config import GROQ_INPUT_PRICE_PER_1M, GROQ_OUTPUT_PRICE_PER_1M

st.set_page_config(page_title="Admin: API Usage", page_icon="📈", layout="wide")

from app.styling import inject_custom_css, page_header
inject_custom_css()

db = get_db()
user = require_user()
require_superuser(user)
render_user_badge(user)

page_header(
    "📈", "Admin: Groq API Usage",
    f"Estimated cost uses ${GROQ_INPUT_PRICE_PER_1M}/1M input + ${GROQ_OUTPUT_PRICE_PER_1M}/1M output tokens "
    "for openai/gpt-oss-120b -- verify against console.groq.com/docs/models if this matters precisely.",
)

rows = repo.list_api_usage(db)
if not rows:
    st.info("No API usage recorded yet.")
    st.stop()

df = pd.DataFrame(rows)
df["created_at"] = pd.to_datetime(df["created_at"])
df["date"] = df["created_at"].dt.date

uid_to_email = {u["uid"]: u["email"] for u in authz.list_users() if u.get("uid")}
df["user_email"] = df["owner_uid"].map(uid_to_email).fillna(df["owner_uid"])

df["estimated_cost"] = (
    df["prompt_tokens"].fillna(0) / 1_000_000 * GROQ_INPUT_PRICE_PER_1M
    + df["completion_tokens"].fillna(0) / 1_000_000 * GROQ_OUTPUT_PRICE_PER_1M
)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Requests", len(df))
col2.metric("Input tokens", f"{int(df['prompt_tokens'].fillna(0).sum()):,}")
col3.metric("Output tokens", f"{int(df['completion_tokens'].fillna(0).sum()):,}")
col4.metric("Total tokens", f"{int(df['total_tokens'].fillna(0).sum()):,}")
col5.metric("Estimated cost", f"${df['estimated_cost'].sum():.4f}")

st.subheader("Usage by date")
by_date = df.groupby("date").agg(
    requests=("created_at", "count"),
    total_tokens=("total_tokens", "sum"),
    estimated_cost=("estimated_cost", "sum"),
).sort_index(ascending=False)
st.dataframe(by_date, use_container_width=True)

st.subheader("Usage by user")
by_user = df.groupby("user_email").agg(
    requests=("created_at", "count"),
    total_tokens=("total_tokens", "sum"),
    estimated_cost=("estimated_cost", "sum"),
).sort_values("requests", ascending=False)
st.dataframe(by_user, use_container_width=True)

with st.expander("Raw log"):
    st.dataframe(
        df[["created_at", "user_email", "schema_name", "model", "prompt_tokens", "completion_tokens", "total_tokens"]],
        use_container_width=True,
    )
