"""Streamlit frontend for the Employee Leave Management System.

Compared to the original version, every API call now sends the JWT
issued at login in an Authorization header, and error messages from the
backend (validation errors, 403s, 404s) are shown to the user instead of
being silently ignored.
"""

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8001"

st.set_page_config(
    page_title="Employee Leave Management", page_icon="🏢", layout="wide"
)

st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg, #0f172a, #020617); color: white; }
    section[data-testid="stSidebar"] { background-color: #111827; }
    .main-title { font-size: 42px; font-weight: 700; color: white; }
    .sub-title { color: #94a3b8; font-size: 18px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def auth_headers() -> dict:
    """Build the Authorization header from the token stored in session state."""
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_get(path: str) -> requests.Response:
    return requests.get(f"{API_URL}{path}", headers=auth_headers())


def api_post(path: str, json_body: dict) -> requests.Response:
    return requests.post(f"{API_URL}{path}", json=json_body, headers=auth_headers())


def api_put(path: str, json_body: dict) -> requests.Response:
    return requests.put(f"{API_URL}{path}", json=json_body, headers=auth_headers())


def show_api_error(response: requests.Response) -> None:
    """Display a backend error (validation, 403, 404, ...) in a readable form."""
    try:
        detail = response.json().get("detail", "Something went wrong.")
    except ValueError:
        detail = "Something went wrong."

    if isinstance(detail, list):
        # FastAPI/Pydantic validation errors come back as a list of objects.
        messages = [error.get("msg", str(error)) for error in detail]
        st.error("\n".join(messages))
    else:
        st.error(detail)


st.markdown(
    """
    <div class='main-title'>🏢 Employee Leave Management System</div>
    <div class='sub-title'>Manage employee leave requests efficiently</div>
    <br>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Login screen
# ---------------------------------------------------------------------------
if "user" not in st.session_state:
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("## 🔐 Login")

        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):
            response = requests.post(
                f"{API_URL}/login", json={"email": email, "password": password}
            )

            if response.status_code == 200:
                data = response.json()
                st.session_state.user = {
                    "id": data["id"],
                    "name": data["name"],
                    "role": data["role"],
                }
                st.session_state.token = data["access_token"]
                st.rerun()
            else:
                show_api_error(response)

        st.markdown("---")
        st.info(
            """
            ### Demo Accounts

            **Employee:** employee@gmail.com / 1234

            **Manager:** manager@gmail.com / 1234
            """
        )

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
else:
    user = st.session_state.user

    st.sidebar.title("🏢 Leave Portal")
    st.sidebar.success(f"Logged in as\n\n**{user['name']}**\n\n({user['role']})")

    if st.sidebar.button("🚪 Logout"):
        del st.session_state["user"]
        del st.session_state["token"]
        st.rerun()

    # ---- Employee dashboard ----
    if user["role"] == "employee":
        history_response = api_get(f"/leave_history/{user['id']}")
        history = (
            history_response.json() if history_response.status_code == 200 else []
        )

        total = len(history)
        approved = len([item for item in history if item["status"] == "Approved"])
        pending = len([item for item in history if item["status"] == "Pending"])

        st.header("👨‍💼 Employee Dashboard")

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Leaves", total)
        col2.metric("Approved", approved)
        col3.metric("Pending", pending)

        st.markdown("---")
        st.subheader("📝 Apply New Leave")

        col1, col2 = st.columns(2)
        start = col1.date_input("Start Date")
        end = col2.date_input("End Date")
        reason = st.text_area("Reason")

        if st.button("Apply Leave"):
            response = api_post(
                "/apply_leave",
                {
                    "start_date": str(start),
                    "end_date": str(end),
                    "reason": reason,
                },
            )

            if response.status_code == 201:
                st.success("Leave Applied Successfully")
                st.rerun()
            else:
                show_api_error(response)

        st.markdown("---")
        st.subheader("📜 Leave History")

        if history:
            st.dataframe(pd.DataFrame(history), use_container_width=True)
        else:
            st.info("No leave records found")

    # ---- Manager dashboard ----
    elif user["role"] == "manager":
        leaves_response = api_get("/all_leaves")
        leaves = leaves_response.json() if leaves_response.status_code == 200 else []

        approved = len([item for item in leaves if item["status"] == "Approved"])
        rejected = len([item for item in leaves if item["status"] == "Rejected"])
        pending = len([item for item in leaves if item["status"] == "Pending"])

        st.header("📋 Manager Dashboard")

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Requests", len(leaves))
        col2.metric("Approved", approved)
        col3.metric("Pending", pending)

        st.markdown("---")
        st.subheader("📑 All Leave Requests")

        if leaves:
            st.dataframe(pd.DataFrame(leaves), use_container_width=True)
        else:
            st.info("No leave requests found")

        st.markdown("---")
        st.subheader("✅ Approve / Reject Leave")

        col1, col2 = st.columns(2)
        leave_id = col1.number_input("Leave ID", min_value=1, step=1)
        new_status = col2.selectbox("Status", ["Approved", "Rejected"])

        if st.button("Update Status"):
            response = api_put(f"/update_leave/{int(leave_id)}", {"status": new_status})

            if response.status_code == 200:
                st.success(f"Leave #{int(leave_id)} updated to {new_status}")
                st.rerun()
            else:
                show_api_error(response)

        st.markdown("---")
        st.subheader("📊 Leave Statistics")

        stats_df = pd.DataFrame(
            {
                "Status": ["Approved", "Rejected", "Pending"],
                "Count": [approved, rejected, pending],
            }
        )

        col1, col2 = st.columns(2)
        col1.dataframe(stats_df, use_container_width=True)

        with col2:
            fig = px.pie(
                stats_df,
                values="Count",
                names="Status",
                hole=0.5,
                title="Leave Distribution",
            )
            st.plotly_chart(fig, use_container_width=True)
