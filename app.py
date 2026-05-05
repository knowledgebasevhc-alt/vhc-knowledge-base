import streamlit as st
import google.generativeai as genai
from supabase import create_client
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VHC Knowledge Base",
    page_icon="🏠",
    layout="wide"
)

# ─── Password Protection ────────────────────────────────────────────────────────
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("## 🏠 VHC Knowledge Base")
        st.text_input("Enter team password to continue:",
                      type="password",
                      on_change=password_entered,
                      key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("## 🏠 VHC Knowledge Base")
        st.text_input("Enter team password to continue:",
                      type="password",
                      on_change=password_entered,
                      key="password")
        st.error("❌ Incorrect password. Try again.")
        return False
    return True

if not check_password():
    st.stop()

# ─── Initialize Connections ─────────────────────────────────────────────────────
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_resource
def init_gemini():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel("gemini-1.5-flash")

supabase = init_supabase()
model    = init_gemini()

# ─── Helper: Search Knowledge Base ─────────────────────────────────────────────
def search_knowledge_base(query: str) -> str:
    rows = supabase.table("knowledge_base").select("*").execute().data
    if not rows:
        return "NOT_FOUND"

    entries_text = json.dumps(rows, indent=2, default=str)
    prompt = f"""You are an assistant for a vacation rental company called VacayHome.

A team member asked: "{query}"

Below is every entry in our internal knowledge base:
{entries_text}

Instructions:
- Search for entries that match the property name, address, VHC ID, or topic in the question.
- If you find a relevant match, return a clear, friendly answer using only the data provided.
- If nothing matches, respond with exactly the word: NOT_FOUND
- Do not make up information. Only use what is in the entries above."""

    return model.generate_content(prompt).text

# ─── Helper: Scrape Supplier Website ───────────────────────────────────────────
def scrape_supplier_site(url: str, query: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp    = requests.get(url, headers=headers, timeout=15)
        soup    = BeautifulSoup(resp.content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)[:8000]

        prompt = f"""You are searching a vacation rental supplier's website for specific information.

Question: "{query}"

Website text:
{text}

Instructions:
- If you find a clear answer to the question, respond with: FOUND: [answer here]
- If the answer is not on this page, respond with exactly: NOT_FOUND
- Be specific and brief. Do not guess."""

        return model.generate_content(prompt).text
    except Exception as e:
        return f"ERROR: {str(e)}"

# ─── Helper: Save to Knowledge Base ────────────────────────────────────────────
def save_entry(vhc_id, property_name, question, answer, source, added_by):
    q = question.lower()
    if   "pet"                             in q: category = "Pet Policy"
    elif "pool" in q or "heat" in q:             category = "Pool"
    elif "step" in q or "access" in q or \
         "walker" in q or "handicap" in q:       category = "Accessibility"
    elif "park" in q:                            category = "Parking"
    else:                                        category = "Other"

    supabase.table("knowledge_base").insert({
        "vhc_id":            vhc_id or "",
        "property_name":     property_name,
        "question_category": category,
        "question":          question,
        "answer":            answer,
        "source":            source,
        "added_by":          added_by,
        "updated_at":        datetime.utcnow().isoformat()
    }).execute()

# ─── Helper: Delete Entry ───────────────────────────────────────────────────────
def delete_entry(entry_id: int):
    supabase.table("knowledge_base").delete().eq("id", entry_id).execute()

# ─── UI ─────────────────────────────────────────────────────────────────────────
st.title("🏠 VHC Knowledge Base")
st.caption("Your team's single source of truth for property information gaps.")
st.markdown("---")

tab_search, tab_add, tab_view = st.tabs(["🔍  Search", "➕  Add Knowledge", "📋  View / Edit All"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SEARCH
# ══════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.subheader("Ask anything about a property")
    st.caption("Use property name, address, or VHC ID in your question.")

    query = st.text_input(
        "Your question:",
        placeholder="e.g.  What is the pet fee for 66 Snapper St?   |   Is Coles Ranch Lodge pet friendly?   |   How many steps at Sedona Summit unit 2B?"
    )

    with st.expander("🌐  Optional — provide supplier website to search automatically if not found"):
        supplier_url = st.text_input(
            "Supplier website URL",
            placeholder="https://www.blueswellrentals.com"
        )

    search_clicked = st.button("🔍  Search", type="primary")

    if search_clicked and query.strip():
        # Step 1 — Check knowledge base
        with st.spinner("Checking knowledge base..."):
            kb_result = search_knowledge_base(query)

        if "NOT_FOUND" not in kb_result:
            st.success("✅  Found in Knowledge Base")
            st.write(kb_result)

        else:
            st.warning("⚠️  Not found in knowledge base.")

            # Step 2 — Check supplier website
            if supplier_url.strip():
                with st.spinner(f"Searching supplier website..."):
                    web_result = scrape_supplier_site(supplier_url.strip(), query)

                if "FOUND:" in web_result:
                    found_answer = web_result.replace("FOUND:", "").strip()
                    st.success("✅  Found on supplier website!")
                    st.write(found_answer)

                    st.markdown("---")
                    st.info("💾  Save this answer so your team never has to look it up again.")

                    c1, c2, c3 = st.columns(3)
                    with c1: sv_vhc  = st.text_input("VHC ID (optional)", key="sv_vhc")
                    with c2: sv_prop = st.text_input("Property name *",    key="sv_prop")
                    with c3: sv_by   = st.text_input("Your name *",        key="sv_by")

                    if st.button("💾  Save to Knowledge Base", key="save_from_search"):
                        if sv_prop and sv_by:
                            save_entry(sv_vhc, sv_prop, query, found_answer, "Supplier website", sv_by)
                            st.success("Saved! This answer is now permanently in your knowledge base.")
                        else:
                            st.error("Please fill in Property name and Your name.")

                elif "ERROR" in web_result:
                    st.error(f"Could not access the website. {web_result}")
                    st.info("📧  You will need to contact the supplier directly for this one.")

                else:
                    st.error("❌  Not found on the supplier website either.")
                    st.info("📧  Contact the supplier. Once they respond, come to **Add Knowledge** and save the answer.")

            else:
                st.info("👆  Add the supplier website URL above to automatically search it.")

    elif search_clicked:
        st.warning("Please type a question first.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ADD KNOWLEDGE
# ══════════════════════════════════════════════════════════════════════════════
with tab_add:
    st.subheader("Save new property information")
    st.caption("Use this after you get an answer from a supplier email, phone call, or website.")

    c1, c2 = st.columns(2)
    with c1:
        na_vhc   = st.text_input("VHC ID",         placeholder="e.g.  402129")
        na_prop  = st.text_input("Property Name *", placeholder="e.g.  66 Snapper St, Santa Rosa Beach, FL")
        na_q     = st.text_input("Question *",      placeholder="e.g.  What is the pet fee?")
    with c2:
        na_ans   = st.text_area("Answer *",         placeholder="e.g.  Pet fee is $150 per stay. Max 2 pets. No aggressive breeds.", height=120)
        na_src   = st.selectbox("Source", [
                        "Supplier email",
                        "Supplier phone call",
                        "Supplier website",
                        "Airbnb / VRBO listing",
                        "Other"
                   ])
        na_by    = st.text_input("Your name *",     placeholder="e.g.  Maria")

    if st.button("✅  Save to Knowledge Base", type="primary"):
        if na_prop and na_q and na_ans and na_by:
            save_entry(na_vhc, na_prop, na_q, na_ans, na_src, na_by)
            st.success(f"✅  Saved! '{na_q}' for **{na_prop}** is now in the knowledge base.")
            st.balloons()
        else:
            st.error("Please fill in all required fields (marked with *)")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — VIEW / EDIT ALL
# ══════════════════════════════════════════════════════════════════════════════
with tab_view:
    st.subheader("All Knowledge Base Entries")

    c1, c2 = st.columns(2)
    with c1:
        f_cat  = st.selectbox("Filter by category", ["All", "Pet Policy", "Pool", "Accessibility", "Parking", "Other"])
    with c2:
        f_prop = st.text_input("Search by property name", placeholder="Type to filter...")

    if st.button("🔄  Refresh list"):
        st.rerun()

    rows = supabase.table("knowledge_base").select("*").order("created_at", desc=True).execute().data

    if f_cat  != "All":
        rows = [r for r in rows if r.get("question_category") == f_cat]
    if f_prop.strip():
        rows = [r for r in rows if f_prop.lower() in (r.get("property_name") or "").lower()]

    st.markdown(f"**{len(rows)} entr{'y' if len(rows)==1 else 'ies'} found**")

    if not rows:
        st.info("No entries yet — start searching or adding knowledge above!")
    else:
        for row in rows:
            label = f"🏠  {row.get('property_name','Unknown')}  |  {row.get('question','')[:60]}"
            with st.expander(label):
                ec1, ec2 = st.columns(2)
                with ec1:
                    st.markdown(f"**VHC ID:** {row.get('vhc_id') or '—'}")
                    st.markdown(f"**Category:** {row.get('question_category','—')}")
                    st.markdown(f"**Source:** {row.get('source','—')}")
                with ec2:
                    st.markdown(f"**Added by:** {row.get('added_by','—')}")
                    created = (row.get('created_at') or '')[:10]
                    st.markdown(f"**Date added:** {created or '—'}")

                st.markdown(f"**Question:** {row.get('question','—')}")
                st.markdown(f"**Answer:** {row.get('answer','—')}")

                if st.button(f"🗑️  Delete this entry", key=f"del_{row['id']}"):
                    delete_entry(row["id"])
                    st.success("Entry deleted.")
                    st.rerun()
