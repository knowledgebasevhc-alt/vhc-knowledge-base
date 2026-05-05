import streamlit as st
from groq import Groq
from supabase import create_client
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import pandas as pd
import io

st.set_page_config(page_title="VHC Knowledge Base", page_icon="🏠", layout="wide")

def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.markdown("## 🏠 VHC Knowledge Base")
        st.text_input("Enter team password to continue:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("## 🏠 VHC Knowledge Base")
        st.text_input("Enter team password to continue:", type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect password. Try again.")
        return False
    return True

if not check_password():
    st.stop()

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_resource
def init_groq():
    return Groq(api_key=st.secrets["GROQ_API_KEY"])

supabase = init_supabase()
client   = init_groq()
MODEL    = "llama-3.3-70b-versatile"

def ask_ai(prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=2048
    )
    return response.choices[0].message.content

def categorize(question: str) -> str:
    q = question.lower()
    if "pet" in q:                                                    return "Pet Policy"
    elif "pool" in q or "heat" in q:                                  return "Pool"
    elif "step" in q or "access" in q or "walk" in q \
         or "handicap" in q or "elderly" in q:                        return "Accessibility"
    elif "park" in q:                                                 return "Parking"
    elif "bed" in q or "linen" in q or "sleep" in q:                 return "Bedding"
    elif "fee" in q or "cost" in q or "price" in q:                  return "Fees"
    else:                                                             return "Other"

def save_entry(vhc_id, property_name, question, answer, source, added_by):
    supabase.table("knowledge_base").insert({
        "vhc_id":            vhc_id or "",
        "property_name":     property_name,
        "question_category": categorize(question),
        "question":          question,
        "answer":            answer,
        "source":            source,
        "added_by":          added_by,
        "updated_at":        datetime.utcnow().isoformat()
    }).execute()

def delete_entry(entry_id: int):
    supabase.table("knowledge_base").delete().eq("id", entry_id).execute()

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
- Search for entries matching the property name, address, VHC ID, or topic.
- If you find a relevant match, return a clear friendly answer using only the data provided.
- If nothing matches, respond with exactly the word: NOT_FOUND
- Do not make up information. Only use what is in the entries above."""
    return ask_ai(prompt)

def scrape_supplier_site(url: str, query: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp    = requests.get(url, headers=headers, timeout=15)
        soup    = BeautifulSoup(resp.content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)[:6000]
        prompt = f"""You are searching a vacation rental supplier website for specific information.

Question: "{query}"

Website text:
{text}

Instructions:
- If you find a clear answer, respond with: FOUND: [answer here]
- If not found, respond with exactly: NOT_FOUND
- Be specific and brief. Do not guess."""
        return ask_ai(prompt)
    except Exception as e:
        return f"ERROR: {str(e)}"

def extract_entries_from_content(content: str) -> list:
    prompt = f"""You are analyzing text from a vacation rental company.
The text may contain property information like pet fees, pool details, accessibility info, bedding, parking, or other property-specific details.

Extract every useful piece of property information and return it as a JSON array.
Each item must have these exact fields:
- "property_name": the property name or address (string, required)
- "vhc_id": the VHC ID or property ID if mentioned, otherwise empty string
- "question": a clear question this information answers (string, required)
- "answer": the answer to that question (string, required)

Rules:
- Only include entries where you are confident about both the property and the answer
- Do not guess or make up information
- If the same property has multiple pieces of info, create separate entries for each
- Return ONLY the raw JSON array with no explanation, no markdown, no backticks

Text to analyze:
{content[:6000]}"""
    try:
        response = ask_ai(prompt).strip()
        response = response.replace("```json", "").replace("```", "").strip()
        start    = response.find("[")
        end      = response.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        entries = json.loads(response[start:end])
        return entries if isinstance(entries, list) else []
    except Exception as e:
        st.error(f"Could not parse AI response: {e}")
        return []

def read_uploaded_file(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        return df.to_string(index=False)
    elif name.endswith(".txt") or name.endswith(".md"):
        return uploaded_file.read().decode("utf-8", errors="ignore")
    elif name.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(uploaded_file.read()))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            return f"ERROR reading PDF: {e}"
    elif name.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(uploaded_file.read()))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            return f"ERROR reading Word doc: {e}"
    else:
        try:
            return uploaded_file.read().decode("utf-8", errors="ignore")
        except:
            return "ERROR: Could not read this file type."

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("🏠 VHC Knowledge Base")
st.caption("Your team's single source of truth for property information gaps.")
st.markdown("---")

tab_search, tab_upload, tab_add, tab_view = st.tabs([
    "🔍  Search", "📤  Bulk Upload", "➕  Add Single Entry", "📋  View / Edit All"
])

# ── SEARCH ─────────────────────────────────────────────────────────────────────
with tab_search:
    st.subheader("Ask anything about a property")
    st.caption("Use property name, address, or VHC ID in your question.")
    query = st.text_input("Your question:", placeholder="e.g.  What is the pet fee for 66 Snapper St?  |  Is Coles Ranch Lodge pet friendly?")
    with st.expander("🌐  Optional — provide supplier website to search if not found in knowledge base"):
        supplier_url = st.text_input("Supplier website URL", placeholder="https://www.blueswellrentals.com")
    if st.button("🔍  Search", type="primary"):
        if query.strip():
            with st.spinner("Checking knowledge base..."):
                kb_result = search_knowledge_base(query)
            if "NOT_FOUND" not in kb_result:
                st.success("✅  Found in Knowledge Base")
                st.write(kb_result)
            else:
                st.warning("⚠️  Not found in knowledge base.")
                if supplier_url.strip():
                    with st.spinner("Searching supplier website..."):
                        web_result = scrape_supplier_site(supplier_url.strip(), query)
                    if "FOUND:" in web_result:
                        found_answer = web_result.replace("FOUND:", "").strip()
                        st.success("✅  Found on supplier website!")
                        st.write(found_answer)
                        st.markdown("---")
                        st.info("💾  Save this so your team never has to look it up again.")
                        c1, c2, c3 = st.columns(3)
                        with c1: sv_vhc  = st.text_input("VHC ID (optional)", key="sv_vhc")
                        with c2: sv_prop = st.text_input("Property name *",    key="sv_prop")
                        with c3: sv_by   = st.text_input("Your name *",        key="sv_by")
                        if st.button("💾  Save to Knowledge Base", key="save_web"):
                            if sv_prop and sv_by:
                                save_entry(sv_vhc, sv_prop, query, found_answer, "Supplier website", sv_by)
                                st.success("Saved!")
                            else:
                                st.error("Please fill in Property name and Your name.")
                    elif "ERROR" in web_result:
                        st.error(f"Could not access the website. {web_result}")
                        st.info("📧  Contact the supplier directly.")
                    else:
                        st.error("❌  Not found on supplier website either.")
                        st.info("📧  Contact the supplier. Then use Add Single Entry to save the answer.")
                else:
                    st.info("👆  Add the supplier website URL above to automatically search it.")
        else:
            st.warning("Please type a question first.")

# ── BULK UPLOAD ────────────────────────────────────────────────────────────────
with tab_upload:
    st.subheader("Upload a file to extract and store property information")
    st.caption("Upload any file — the AI will read it, find all useful information, and save it automatically.")
    st.markdown("""
**What you can upload:**
- 📊 **CSV files** — property exports from Sentinel
- 📄 **Word documents (.docx)** — supplier emails, notes, reports
- 📋 **PDF files** — property guides, supplier documents
- 📝 **Text files (.txt)** — copy-pasted emails or notes
""")
    uploaded_file = st.file_uploader("Choose a file", type=["csv","txt","pdf","docx","md"])
    upload_by     = st.text_input("Your name *", placeholder="e.g.  Maria", key="upload_by")

    if uploaded_file and upload_by:
        if st.button("🤖  Analyze & Extract Information", type="primary"):
            with st.spinner(f"Reading {uploaded_file.name}..."):
                content = read_uploaded_file(uploaded_file)
            if content.startswith("ERROR"):
                st.error(content)
            else:
                st.info("✅ File read. Analyzing with AI...")
                with st.spinner("Extracting property information... 20-30 seconds..."):
                    entries = extract_entries_from_content(content)
                if not entries:
                    st.warning("⚠️  No clear property Q&A found in this file. Try a file with more specific property details like emails from suppliers.")
                else:
                    valid = [e for e in entries if e.get("property_name","").strip() and e.get("question","").strip() and e.get("answer","").strip()]
                    st.session_state["extracted_entries"]  = valid
                    st.session_state["extracted_filename"] = uploaded_file.name

    if st.session_state.get("extracted_entries"):
        valid         = st.session_state["extracted_entries"]
        filename      = st.session_state.get("extracted_filename","uploaded file")
        st.success(f"✅  Found **{len(valid)} pieces of information** to save!")
        st.markdown("---")
        st.markdown("**Review below — then click Save All:**")
        for entry in valid:
            prop = entry.get("property_name","").strip()
            q    = entry.get("question","").strip()
            ans  = entry.get("answer","").strip()
            vhc  = entry.get("vhc_id","").strip()
            with st.expander(f"🏠  {prop}  |  {q[:70]}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Property:** {prop}")
                    if vhc: st.markdown(f"**VHC ID:** {vhc}")
                with c2:
                    st.markdown(f"**Category:** {categorize(q)}")
                st.markdown(f"**Q:** {q}")
                st.markdown(f"**A:** {ans}")
        st.markdown("---")
        if st.button(f"💾  Save All {len(valid)} Entries to Knowledge Base", type="primary"):
            saved = 0
            for entry in valid:
                try:
                    save_entry(
                        entry.get("vhc_id",""),
                        entry.get("property_name",""),
                        entry.get("question",""),
                        entry.get("answer",""),
                        f"File: {filename}",
                        upload_by or "Team"
                    )
                    saved += 1
                except Exception as e:
                    st.error(f"Error saving entry: {e}")
            st.success(f"🎉  Saved {saved} entries to your knowledge base!")
            st.session_state["extracted_entries"]  = []
            st.session_state["extracted_filename"] = ""
            st.balloons()

    elif uploaded_file and not upload_by:
        st.warning("Please enter your name before analyzing.")

# ── ADD SINGLE ENTRY ───────────────────────────────────────────────────────────
with tab_add:
    st.subheader("Manually save a single piece of property information")
    st.caption("Use this after getting an answer from a supplier email or phone call.")
    c1, c2 = st.columns(2)
    with c1:
        na_vhc  = st.text_input("VHC ID",         placeholder="e.g.  402129")
        na_prop = st.text_input("Property Name *", placeholder="e.g.  66 Snapper St, Santa Rosa Beach, FL")
        na_q    = st.text_input("Question *",      placeholder="e.g.  What is the pet fee?")
    with c2:
        na_ans  = st.text_area("Answer *",  placeholder="e.g.  Pet fee is $150 per stay. Max 2 pets.", height=120)
        na_src  = st.selectbox("Source", ["Supplier email","Supplier phone call","Supplier website","Airbnb / VRBO listing","Other"])
        na_by   = st.text_input("Your name *", placeholder="e.g.  Maria")
    if st.button("✅  Save to Knowledge Base", type="primary"):
        if na_prop and na_q and na_ans and na_by:
            save_entry(na_vhc, na_prop, na_q, na_ans, na_src, na_by)
            st.success(f"✅  Saved!")
            st.balloons()
        else:
            st.error("Please fill in all required fields (marked with *)")

# ── VIEW / EDIT ALL ────────────────────────────────────────────────────────────
with tab_view:
    st.subheader("All Knowledge Base Entries")
    c1, c2 = st.columns(2)
    with c1:
        f_cat  = st.selectbox("Filter by category", ["All","Pet Policy","Pool","Accessibility","Parking","Bedding","Fees","Other"])
    with c2:
        f_prop = st.text_input("Search by property name", placeholder="Type to filter...")
    if st.button("🔄  Refresh"):
        st.rerun()
    rows = supabase.table("knowledge_base").select("*").order("created_at", desc=True).execute().data
    if f_cat  != "All":
        rows = [r for r in rows if r.get("question_category") == f_cat]
    if f_prop.strip():
        rows = [r for r in rows if f_prop.lower() in (r.get("property_name") or "").lower()]
    st.markdown(f"**{len(rows)} entr{'y' if len(rows)==1 else 'ies'} found**")
    if not rows:
        st.info("No entries yet. Start by uploading a file or adding entries above!")
    else:
        for row in rows:
            with st.expander(f"🏠  {row.get('property_name','Unknown')}  |  {row.get('question','')[:60]}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**VHC ID:** {row.get('vhc_id') or '—'}")
                    st.markdown(f"**Category:** {row.get('question_category','—')}")
                    st.markdown(f"**Source:** {row.get('source','—')}")
                with c2:
                    st.markdown(f"**Added by:** {row.get('added_by','—')}")
                    st.markdown(f"**Date:** {(row.get('created_at') or '')[:10] or '—'}")
                st.markdown(f"**Question:** {row.get('question','—')}")
                st.markdown(f"**Answer:** {row.get('answer','—')}")
                if st.button("🗑️  Delete", key=f"del_{row['id']}"):
                    delete_entry(row["id"])
                    st.success("Deleted.")
                    st.rerun()
