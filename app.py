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

# ── Password ───────────────────────────────────────────────────────────────────
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.markdown("## 🏠 VHC Knowledge Base")
        st.text_input("Enter team password:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("## 🏠 VHC Knowledge Base")
        st.text_input("Enter team password:", type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect password.")
        return False
    return True

if not check_password():
    st.stop()

# ── Connections ────────────────────────────────────────────────────────────────
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_resource
def init_groq():
    return Groq(api_key=st.secrets["GROQ_API_KEY"])

supabase = init_supabase()
client   = init_groq()
MODEL    = "llama-3.3-70b-versatile"

# ── AI Helper ──────────────────────────────────────────────────────────────────
def ask_ai(prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=2048
    )
    return response.choices[0].message.content

# ── Helpers ────────────────────────────────────────────────────────────────────
def categorize(question: str) -> str:
    q = question.lower()
    if "pet" in q:                                                           return "Pet Policy"
    elif "pool" in q or "hot tub" in q or "jacuzzi" in q or "spa" in q:    return "Pool"
    elif "step" in q or "access" in q or "walk" in q          or "handicap" in q or "elderly" in q or "wheelchair" in q:         return "Accessibility"
    elif "park" in q:                                                        return "Parking"
    elif "bed" in q or "linen" in q or "sleep" in q or "pillow" in q:      return "Bedding"
    elif "fee" in q or "cost" in q or "price" in q or "charge" in q:       return "Fees"
    elif "beach" in q and ("access" in q or "equip" in q or "chair" in q
         or "umbrella" in q or "gear" in q):                                 return "Beach"
    elif "wifi" in q or "internet" in q or "wireless" in q:                 return "WiFi"
    elif "tv" in q or "television" in q or "streaming" in q          or "cable" in q or "smart" in q or "netflix" in q:                 return "TV & Entertainment"
    elif "grill" in q or "bbq" in q or "barbecue" in q:                    return "Grill"
    elif "front desk" in q or "concierge" in q or "reception" in q:        return "Front Desk"
    else:                                                                    return "Other"

def get_suppliers() -> list:
    rows = supabase.table("suppliers").select("*").order("name").execute().data
    return rows or []

def get_supplier_names() -> list:
    return [s["name"] for s in get_suppliers()]

def get_supplier_website(name: str) -> str:
    rows = supabase.table("suppliers").select("website").eq("name", name).execute().data
    if rows and rows[0].get("website"):
        return rows[0]["website"]
    return ""

def is_duplicate(property_name: str, question: str, vhc_id: str = "") -> bool:
    existing = supabase.table("knowledge_base").select("id").execute().data
    all_rows = supabase.table("knowledge_base").select("property_name,question,vhc_id").execute().data
    prop_lower = (property_name or "").lower().strip()
    q_lower    = (question or "").lower().strip()
    for r in all_rows:
        r_prop = (r.get("property_name","") or "").lower().strip()
        r_q    = (r.get("question","") or "").lower().strip()
        r_vhc  = (r.get("vhc_id","") or "").strip()
        if r_q == q_lower and (r_prop == prop_lower or (vhc_id and r_vhc == vhc_id.strip())):
            return True
    return False

def save_entry(vhc_id, property_name, question, answer, source, added_by, supplier_name="", unit_label=""):
    supabase.table("knowledge_base").insert({
        "vhc_id":            vhc_id or "",
        "unit_label":        unit_label or "",
        "property_name":     property_name,
        "question_category": categorize(question),
        "question":          question,
        "answer":            answer,
        "source":            source,
        "added_by":          added_by,
        "supplier_name":     supplier_name or "",
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
- Search for entries matching the property name, address, VHC ID, supplier, or topic.
- If you find a relevant match, return a clear friendly answer using only the data provided. Include the supplier name in your answer.
- If nothing matches, respond with exactly: NOT_FOUND
- Do not make up information."""
    return ask_ai(prompt)

def scrape_supplier_site(url: str, query: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp    = requests.get(url, headers=headers, timeout=15)
        soup    = BeautifulSoup(resp.content, "html.parser")
        for tag in soup(["script","style","nav","footer","header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)[:6000]
        prompt = f"""You are searching a vacation rental supplier website for specific information.
Question: "{query}"
Website text: {text}
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
- "unit_label": the unit label, unit number, or apartment identifier if mentioned, otherwise empty string
- "question": a clear question this information answers (string, required)
- "answer": the answer to that question (string, required)
Rules:
- Only include entries where you are confident about both the property and the answer
- Do not guess or make up information
- If the same property has multiple pieces of info, create separate entries for each
- Return ONLY the raw JSON array, no explanation, no markdown, no backticks
Text to analyze:
{content[:6000]}"""
    try:
        response = ask_ai(prompt).strip()
        response = response.replace("```json","").replace("```","").strip()
        start    = response.find("[")
        end      = response.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        return json.loads(response[start:end])
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

tab_search, tab_upload, tab_add, tab_suppliers, tab_view = st.tabs([
    "🔍  Search",
    "📤  Bulk Upload",
    "➕  Add Single Entry",
    "🏢  Manage Suppliers",
    "📋  View / Edit All"
])

# ══════════════════════════════════════════════════════════════════════════════
# SEARCH
# ══════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.subheader("Ask anything about a property")
    st.caption("Use property name, address, VHC ID, or supplier name in your question.")

    query = st.text_input("Your question:",
        placeholder="e.g.  What is the pet fee for 66 Snapper St?  |  Is Coles Ranch Lodge pet friendly?  |  All Blue Swell properties that allow pets")

    supplier_names = get_supplier_names()
    search_supplier = st.selectbox(
        "Filter by supplier (optional)",
        ["All suppliers"] + supplier_names,
        key="search_supplier"
    )

    # Auto-fill website from supplier
    auto_website = ""
    if search_supplier != "All suppliers":
        auto_website = get_supplier_website(search_supplier)

    with st.expander("🌐  Supplier website — auto-filled if supplier selected above"):
        supplier_url = st.text_input("Supplier website URL",
            value=auto_website,
            placeholder="https://www.blueswellrentals.com")

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
                        found_answer = web_result.replace("FOUND:","").strip()
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
                                sup = "" if search_supplier == "All suppliers" else search_supplier
                                save_entry(sv_vhc, sv_prop, query, found_answer, "Supplier website", sv_by, sup)
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
                    st.info("👆  Select a supplier above or add their website URL to automatically search it.")
        else:
            st.warning("Please type a question first.")

# ══════════════════════════════════════════════════════════════════════════════
# BULK UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.subheader("Upload a file to extract and store property information")
    st.caption("Upload any file — the AI will read it, find all useful information, and save it automatically.")

    supplier_names = get_supplier_names()
    if not supplier_names:
        st.warning("⚠️  No suppliers added yet. Go to **Manage Suppliers** tab first and add the supplier before uploading.")
    else:
        st.markdown("""
**What you can upload:**
- 📊 **CSV files** — property exports from Sentinel
- 📄 **Word documents (.docx)** — supplier emails, notes, reports
- 📋 **PDF files** — property guides, supplier documents
- 📝 **Text files (.txt)** — copy-pasted emails or notes
""")
        up_supplier = st.selectbox("Which supplier does this file belong to? *",
                                   ["— Select a supplier —"] + supplier_names,
                                   key="up_supplier")
        uploaded_file = st.file_uploader("Choose a file", type=["csv","txt","pdf","docx","md"])
        upload_by     = st.text_input("Your name *", placeholder="e.g.  Maria", key="upload_by")

        if uploaded_file and upload_by and up_supplier != "— Select a supplier —":
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
                        st.warning("⚠️  No clear property Q&A found in this file.")
                    else:
                        valid = [e for e in entries
                                 if e.get("property_name","").strip()
                                 and e.get("question","").strip()
                                 and e.get("answer","").strip()]
                        st.session_state["extracted_entries"]  = valid
                        st.session_state["extracted_filename"] = uploaded_file.name
                        st.session_state["extracted_supplier"] = up_supplier
                        st.session_state["extracted_by"]       = upload_by

        if st.session_state.get("extracted_entries"):
            valid    = st.session_state["extracted_entries"]
            filename = st.session_state.get("extracted_filename","file")
            supplier = st.session_state.get("extracted_supplier","")
            by       = st.session_state.get("extracted_by","Team")

            st.success(f"✅  Found **{len(valid)} pieces of information** for **{supplier}**")
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
                        st.markdown(f"**Supplier:** {supplier}")
                    with c2:
                        st.markdown(f"**Category:** {categorize(q)}")
                    st.markdown(f"**Q:** {q}")
                    st.markdown(f"**A:** {ans}")
            st.markdown("---")
            if st.button(f"💾  Save All {len(valid)} Entries to Knowledge Base", type="primary"):
                saved   = 0
                skipped = 0
                for entry in valid:
                    try:
                        prop = entry.get("property_name","")
                        q    = entry.get("question","")
                        vhc  = entry.get("vhc_id","")
                        if is_duplicate(prop, q, vhc):
                            skipped += 1
                            continue
                        save_entry(
                            vhc, prop, q,
                            entry.get("answer",""),
                            f"File: {filename}",
                            by,
                            supplier,
                            entry.get("unit_label","")
                        )
                        saved += 1
                    except Exception as e:
                        st.error(f"Error saving entry: {e}")
                msg = f"🎉  Saved {saved} entries for {supplier}!"
                if skipped:
                    msg += f" ({skipped} duplicate{'s' if skipped>1 else ''} skipped)"
                st.success(msg)
                st.session_state["extracted_entries"]  = []
                st.session_state["extracted_filename"] = ""
                st.session_state["extracted_supplier"] = ""
                st.balloons()
        elif uploaded_file and not upload_by:
            st.warning("Please enter your name.")
        elif uploaded_file and up_supplier == "— Select a supplier —":
            st.warning("Please select a supplier.")

# ══════════════════════════════════════════════════════════════════════════════
# ADD SINGLE ENTRY
# ══════════════════════════════════════════════════════════════════════════════
with tab_add:
    st.subheader("Manually save a single piece of property information")
    st.caption("Use this after getting an answer from a supplier email or phone call.")

    supplier_names = get_supplier_names()
    c1, c2 = st.columns(2)
    with c1:
        na_supplier = st.selectbox("Supplier *",
                                   ["— Select a supplier —"] + supplier_names + ["+ Other (type below)"],
                                   key="na_supplier")
        if na_supplier == "+ Other (type below)":
            na_supplier = st.text_input("Type supplier name:", key="na_supplier_custom")
        na_vhc   = st.text_input("VHC ID",         placeholder="e.g.  402129")
        na_unit  = st.text_input("Unit Label",      placeholder="e.g.  Unit 2B / Apt 4 / Villa 3")
        na_prop  = st.text_input("Property Name *", placeholder="e.g.  66 Snapper St, Santa Rosa Beach, FL")
        na_q     = st.text_input("Question *",      placeholder="e.g.  What is the pet fee?")
    with c2:
        na_ans  = st.text_area("Answer *",
            placeholder="e.g.  Pet fee is $150 per stay. Max 2 pets. No aggressive breeds.",
            height=120)
        na_src  = st.selectbox("Source", [
            "Supplier email","Supplier phone call","Supplier website",
            "Airbnb / VRBO listing","Other"])
        na_by   = st.text_input("Your name *", placeholder="e.g.  Maria")

    if st.button("✅  Save to Knowledge Base", type="primary"):
        if na_prop and na_q and na_ans and na_by and na_supplier not in ["— Select a supplier —",""]:
            if is_duplicate(na_prop, na_q, na_vhc):
                st.warning("⚠️  This entry already exists in the knowledge base. Not saved.")
            else:
                existing = [s["name"] for s in get_suppliers()]
                if na_supplier.strip() not in existing:
                    try:
                        supabase.table("suppliers").insert({"name": na_supplier.strip(), "website": ""}).execute()
                    except:
                        pass
                save_entry(na_vhc, na_prop, na_q, na_ans, na_src, na_by, na_supplier, na_unit)
                st.success(f"✅  Saved for **{na_supplier}**!")
                st.balloons()
        else:
            st.error("Please fill in all required fields including supplier.")

# ══════════════════════════════════════════════════════════════════════════════
# MANAGE SUPPLIERS
# ══════════════════════════════════════════════════════════════════════════════
with tab_suppliers:
    st.subheader("Manage Your Suppliers")
    st.caption("Add suppliers here first. They will appear in dropdowns throughout the app.")

    with st.form("add_supplier_form"):
        st.markdown("**Add a new supplier:**")
        fc1, fc2 = st.columns(2)
        with fc1:
            new_sup_name    = st.text_input("Supplier Name *", placeholder="e.g.  Blue Swell Rentals")
        with fc2:
            new_sup_website = st.text_input("Website URL", placeholder="e.g.  https://www.blueswellrentals.com")
        submitted = st.form_submit_button("➕  Add Supplier", type="primary")
        if submitted:
            if new_sup_name.strip():
                try:
                    supabase.table("suppliers").insert({
                        "name":    new_sup_name.strip(),
                        "website": new_sup_website.strip() or ""
                    }).execute()
                    st.success(f"✅  Added **{new_sup_name}** to your supplier list!")
                    st.rerun()
                except Exception as e:
                    if "unique" in str(e).lower():
                        st.warning(f"'{new_sup_name}' already exists.")
                    else:
                        st.error(f"Error: {e}")
            else:
                st.error("Please enter a supplier name.")

    st.markdown("---")
    st.markdown("**Your current suppliers:**")

    suppliers = get_suppliers()
    if not suppliers:
        st.info("No suppliers added yet. Add your first one above!")
    else:
        st.markdown(f"**{len(suppliers)} supplier{'s' if len(suppliers)!=1 else ''} total**")
        for sup in suppliers:
            with st.expander(f"🏢  {sup['name']}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Name:** {sup['name']}")
                    st.markdown(f"**Website:** {sup.get('website') or '—'}")
                with c2:
                    added = (sup.get('created_at') or '')[:10]
                    st.markdown(f"**Added:** {added or '—'}")
                if st.button("🗑️  Delete supplier", key=f"delsup_{sup['id']}"):
                    supabase.table("suppliers").delete().eq("id", sup["id"]).execute()
                    st.success("Supplier deleted.")
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# VIEW / EDIT ALL
# ══════════════════════════════════════════════════════════════════════════════
BADGE_COLORS = [
    ("background:#E6F1FB;color:#0C447C","background:#E6F1FB;color:#0C447C"),
    ("background:#E1F5EE;color:#085041","background:#E1F5EE;color:#085041"),
    ("background:#FAEEDA;color:#633806","background:#FAEEDA;color:#633806"),
    ("background:#FAECE7;color:#4A1B0C","background:#FAECE7;color:#4A1B0C"),
    ("background:#EEEDFE;color:#26215C","background:#EEEDFE;color:#26215C"),
    ("background:#FBEAF0;color:#4B1528","background:#FBEAF0;color:#4B1528"),
    ("background:#EAF3DE;color:#173404","background:#EAF3DE;color:#173404"),
]

def supplier_badge_style(name: str) -> str:
    idx = hash(name or "") % len(BADGE_COLORS)
    return BADGE_COLORS[idx][0]

with tab_view:
    st.subheader("All Knowledge Base Entries")

    supplier_names = get_supplier_names()
    c1, c2, c3 = st.columns(3)
    with c1:
        f_supplier = st.selectbox("Filter by supplier", ["All"] + supplier_names)
    with c2:
        f_cat = st.selectbox("Filter by category",
                    ["All","Pet Policy","Pool","Accessibility","Parking","Bedding","Fees","Beach","WiFi","TV & Entertainment","Grill","Front Desk","Other"])
    with c3:
        f_prop = st.text_input("Search by property name", placeholder="Type to filter...")

    if st.button("🔄  Refresh"):
        st.rerun()

    rows = supabase.table("knowledge_base").select("*").order("created_at", desc=True).execute().data

    if f_supplier != "All":
        rows = [r for r in rows if r.get("supplier_name","") == f_supplier]
    if f_cat != "All":
        rows = [r for r in rows if r.get("question_category") == f_cat]
    if f_prop.strip():
        rows = [r for r in rows if f_prop.lower() in (r.get("property_name") or "").lower()]

    st.markdown(f"**{len(rows)} entr{'y' if len(rows)==1 else 'ies'} found**")

    if not rows:
        st.info("No entries yet. Start by adding a supplier, then upload a file or add entries manually!")
    else:
        # Table header
        h1, h2, h3, h4, h5 = st.columns([2, 3, 3, 1.2, 1.2])
        with h1: st.markdown("<span style='font-size:12px;color:var(--color-text-secondary);font-weight:500;'>SUPPLIER</span>", unsafe_allow_html=True)
        with h2: st.markdown("<span style='font-size:12px;color:var(--color-text-secondary);font-weight:500;'>PROPERTY</span>", unsafe_allow_html=True)
        with h3: st.markdown("<span style='font-size:12px;color:var(--color-text-secondary);font-weight:500;'>QUESTION</span>", unsafe_allow_html=True)
        with h4: st.markdown("<span style='font-size:12px;color:var(--color-text-secondary);font-weight:500;'>CATEGORY</span>", unsafe_allow_html=True)
        with h5: st.markdown("<span style='font-size:12px;color:var(--color-text-secondary);font-weight:500;'>ACTIONS</span>", unsafe_allow_html=True)
        st.markdown("<hr style='margin:4px 0 8px 0;border:none;border-top:0.5px solid var(--color-border-tertiary);'>", unsafe_allow_html=True)

        for row in rows:
            edit_key = f"edit_mode_{row['id']}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False

            if not st.session_state[edit_key]:
                # ── TABLE ROW ──
                sup   = row.get("supplier_name","") or ""
                style = supplier_badge_style(sup)
                cat   = row.get("question_category","") or "Other"
                vhc   = row.get("vhc_id","") or ""

                r1, r2, r3, r4, r5 = st.columns([2, 3, 3, 1.2, 1.2])
                with r1:
                    if sup:
                        st.markdown(f"<span style='display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:500;{style}'>{sup}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span style='color:var(--color-text-secondary);font-size:12px;'>—</span>", unsafe_allow_html=True)
                with r2:
                    prop_short  = (row.get("property_name","") or "")[:45]
                    unit_lbl    = row.get("unit_label","") or ""
                    vhc_txt     = f"VHC: {vhc}" if vhc else ""
                    unit_txt    = f"Unit: {unit_lbl}" if unit_lbl else ""
                    sub_parts   = " | ".join(filter(None, [vhc_txt, unit_txt]))
                    sub_html    = f"<br><span style='font-size:11px;color:var(--color-text-secondary);'>{sub_parts}</span>" if sub_parts else ""
                    st.markdown(f"<span style='font-size:13px;font-weight:500;'>{prop_short}</span>{sub_html}", unsafe_allow_html=True)
                with r3:
                    q_short = (row.get("question","") or "")[:65]
                    st.markdown(f"<span style='font-size:13px;color:var(--color-text-secondary);'>{q_short}</span>", unsafe_allow_html=True)
                with r4:
                    st.markdown(f"<span style='display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;background:var(--color-background-secondary);color:var(--color-text-secondary);'>{cat}</span>", unsafe_allow_html=True)
                with r5:
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if st.button("✏️", key=f"editbtn_{row['id']}", help="Edit this entry"):
                            st.session_state[edit_key] = True
                            st.rerun()
                    with bc2:
                        if st.button("🗑️", key=f"del_{row['id']}", help="Delete this entry"):
                            delete_entry(row["id"])
                            st.rerun()

                st.markdown("<hr style='margin:2px 0;border:none;border-top:0.5px solid var(--color-border-tertiary);'>", unsafe_allow_html=True)

            else:
                # ── EDIT FORM (inline below the row) ──
                with st.container():
                    st.markdown(f"<div style='background:var(--color-background-secondary);border-radius:8px;padding:12px 16px;margin:4px 0;'>", unsafe_allow_html=True)
                    st.markdown(f"**✏️ Editing: {(row.get('property_name','') or '')[:50]}**")
                    all_suppliers = get_supplier_names()
                    cur_sup       = row.get("supplier_name","")
                    sup_options   = ["— Select —"] + all_suppliers + ["+ Type new supplier"]
                    cur_idx       = sup_options.index(cur_sup) if cur_sup in sup_options else 0

                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_sup = st.selectbox("Supplier", sup_options, index=cur_idx, key=f"e_sup_{row['id']}")
                        if e_sup == "+ Type new supplier":
                            e_sup = st.text_input("Type supplier name:", key=f"e_sup_txt_{row['id']}")
                        e_vhc  = st.text_input("VHC ID",        value=row.get("vhc_id",""),          key=f"e_vhc_{row['id']}")
                        e_unit = st.text_input("Unit Label",    value=row.get("unit_label",""),       key=f"e_unit_{row['id']}")
                        e_prop = st.text_input("Property Name", value=row.get("property_name",""),    key=f"e_prop_{row['id']}")
                        e_q    = st.text_input("Question",      value=row.get("question",""),         key=f"e_q_{row['id']}")
                    with ec2:
                        e_ans = st.text_area("Answer", value=row.get("answer",""), height=120,        key=f"e_ans_{row['id']}")
                        src_opts = ["Supplier email","Supplier phone call","Supplier website","Airbnb / VRBO listing","Other"]
                        src_idx  = src_opts.index(row.get("source","Other")) if row.get("source","Other") in src_opts else 0
                        e_src = st.selectbox("Source", src_opts, index=src_idx,                      key=f"e_src_{row['id']}")
                        e_by  = st.text_input("Updated by", value=row.get("added_by",""),             key=f"e_by_{row['id']}")

                    sc1, sc2 = st.columns(2)
                    with sc1:
                        if st.button("💾  Save Changes", type="primary", key=f"save_edit_{row['id']}"):
                            if e_sup and e_sup not in ["— Select —",""]:
                                existing = get_supplier_names()
                                if e_sup.strip() not in existing:
                                    try:
                                        supabase.table("suppliers").insert({"name": e_sup.strip(), "website": ""}).execute()
                                    except:
                                        pass
                            supabase.table("knowledge_base").update({
                                "supplier_name":     e_sup if e_sup not in ["— Select —",""] else "",
                                "vhc_id":            e_vhc,
                                "unit_label":        e_unit,
                                "property_name":     e_prop,
                                "question":          e_q,
                                "question_category": categorize(e_q),
                                "answer":            e_ans,
                                "source":            e_src,
                                "added_by":          e_by,
                                "updated_at":        datetime.utcnow().isoformat()
                            }).eq("id", row["id"]).execute()
                            st.session_state[edit_key] = False
                            st.success("✅  Updated!")
                            st.rerun()
                    with sc2:
                        if st.button("✖️  Cancel", key=f"cancel_edit_{row['id']}"):
                            st.session_state[edit_key] = False
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                    st.markdown("<hr style='margin:2px 0;border:none;border-top:0.5px solid var(--color-border-tertiary);'>", unsafe_allow_html=True)
