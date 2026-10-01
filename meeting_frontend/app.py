import streamlit as st
import requests
import os
import json
import uuid

# API Base URL
API_BASE = "http://localhost:8000/api/v1"

# Timeouts
DEFAULT_TIMEOUT = 15
LLM_TIMEOUT = 60

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Meeting Assistant",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={},
)

st.markdown("""
<style>
    .main { background-color: #0f172a; }
    .stApp { background-color: #0f172a; }
    h1, h2, h3, h4 { color: #e2e8f0 !important; font-weight: 600; }

    .stButton>button {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white; border: none; border-radius: 12px;
        padding: 12px 24px; font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(99,102,241,0.3);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(99,102,241,0.4);
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    }

    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea {
        background-color: #1e293b; color: #e2e8f0;
        border: 1px solid #334155; border-radius: 12px; padding: 12px;
    }
    .stTextInput>div>div>input:focus,
    .stTextArea>div>div>textarea:focus { border-color: #6366f1; }

    .stFileUploader {
        background-color: #1e293b; border: 2px dashed #334155;
        border-radius: 12px; padding: 20px;
    }
    .stExpander { background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; margin: 10px 0; }
    .stExpanderHeader { color: #e2e8f0 !important; }

    .status-completed {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white; padding: 6px 16px; border-radius: 20px;
        font-weight: 600; box-shadow: 0 2px 4px rgba(16,185,129,0.3);
    }
    .status-processing {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white; padding: 6px 16px; border-radius: 20px;
        font-weight: 600; box-shadow: 0 2px 4px rgba(245,158,11,0.3);
    }
    .status-failed {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white; padding: 6px 16px; border-radius: 20px;
        font-weight: 600; box-shadow: 0 2px 4px rgba(239,68,68,0.3);
    }

    p, span, div { color: #cbd5e1 !important; }
    [data-testid="stMetricValue"] { color: #e2e8f0 !important; font-size: 2rem; font-weight: 700; }
    [data-testid="stMetricLabel"] { color: #94a3b8 !important; }
    .css-1d391kg { background-color: #0f172a; }
    textarea { color: #e2e8f0 !important; background-color: #1e293b !important; }

    .stSuccess { background-color: rgba(16,185,129,0.1); border-left: 4px solid #10b981; color: #10b981; }
    .stInfo    { background-color: rgba(59,130,246,0.1);  border-left: 4px solid #3b82f6; color: #3b82f6; }
    .stWarning { background-color: rgba(245,158,11,0.1);  border-left: 4px solid #f59e0b; color: #f59e0b; }
    .stError   { background-color: rgba(239,68,68,0.1);   border-left: 4px solid #ef4444; color: #ef4444; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #1e293b; border-radius: 12px;
        padding: 4px; border: 1px solid #334155;
        gap: 4px; margin-bottom: 16px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px; color: #94a3b8;
        font-weight: 500; padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# ─── Session state init ────────────────────────────────────────────────────────
for key, default in [
    ("token", ""),
    ("is_authenticated", False),
    ("user_id", 0),
    ("current_page", "login"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

TOKEN_FILE = ".session_token.json"

# Load persisted token exactly once per browser session
if not st.session_state.token:
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                saved = json.load(f)
                if saved.get("token"):
                    st.session_state.token = saved["token"]
                    st.session_state.is_authenticated = True
                    st.session_state.user_id = saved.get("user_id", 0)
                    st.session_state.current_page = "meetings"
    except Exception:
        pass

# ─── Helpers ──────────────────────────────────────────────────────────────────

def set_page(page: str):
    st.session_state.current_page = page


def logout():
    st.session_state.token = ""
    st.session_state.is_authenticated = False
    st.session_state.user_id = 0
    for k in list(st.session_state.keys()):
        if any(k.startswith(p) for p in (
            "meeting_cache_", "meeting_loaded_",
            "meetings_list", "chat_history_",
            "frontend_qa_cache_", "meeting_questions_",
            "coaching_report_",
        )):
            del st.session_state[k]
    set_page("login")
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
    except Exception:
        pass


def handle_unauthorized(response) -> bool:
    if response.status_code != 401:
        return False
    st.session_state.token = ""
    st.session_state.is_authenticated = False
    st.session_state.user_id = 0
    st.session_state.current_page = "login"
    st.session_state.auth_message = "Your login expired. Please sign in again."
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
    except OSError:
        pass
    st.rerun()
    return True


def _headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


# ─── API calls ────────────────────────────────────────────────────────────────

def login_api(email: str, password: str):
    try:
        r = requests.post(f"{API_BASE}/auth/login",
                          data={"username": email, "password": password},
                          timeout=DEFAULT_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            st.session_state.token = data["access_token"]
            st.session_state.is_authenticated = True
            set_page("meetings")
            try:
                with open(TOKEN_FILE, "w") as f:
                    json.dump({"token": st.session_state.token,
                               "user_id": st.session_state.user_id}, f)
            except Exception:
                pass
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Login failed. Please check your credentials.")
    except requests.Timeout:
        st.error("Request timed out. Is the backend running?")
    except Exception as e:
        st.error(f"Error: {e}")


def register_api(email: str, username: str, password: str):
    try:
        r = requests.post(f"{API_BASE}/auth/register",
                          json={"email": email, "username": username, "password": password},
                          timeout=DEFAULT_TIMEOUT)
        if r.status_code == 201:
            st.success("Registration successful! Please login.")
            set_page("login")
            st.rerun()
        else:
            st.error(f"Registration failed: {r.json().get('detail', 'Unknown error')}")
    except requests.Timeout:
        st.error("Request timed out.")
    except Exception as e:
        st.error(f"Error: {e}")


def get_meetings():
    """
    Fetch meetings list once per session; cached in session_state.
    Call invalidate_meetings_cache() when a stale list is needed.
    """
    if "meetings_list" in st.session_state:
        return st.session_state["meetings_list"]
    try:
        r = requests.get(f"{API_BASE}/meetings/", headers=_headers(), timeout=DEFAULT_TIMEOUT)
        if handle_unauthorized(r):
            return []
        if r.status_code == 200:
            payload = r.json()
            result = [m for m in payload if isinstance(m, dict)] if isinstance(payload, list) else []
            st.session_state["meetings_list"] = result
            return result
        return []
    except requests.Timeout:
        st.warning("Meetings list timed out.")
        return []
    except Exception as e:
        st.error(f"Error: {e}")
        return []


def invalidate_meetings_cache():
    st.session_state.pop("meetings_list", None)


def upload_meeting_api(title: str, description: str, audio_file):
    try:
        r = requests.post(
            f"{API_BASE}/meetings/",
            headers=_headers(),
            files={"audio_file": (audio_file.name, audio_file, audio_file.type)},
            data={"title": title, "description": description},
            timeout=120,
        )
        if handle_unauthorized(r):
            return None
        if r.status_code == 201:
            invalidate_meetings_cache()
            st.success("Meeting uploaded successfully!")
            return r.json()
        elif r.status_code == 422:
            st.error(f"Upload failed: {r.text}")
            return None
        else:
            st.error(f"Upload failed. Status: {r.status_code}, Response: {r.text}")
            return None
    except requests.Timeout:
        st.error("Upload timed out.")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def fetch_meeting(meeting_id: int):
    """Raw fetch — caller decides caching."""
    try:
        r = requests.get(f"{API_BASE}/meetings/{meeting_id}",
                         headers=_headers(), timeout=DEFAULT_TIMEOUT)
        if handle_unauthorized(r):
            return None
        return r.json() if r.status_code == 200 else None
    except requests.Timeout:
        st.warning("Meeting fetch timed out.")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def update_meeting_api(meeting_id: int, title: str, description: str):
    try:
        r = requests.patch(
            f"{API_BASE}/meetings/{meeting_id}",
            json={"title": title, "description": description or None},
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        if handle_unauthorized(r):
            return None
        if r.status_code == 200:
            invalidate_meetings_cache()
            return r.json()
        st.error(f"Update failed: {r.json().get('detail', 'Unknown error')}")
    except requests.Timeout:
        st.error("Update timed out.")
    except Exception as e:
        st.error(f"Error: {e}")
    return None


def delete_meeting_api(meeting_id: int) -> bool:
    try:
        r = requests.delete(f"{API_BASE}/meetings/{meeting_id}",
                            headers=_headers(), timeout=DEFAULT_TIMEOUT)
        if handle_unauthorized(r):
            return False
        if r.status_code == 204:
            invalidate_meetings_cache()
            st.session_state.pop(f"meeting_cache_{meeting_id}", None)
            st.session_state.pop(f"meeting_loaded_{meeting_id}", None)
            return True
        st.error(f"Delete failed: {r.json().get('detail', 'Unknown error')}")
    except requests.Timeout:
        st.error("Delete timed out.")
    except Exception as e:
        st.error(f"Error: {e}")
    return False


def ask_question_api(meeting_id: int, question: str, history: list = None):
    try:
        payload = {"question_text": question}
        if history:
            payload["history"] = history
        r = requests.post(
            f"{API_BASE}/meetings/{meeting_id}/questions",
            json=payload, headers=_headers(), timeout=LLM_TIMEOUT,
        )
        if handle_unauthorized(r):
            return None
        if r.status_code == 200:
            return r.json()
        st.error(f"Error: {r.json().get('detail', r.text[:200])}")
        return None
    except requests.Timeout:
        st.error("The AI took too long to respond. Please try again.")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def get_coaching_api(meeting_id: int):
    try:
        r = requests.post(f"{API_BASE}/meetings/{meeting_id}/coaching",
                          headers=_headers(), timeout=LLM_TIMEOUT)
        if handle_unauthorized(r):
            return None
        if r.status_code == 200:
            return r.json()
        st.error("Could not generate coaching at this time.")
        return None
    except requests.Timeout:
        st.error("Coaching analysis timed out. Please try again.")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def get_questions_api(meeting_id: int):
    try:
        r = requests.get(f"{API_BASE}/meetings/{meeting_id}/questions",
                         headers=_headers(), timeout=DEFAULT_TIMEOUT)
        if handle_unauthorized(r):
            return []
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def format_talk_improvement(imp) -> str:
    if isinstance(imp, dict):
        area = imp.get("area") or imp.get("title") or "Recommendation"
        advice = imp.get("advice") or imp.get("description") or ""
        return f"**{area}**: {advice}" if advice else f"**{area}**"
    elif isinstance(imp, str) and ("'area':" in imp or '"area":' in imp):
        try:
            import ast
            d = ast.literal_eval(imp)
            if isinstance(d, dict):
                area = d.get("area") or d.get("title") or "Recommendation"
                advice = d.get("advice") or d.get("description") or ""
                return f"**{area}**: {advice}" if advice else f"**{area}**"
        except Exception:
            pass
    return str(imp)


# ─── Pages ────────────────────────────────────────────────────────────────────

def login_page():
    auth_message = st.session_state.pop("auth_message", None)
    if auth_message:
        st.warning(auth_message)

    st.markdown("<h1 style='text-align:center;color:white;'>Meeting AI Assistant</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:white;font-size:20px;'>Transform your meetings into searchable knowledge</p>", unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center;color:white;'>Login</h2>", unsafe_allow_html=True)

    email = st.text_input("Email", placeholder="Enter your email")
    password = st.text_input("Password", type="password", placeholder="Enter your password")
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Login", use_container_width=True):
            if email and password:
                login_api(email, password)
            else:
                st.warning("Please fill in all fields.")
    with c2:
        if st.button("Register", use_container_width=True):
            set_page("register")
            st.rerun()


def register_page():
    st.markdown("<h1 style='text-align:center;color:white;'>Meeting AI Assistant</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:white;font-size:20px;'>Transform your meetings into searchable knowledge</p>", unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center;color:white;'>Create Account</h2>", unsafe_allow_html=True)

    email = st.text_input("Email", placeholder="Enter your email")
    username = st.text_input("Username", placeholder="Choose a username")
    password = st.text_input("Password", type="password", placeholder="Create a password")
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Register", use_container_width=True):
            if email and username and password:
                register_api(email, username, password)
            else:
                st.warning("Please fill in all fields.")
    with c2:
        if st.button("Back", use_container_width=True):
            set_page("login")
            st.rerun()


def meeting_list_page():
    st.markdown("<h1 style='color:white;'>My Meetings</h1>", unsafe_allow_html=True)

    meetings = get_meetings()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Meetings", len(meetings))
    c2.metric("Completed", len([m for m in meetings if m.get("status") == "completed"]))
    c3.metric("Processing", len([m for m in meetings if m.get("status") == "processing"]))
    c4.metric("Failed", len([m for m in meetings if m.get("status") == "failed"]))

    st.markdown("<br>", unsafe_allow_html=True)

    if not meetings:
        st.markdown("<h3 style='text-align:center;color:white;'>No meetings yet!</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:white;'>Upload your first meeting to get started</p>", unsafe_allow_html=True)
        return

    cols = st.columns(3)
    for idx, meeting in enumerate(meetings):
        col = cols[idx % 3]
        meeting_id = meeting.get("id")
        status = str(meeting.get("status") or "unknown").lower()
        title = meeting.get("title") or "Untitled meeting"
        description = meeting.get("description") or "No description"
        created_at = meeting.get("created_at") or "N/A"
        with col:
            st.markdown(f"<h3 style='color:white;margin-bottom:10px;'>{title}</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='color:#cbd5e1;font-size:14px;margin-bottom:5px;'>{description[:50]}...</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='color:#94a3b8;font-size:12px;'>Created: {created_at}</p>", unsafe_allow_html=True)
            st.markdown(f"<span class='status-{status}'>{status.upper()}</span>", unsafe_allow_html=True)
            if meeting_id is not None and st.button("View", key=f"view_{meeting_id}", use_container_width=True):
                st.session_state.selected_meeting_id = meeting_id
                st.session_state.current_page = "meeting_detail"
                st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)


def upload_page():
    st.markdown("<h1 style='color:white;'>Upload Meeting</h1>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:white;'>Upload Audio</h2>", unsafe_allow_html=True)

    title = st.text_input("Meeting Title", placeholder="Enter meeting title")
    description = st.text_area("Description (optional)", placeholder="Add a description...")
    audio_file = st.file_uploader(
        "Select Audio File",
        type=["mp3", "wav", "m4a", "mp4", "aac", "flac", "ogg", "opus", "webm"],
        help="Automatic language detection is enabled.",
    )

    if audio_file:
        st.success(f"Selected: {audio_file.name}")
        st.info(f"Size: {audio_file.size / (1024*1024):.2f} MB")

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Upload", use_container_width=True):
            if title and audio_file:
                with st.spinner("Uploading and processing..."):
                    result = upload_meeting_api(title, description, audio_file)
                    if result:
                        st.success("Meeting uploaded! Processing will take a few minutes.")
                        st.session_state.current_page = "meetings"
                        invalidate_meetings_cache()
                        st.rerun()
            else:
                st.warning("Please provide a title and select an audio file.")
    with c2:
        if st.button("Back", use_container_width=True):
            st.session_state.current_page = "meetings"
            st.rerun()


def meeting_detail_page():
    """
    Meeting detail page.
    - Meeting data is fetched ONCE per meeting_id and stored permanently in session state.
    - No refresh buttons anywhere — the user uses the Back button and re-opens to get fresh data.
    - st.chat_input is handled safely so it never triggers extra API calls.
    """
    meeting_id = st.session_state.get("selected_meeting_id")
    if not meeting_id:
        # No meeting selected — show a button to go back rather than auto-navigating
        # (auto st.rerun() here can cause infinite loops if session state is inconsistent)
        set_page("meetings")
        st.info("No meeting selected.")
        if st.button("Go to My Meetings", key="btn_no_meeting"):
            st.rerun()
        return

    cache_key   = f"meeting_cache_{meeting_id}"
    loaded_key  = f"meeting_loaded_{meeting_id}"   # separate boolean flag

    # Fetch once; the loaded_key flag ensures we never re-fetch on reruns
    if not st.session_state.get(loaded_key):
        with st.spinner("Loading meeting..."):
            meeting = fetch_meeting(meeting_id)
        if meeting:
            st.session_state[cache_key]  = meeting
            st.session_state[loaded_key] = True
        else:
            # Mark as failed so we don't retry on every rerun (which causes infinite loops)
            st.session_state[loaded_key] = "failed"
            st.error("Could not load this meeting. Go back and try again.")
            if st.button("⬅️ Back to Meetings", key="back_on_load_fail"):
                st.session_state.selected_meeting_id = None
                st.session_state.pop(loaded_key, None)
                set_page("meetings")
                st.rerun()
            return

    # If previous load failed, show error and stop — don't loop
    if st.session_state.get(loaded_key) == "failed":
        st.error("Could not load this meeting.")
        if st.button("⬅️ Back to Meetings", key="back_on_load_fail_2"):
            st.session_state.selected_meeting_id = None
            st.session_state.pop(loaded_key, None)
            set_page("meetings")
            st.rerun()
        return

    meeting = st.session_state[cache_key]

    # Per-meeting caches
    qa_cache_key = f"frontend_qa_cache_{meeting_id}"
    q_cache_key  = f"meeting_questions_{meeting_id}"

    if qa_cache_key not in st.session_state:
        st.session_state[qa_cache_key] = {}

    # ── Header ──────────────────────────────────────────────────────────────
    col_title, col_back = st.columns([7, 1])
    with col_title:
        st.markdown(
            f"<h1 style='color:white;margin-bottom:2px;'>{meeting.get('title', 'Meeting Details')}</h1>",
            unsafe_allow_html=True,
        )
        if meeting.get("description"):
            st.markdown(
                f"<p style='color:#94a3b8;font-size:15px;margin-top:0;'>{meeting['description']}</p>",
                unsafe_allow_html=True,
            )
    with col_back:
        if st.button("Back", key=f"btn_back_{meeting_id}", use_container_width=True):
            st.session_state.selected_meeting_id = None
            set_page("meetings")
            st.rerun()

    status = str(meeting.get("status", "unknown")).lower()

    if meeting.get("error_message"):
        st.error(f"Error: {meeting['error_message']}")

    # Not completed — show status only, no polling
    if status != "completed":
        st.markdown(
            f"<span class='status-{status}'>Status: {status.upper()}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(
            "Your meeting audio is being transcribed and indexed. "
            "Go back to the meetings list and reopen this meeting to check the latest status."
        )
        return

    # ── Stats bar ───────────────────────────────────────────────────────────
    if q_cache_key not in st.session_state:
        st.session_state[q_cache_key] = get_questions_api(meeting_id)
    questions = st.session_state[q_cache_key]
    segments  = meeting.get("transcript_segments", [])
    duration  = meeting.get("duration", 0) or 0

    st.markdown(f"""
    <div style='display:flex;gap:10px;align-items:center;margin-bottom:16px;flex-wrap:wrap;'>
        <span class='status-{status}' style='font-size:12px;padding:4px 12px;'>{status.upper()}</span>
        <span style='background:#1e293b;color:#94a3b8;border:1px solid #334155;padding:4px 12px;border-radius:20px;font-size:13px;'>⏱ {duration:.1f}s</span>
        <span style='background:#1e293b;color:#94a3b8;border:1px solid #334155;padding:4px 12px;border-radius:20px;font-size:13px;'>  {len(segments)} Segments</span>
        <span style='background:#1e293b;color:#94a3b8;border:1px solid #334155;padding:4px 12px;border-radius:20px;font-size:13px;'>  {len(questions)} Past Questions</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Chat state init ─────────────────────────────────────────────────────
    chat_key = f"chat_history_{meeting_id}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    # ── Tabs ────────────────────────────────────────────────────────────────
    tab_chat, tab_coaching, tab_transcript, tab_settings = st.tabs([
        "💬 AI Chat & Q&A",
        "💡 Talk Coaching",
        "📜 Transcript",
        "⚙️ Manage",
    ])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — AI Chat
    # ══════════════════════════════════════════════════════════════════════
    with tab_chat:
        # ── Text input + Send button (works inside tabs, no scope restrictions) ──
        inp_col, btn_col = st.columns([5, 1])
        with inp_col:
            user_input = st.text_input(
                "Ask a question",
                placeholder="Type your question about this meeting...",
                key=f"chat_text_{meeting_id}",
                label_visibility="collapsed",
            )
        with btn_col:
            send_clicked = st.button("Send ➤", key=f"chat_send_{meeting_id}", use_container_width=True)

        # Process question when Send is clicked and input is non-empty
        if send_clicked and user_input and user_input.strip():
            query = user_input.strip()
            nq = query.lower()
            st.session_state[chat_key].append({"role": "user", "content": query})

            if nq in st.session_state[qa_cache_key]:
                st.session_state[chat_key].append(st.session_state[qa_cache_key][nq])
                st.rerun()
            else:
                recent_history = [
                    {"role": m["role"], "content": m.get("content") or m.get("answer", "")}
                    for m in st.session_state[chat_key]
                ][-3:]
                with st.spinner("Analyzing with AI..."):
                    data = ask_question_api(meeting_id, query, history=recent_history)
                    if data:
                        new_msg = {
                            "role": "assistant",
                            "answer": data.get("answer") or data.get("answer_text", "No answer available"),
                            "user_say": data.get("user_say", ""),
                            "reasoning": data.get("reasoning", ""),
                            "talk_improvements": data.get("talk_improvements", []),
                            "timestamps": data.get("timestamps", []),
                            "model_used": data.get("model_used", ""),
                        }
                        st.session_state[chat_key].append(new_msg)
                        st.session_state[qa_cache_key][nq] = new_msg
                        st.session_state.pop(q_cache_key, None)
                        st.rerun()

        st.markdown("<hr style='border-color:#334155;margin:8px 0;'>", unsafe_allow_html=True)

        # Clear chat button
        if st.session_state[chat_key]:
            col_clr, _ = st.columns([1, 5])
            with col_clr:
                if st.button(" Clear Chat", key=f"clear_chat_{meeting_id}", use_container_width=True):
                    st.session_state[chat_key] = []
                    st.rerun()

        # Chat history display
        if not st.session_state[chat_key]:
            st.markdown("""
            <div style='background:#1e293b;border:1px dashed #334155;border-radius:12px;
                        padding:24px;text-align:center;margin:15px 0;'>
                <p style='color:#e2e8f0;font-size:16px;font-weight:500;margin-bottom:6px;'>
                    👋 Start a conversation about this meeting</p>
                <p style='color:#94a3b8;font-size:13px;margin:0;'>
                    Type your question above and click Send.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            for msg in st.session_state[chat_key]:
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        st.write(msg["content"])
                else:
                    with st.chat_message("assistant"):
                        st.markdown(f"** Answer:**\n{msg.get('answer', '')}")
                        if msg.get("user_say"):
                            st.markdown(
                                f"<div style='background-color:#0f172a;padding:12px;"
                                f"border-left:3px solid #38bdf8;border-radius:6px;"
                                f"margin:8px 0;color:#e2e8f0;white-space:pre-wrap;'>"
                                f"<b>🗣️ What Participants Said:</b><br>{msg['user_say']}</div>",
                                unsafe_allow_html=True,
                            )
                        if msg.get("talk_improvements"):
                            st.markdown(
                                "<div style='background-color:#064e3b;padding:12px;"
                                "border-left:3px solid #34d399;border-radius:6px;"
                                "margin:8px 0;color:#ecfdf5;'>"
                                "<b>💡 What Should Be Changed in the Talk:</b>",
                                unsafe_allow_html=True,
                            )
                            for imp in msg["talk_improvements"]:
                                st.markdown(f"• {format_talk_improvement(imp)}")
                            st.markdown("</div>", unsafe_allow_html=True)
                        if msg.get("reasoning"):
                            with st.expander("🧠 AI Reasoning Trace", expanded=False):
                                st.markdown(msg["reasoning"])
                                if msg.get("model_used"):
                                    st.caption(f"⚡ Model: {msg['model_used']}")
                        if msg.get("timestamps"):
                            with st.expander("📍 Relevant Timestamps", expanded=False):
                                for t in msg["timestamps"]:
                                    st.markdown(
                                        f"• **[{t.get('start_time',0):.1f}s – "
                                        f"{t.get('end_time',0):.1f}s]**: {t.get('text','')}"
                                    )

        # Archived past questions
        if questions:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander(f" Previous Questions Archive ({len(questions)} saved)", expanded=False):
                st.markdown("<p style='color:#94a3b8;font-size:13px;'>Stored Q&A for this meeting:</p>", unsafe_allow_html=True)
                for idx, q in enumerate(questions):
                    st.markdown(f"**Q{idx+1}: {q.get('question_text', '')}**")
                    st.markdown(f"<p style='color:#cbd5e1;font-size:14px;'>{q.get('answer_text', '')}</p>", unsafe_allow_html=True)
                    if q.get("user_say"):
                        st.caption(f"️ {q['user_say'][:150]}...")
                    st.markdown("<hr style='border-color:#334155;margin:8px 0;'>", unsafe_allow_html=True)
                    st.markdown(f"<p style='color:#cbd5e1;font-size:14px;'>{q.get('answer_text', '')}</p>", unsafe_allow_html=True)
                    if q.get("user_say"):
                        st.caption(f" {q['user_say'][:150]}...")
                    st.markdown("<hr style='border-color:#334155;margin:8px 0;'>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — Talk Coaching
    # ══════════════════════════════════════════════════════════════════════
    with tab_coaching:
        st.markdown("<h3 style='color:#818cf8;margin-bottom:4px;'>💡 Conversation Coaching</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color:#94a3b8;font-size:14px;'>Actionable feedback on what should be changed in the talk.</p>", unsafe_allow_html=True)

        coaching_key = f"coaching_report_{meeting_id}"
        if coaching_key not in st.session_state:
            col_c1, _ = st.columns([1, 2])
            with col_c1:
                if st.button("Analyze Talk", key=f"btn_coach_{meeting_id}", use_container_width=True):
                    with st.spinner("Analyzing conversation dynamics..."):
                        result = get_coaching_api(meeting_id)
                        if result:
                            st.session_state[coaching_key] = result
                            st.rerun()
            st.info("Click the button above to generate coaching recommendations.")
        else:
            coach = st.session_state[coaching_key]
            st.markdown(
                "<div style='background:#1e1b4b;border-left:4px solid #818cf8;"
                "padding:18px;border-radius:8px;margin:15px 0;color:#f8fafc;'>",
                unsafe_allow_html=True,
            )
            st.markdown(f"** Executive Assessment:**\n\n{coach.get('assessment', '')}")
            improvements = coach.get("talk_improvements", [])
            if improvements:
                st.markdown("<br>**What Should Be Changed:**", unsafe_allow_html=True)
                for imp in improvements:
                    st.markdown(f" {format_talk_improvement(imp)}")
            if coach.get("reasoning"):
                with st.expander(" Analytical Reasoning", expanded=False):
                    st.markdown(coach["reasoning"])
            st.markdown("</div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — Transcript
    # ══════════════════════════════════════════════════════════════════════
    with tab_transcript:
        st.markdown("<h3 style='color:white;margin-bottom:4px;'>Meeting Transcript</h3>", unsafe_allow_html=True)
        if meeting.get("transcript"):
            st.text_area("Full Transcript", meeting["transcript"], height=200, disabled=True, key=f"full_txt_{meeting_id}")
        else:
            st.info("No transcript available.")

        if segments:
            st.markdown(f"<h4 style='color:white;margin-top:15px;'> {len(segments)} Timestamped Segments</h4>", unsafe_allow_html=True)
            search_q = st.text_input("Filter by keyword...", key=f"seg_filter_{meeting_id}")
            filtered = [s for s in segments if search_q.lower() in s.get("text", "").lower()] if search_q else segments
            for seg in filtered:
                st.markdown(f"• **[{seg.get('start_time',0):.1f}s – {seg.get('end_time',0):.1f}s]**: {seg.get('text','')}")

    # ══════════════════════════════════════════════════════════════════════
    # TAB 4 — Manage
    # ══════════════════════════════════════════════════════════════════════
    with tab_settings:
        st.markdown("<h3 style='color:white;'>⚙️ Manage Meeting</h3>", unsafe_allow_html=True)

        with st.expander("Edit Title & Description", expanded=True):
            new_title = st.text_input("Meeting Title", value=meeting.get("title") or "", key=f"inp_title_{meeting_id}")
            new_desc  = st.text_area("Description", value=meeting.get("description") or "", key=f"inp_desc_{meeting_id}")
            if st.button("Save Changes", key=f"btn_save_{meeting_id}", use_container_width=True):
                if not new_title.strip():
                    st.error("Title cannot be empty.")
                else:
                    updated = update_meeting_api(meeting_id, new_title.strip(), new_desc.strip())
                    if updated:
                        st.session_state[cache_key] = updated
                        st.success("Saved!")
                        st.rerun()

        with st.expander("Danger Zone: Delete Meeting"):
            st.warning("Permanently deletes the audio, transcript, questions, and search index.")
            confirmed = st.checkbox("I understand this cannot be undone", key=f"confirm_del_{meeting_id}")
            if st.button("Delete permanently", key=f"btn_del_{meeting_id}", type="primary"):
                if not confirmed:
                    st.error("Please confirm first.")
                elif delete_meeting_api(meeting_id):
                    st.session_state.pop("selected_meeting_id", None)
                    set_page("meetings")
                    st.rerun()


# ─── Main ─────────────────────────────────────────────────────────────────────

def render_sidebar():
    """Sidebar navigation. Called first inside main() before any page widgets."""
    if not st.session_state.is_authenticated:
        return
    with st.sidebar:
        st.markdown("<h2 style='color:white;'>Menu</h2>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button(" My Meetings", key="nav_btn_meetings", use_container_width=True):
            invalidate_meetings_cache()
            st.session_state.current_page = "meetings"
            st.session_state.selected_meeting_id = None
            st.rerun()

        if st.button(" Upload Meeting", key="nav_btn_upload", use_container_width=True):
            st.session_state.current_page = "upload"
            st.rerun()

        st.markdown("<br><br>", unsafe_allow_html=True)

        if st.button(" Logout", key="nav_btn_logout", use_container_width=True):
            logout()
            st.rerun()

        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown(
            "<p style='color:white;font-size:12px;'>Meeting AI Assistant v1.0</p>",
            unsafe_allow_html=True,
        )


def main():
    render_sidebar()

    if not st.session_state.is_authenticated:
        if st.session_state.current_page == "register":
            register_page()
        else:
            login_page()
        return

    page = st.session_state.current_page
    if page == "upload":
        upload_page()
    elif page == "meeting_detail":
        meeting_detail_page()
    else:
        meeting_list_page()


if __name__ == "__main__":
    main()
