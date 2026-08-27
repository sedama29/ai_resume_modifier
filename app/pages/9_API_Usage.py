import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

import db.repository as repo
from app.auth import authz
from app.state import get_db, render_user_badge, require_superuser, require_user
from config import GROQ_INPUT_PRICE_PER_1M, GROQ_OUTPUT_PRICE_PER_1M


from app.styling import inject_custom_css, page_header
inject_custom_css()

db = get_db()
user = require_user()
require_superuser(user)
render_user_badge(user)

page_header(
    "Groq API Usage",
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

def _summarize(subset: pd.DataFrame) -> tuple[int, float, float]:
    requests = len(subset)
    tokens = float(subset["total_tokens"].fillna(0).sum())
    cost = float(subset["estimated_cost"].sum())
    return requests, tokens, cost


def _fmt_tokens(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:.0f}"


now = datetime.now(timezone.utc)
today_mask = df["created_at"].dt.date == now.date()
month_mask = (df["created_at"].dt.year == now.year) & (df["created_at"].dt.month == now.month)

today_req, today_tok, today_cost = _summarize(df[today_mask])
month_req, month_tok, month_cost = _summarize(df[month_mask])
all_req, all_tok, all_cost = _summarize(df)

st.markdown("**Today**")
c1, c2, c3 = st.columns(3)
c1.metric("Requests", today_req)
c2.metric("Tokens", _fmt_tokens(today_tok))
c3.metric("Estimated cost", f"${today_cost:.2f}")

st.write("")
st.markdown("**This month**")
c1, c2, c3 = st.columns(3)
c1.metric("Requests", month_req)
c2.metric("Tokens", _fmt_tokens(month_tok))
c3.metric("Estimated cost", f"${month_cost:.2f}")

st.write("")
st.markdown("**All time**")
c1, c2, c3 = st.columns(3)
c1.metric("Requests", all_req)
c2.metric("Tokens", _fmt_tokens(all_tok))
c3.metric("Estimated cost", f"${all_cost:.2f}")

st.write("")
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
