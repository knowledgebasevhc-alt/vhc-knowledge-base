import streamlit as st
from groq import Groq
from supabase import create_client
import requests
from bs4 import BeautifulSoup
import json, hashlib, io
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="VHC Knowledge Base", page_icon="🏠", layout="wide")

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.big-search input {font-size:18px !important; padding:14px !important;}
.green-result {border-left:4px solid #3B6D11;padding:16px 20px;background:var(--background-color);border-radius:0 8px 8px 0;margin:8px 0;}
.result-tag {font-size:11px;font-weight:600;color:#3B6D11;text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px;}
.result-body {font-size:16px;line-height:1.65;}
.tip-box {padding:12px 16px;border:1px solid #ddd;border-radius:8px;font-size:13px;color:#888;margin-top:12px;}
.qa-pair {background:#f8f8f8;border-radius:8px;padding:14px;margin-bottom:10px;}
</style>
""", unsafe_allow_html=True)

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

SOURCE_OPTS = ["Supplier email","Supplier phone call","Supplier website","Airbnb listing","VRBO listing","Other"]
CAT_OPTS    = ["All","Pet Policy","Pool","Accessibility","Parking","Bedding","Fees","Beach","WiFi","TV & Entertainment","Grill","Front Desk","Other"]
EXAMPLE_QS  = ["Are pets allowed?","What is the pet fee?","Is pool heating available?","How many steps to the unit?","Is there a hot tub?","Is there a grill?","What type of TV?","Is parking free?"]

# ── AI ─────────────────────────────────────────────────────────────────────────
def ask_ai(prompt: str) -> str:
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role":"user","content":prompt}],
        temperature=0.1, max_tokens=2048)
    return r.choices[0].message.content

# ── Categorize ─────────────────────────────────────────────────────────────────
def categorize(q: str) -> str:
    q = q.lower()
    if "pet" in q:                                                              return "Pet Policy"
    elif any(w in q for w in ["pool","hot tub","jacuzzi","spa"]):               return "Pool"
    elif any(w in q for w in ["step","access","walk","handicap","elderly","wheelchair"]): return "Accessibility"
    elif "park" in q:                                                           return "Parking"
    elif any(w in q for w in ["bed","linen","sleep","pillow"]):                 return "Bedding"
    elif any(w in q for w in ["fee","cost","price","charge"]):                  return "Fees"
    elif "beach" in q:                                                          return "Beach"
    elif any(w in q for w in ["wifi","internet","wireless"]):                   return "WiFi"
    elif any(w in q for w in ["tv","television","streaming","cable","smart","netflix"]): return "TV & Entertainment"
    elif any(w in q for w in ["grill","bbq","barbecue"]):                       return "Grill"
    elif any(w in q for w in ["front desk","concierge","reception"]):           return "Front Desk"
    else:                                                                       return "Other"

# ── Supplier helpers ───────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def get_suppliers():
    return supabase.table("suppliers").select("*").order("name").execute().data or []

def get_supplier_names():
    return [s["name"] for s in get_suppliers()]

def get_supplier_website(name: str) -> str:
    rows = supabase.table("suppliers").select("website").eq("name", name).execute().data
    return (rows[0].get("website","") if rows else "") or ""

def ensure_supplier(name: str):
    if not name or not name.strip(): return
    if name.strip() not in get_supplier_names():
        try:
            supabase.table("suppliers").insert({"name":name.strip(),"website":""}).execute()
            get_suppliers.clear()
        except: pass

BADGE_COLORS = [
    "background:#E6F1FB;color:#0C447C","background:#E1F5EE;color:#085041",
    "background:#FAEEDA;color:#633806","background:#FAECE7;color:#4A1B0C",
    "background:#EEEDFE;color:#26215C","background:#FBEAF0;color:#4B1528",
    "background:#EAF3DE;color:#173404",
]
def badge_style(name: str) -> str:
    return BADGE_COLORS[hash(name or "") % len(BADGE_COLORS)]

# ── DB helpers ─────────────────────────────────────────────────────────────────
def save_entry(vhc_id, property_name, question, answer, source, added_by,
               supplier_name="", unit_label="", supplier_url="", sentinel_url=""):
    supabase.table("knowledge_base").insert({
        "vhc_id":            vhc_id or "",
        "unit_label":        unit_label or "",
        "property_name":     property_name or "",
        "question_category": categorize(question) if question else "Other",
        "question":          question or "",
        "answer":            answer or "",
        "source":            source or "",
        "added_by":          added_by or "",
        "supplier_name":     supplier_name or "",
        "supplier_url":      supplier_url or "",
        "sentinel_url":      sentinel_url or "",
        "updated_at":        datetime.utcnow().isoformat()
    }).execute()

def update_entry(row_id, data: dict):
    data["question_category"] = categorize(data.get("question","")) if data.get("question") else "Other"
    data["updated_at"]        = datetime.utcnow().isoformat()
    supabase.table("knowledge_base").update(data).eq("id", row_id).execute()

def delete_entry(entry_id: int):
    supabase.table("knowledge_base").delete().eq("id", entry_id).execute()

def is_duplicate(property_name, question, vhc_id=""):
    if not question: return False
    all_rows = supabase.table("knowledge_base").select("property_name,question,vhc_id").execute().data
    p, q = (property_name or "").lower().strip(), (question or "").lower().strip()
    for r in all_rows:
        rp = (r.get("property_name","") or "").lower().strip()
        rq = (r.get("question","") or "").lower().strip()
        rv = (r.get("vhc_id","") or "").strip()
        if rq == q and (rp == p or (vhc_id and rv == vhc_id.strip())):
            return True
    return False

# ── File helpers ───────────────────────────────────────────────────────────────
def file_hash(raw: bytes) -> str:
    return hashlib.md5(raw).hexdigest()

def file_already_uploaded(fhash: str):
    rows = supabase.table("uploaded_files").select("*").eq("file_hash", fhash).execute().data
    return rows[0] if rows else None

def register_file(fhash, fname, supplier, uploaded_by):
    try:
        supabase.table("uploaded_files").insert({
            "file_hash":fhash,"file_name":fname,
            "supplier_name":supplier,"uploaded_by":uploaded_by
        }).execute()
    except: pass

def read_bytes(raw: bytes, fname: str) -> str:
    n = fname.lower()
    if n.endswith(".csv"):
        return pd.read_csv(io.BytesIO(raw)).to_string(index=False)
    elif n.endswith((".txt",".md")):
        return raw.decode("utf-8", errors="ignore")
    elif n.endswith(".pdf"):
        try:
            import pypdf
            return "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(raw)).pages)
        except Exception as e: return f"ERROR: {e}"
    elif n.endswith(".docx"):
        try:
            import docx
            return "\n".join(p.text for p in docx.Document(io.BytesIO(raw)).paragraphs if p.text.strip())
        except Exception as e: return f"ERROR: {e}"
    else:
        try: return raw.decode("utf-8", errors="ignore")
        except: return "ERROR: Unreadable file."

def extract_entries(content: str) -> list:
    prompt = f"""You are analyzing vacation rental property data.
Extract every useful piece of property information and return a JSON array.
Each item must have:
- "property_name": property name or address (required)
- "vhc_id": VHC or property ID if present, else ""
- "unit_label": unit number/label if present, else ""
- "question": a clear question this info answers (required)
- "answer": the answer (required)
Only include confident entries. No guessing. Return ONLY raw JSON array, no backticks.
Text:
{content[:7000]}"""
    try:
        r = ask_ai(prompt).strip().replace("```json","").replace("```","").strip()
        s, e = r.find("["), r.rfind("]")+1
        return json.loads(r[s:e]) if s>=0 and e>0 else []
    except Exception as ex:
        st.error(f"AI parse error: {ex}")
        return []

def scrape(url: str, query: str) -> str:
    try:
        soup = BeautifulSoup(requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15).content, "html.parser")
        for t in soup(["script","style","nav","footer","header"]): t.decompose()
        text = soup.get_text(" ", strip=True)[:6000]
        return ask_ai(f'Search for: "{query}"\n\nWebsite text:\n{text}\n\nIf found: FOUND: [answer]. If not: NOT_FOUND')
    except Exception as e: return f"ERROR: {e}"

def search_kb(query: str) -> str:
    rows = supabase.table("knowledge_base").select("*").execute().data
    if not rows: return "NOT_FOUND"
    prompt = f"""VacayHome assistant. Team member asked: "{query}"
Knowledge base:
{json.dumps(rows, indent=2, default=str)[:8000]}
If relevant match found, give a clear answer. Include supplier name, property name, and any links available.
Also return a JSON footer on a new line formatted exactly like:
META: {{"supplier":"...","added_by":"...","source":"...","date":"...","supplier_url":"...","sentinel_url":"..."}}
If no match: respond exactly NOT_FOUND."""
    return ask_ai(prompt)

# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════
st.title("🏠 VHC Knowledge Base")
st.caption("Your team's single source of truth for property information.")
st.markdown("---")

tab_search, tab_upload, tab_add, tab_suppliers, tab_view = st.tabs([
    "🔍  Search", "📤  Bulk Upload", "➕  Add Entry", "🏢  Suppliers", "📋  View / Edit All"
])

# ══ SEARCH ════════════════════════════════════════════════════════════════════
with tab_search:
    st.markdown("### What would you like to know?")
    st.markdown("<span style='font-size:14px;color:gray;'>Type a question in plain English — use the property name, address, or VHC ID.</span>", unsafe_allow_html=True)
    st.markdown("")

    # Pre-fill from example chip clicks
    if "search_prefill" not in st.session_state:
        st.session_state["search_prefill"] = ""

    query = st.text_input(
        "Your question",
        value=st.session_state["search_prefill"],
        placeholder="e.g.  Does Mountain River Chalet have air conditioning?  |  What is the pet fee for VHC 410966?",
        label_visibility="collapsed"
    )

    sup_names = get_supplier_names()
    c1, c2 = st.columns([2,3])
    with c1:
        sel_sup = st.selectbox("Filter by supplier (optional)", ["All suppliers"] + sup_names, key="s_sup")
    with c2:
        auto_web = get_supplier_website(sel_sup) if sel_sup != "All suppliers" else ""
        with st.expander("🌐  Add supplier website to search automatically if not found"):
            sup_url = st.text_input("Supplier website URL", value=auto_web, placeholder="https://www.blueswellrentals.com", key="sup_url_search")

    search_clicked = st.button("🔍  Search Knowledge Base", type="primary", use_container_width=True)

    # Example chips
    st.markdown("<div style='margin-top:12px;font-size:12px;color:gray;font-weight:500;'>Common questions to try:</div>", unsafe_allow_html=True)
    chip_cols = st.columns(4)
    for i, eq in enumerate(EXAMPLE_QS):
        with chip_cols[i % 4]:
            if st.button(eq, key=f"chip_{i}", use_container_width=True):
                st.session_state["search_prefill"] = eq
                st.rerun()

    st.markdown("---")

    if search_clicked and query.strip():
        st.session_state["search_prefill"] = ""
        with st.spinner("Searching knowledge base..."):
            result = search_kb(query)

        if "NOT_FOUND" not in result:
            # Parse META footer if present
            meta = {}
            answer_text = result
            if "META:" in result:
                parts = result.split("META:")
                answer_text = parts[0].strip()
                try:
                    meta = json.loads(parts[1].strip())
                except: pass

            st.markdown(f"""
<div class='green-result'>
  <div class='result-tag'>✓ &nbsp; Answer found</div>
  <div class='result-body'>{answer_text}</div>
</div>
""", unsafe_allow_html=True)

            # Meta pills
            pills = []
            if meta.get("supplier"):   pills.append(meta["supplier"])
            if meta.get("added_by"):   pills.append(f"Added by: {meta['added_by']}")
            if meta.get("source"):     pills.append(f"Source: {meta['source']}")
            if meta.get("date"):       pills.append(meta["date"][:10])
            if pills:
                pill_html = " ".join(f"<span style='display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;border:0.5px solid #ddd;color:gray;margin:2px;'>{p}</span>" for p in pills)
                st.markdown(pill_html, unsafe_allow_html=True)

            # Links
            lc1, lc2, lc3 = st.columns(3)
            if meta.get("supplier_url"):
                with lc1: st.link_button("🔗 View on Supplier Website", meta["supplier_url"])
            if meta.get("sentinel_url"):
                with lc2: st.link_button("🔗 View in Sentinel", meta["sentinel_url"])

            st.markdown("<div class='tip-box'>Not what you were looking for? Go to <strong>Add Entry</strong> to save new information for this property.</div>", unsafe_allow_html=True)

        else:
            st.warning("⚠️  Not found in knowledge base.")
            if sup_url.strip():
                with st.spinner("Searching supplier website..."):
                    web = scrape(sup_url.strip(), query)
                if "FOUND:" in web:
                    ans = web.replace("FOUND:","").strip()
                    st.success("✅  Found on supplier website!")
                    st.write(ans)
                    st.markdown("---")
                    st.info("💾  Save this so your team never has to look it up again.")
                    sc1,sc2,sc3 = st.columns(3)
                    with sc1: sv_vhc  = st.text_input("VHC ID (optional)", key="sv_vhc")
                    with sc2: sv_prop = st.text_input("Property name *",    key="sv_prop")
                    with sc3: sv_by   = st.text_input("Your name *",        key="sv_by")
                    if st.button("💾  Save to Knowledge Base", key="save_web"):
                        if sv_prop and sv_by:
                            sup = "" if sel_sup == "All suppliers" else sel_sup
                            save_entry(sv_vhc, sv_prop, query, ans, "Supplier website", sv_by, sup)
                            st.success("Saved!")
                        else: st.error("Fill in Property name and Your name.")
                elif "ERROR" in web:
                    st.error(web)
                    st.info("📧  Contact the supplier directly.")
                else:
                    st.error("❌  Not found on supplier website either.")
                    st.info("📧  Contact supplier. Then save their answer in Add Entry.")
            else:
                st.info("👆  Expand the supplier website section above to search automatically.")

    elif search_clicked:
        st.warning("Please type a question first.")

# ══ BULK UPLOAD ═══════════════════════════════════════════════════════════════
with tab_upload:
    st.subheader("Upload a file to extract and store property information")
    st.caption("CSV, Word (.docx), PDF, or text files. AI reads it and extracts all property info automatically.")
    sup_names = get_supplier_names()
    if not sup_names:
        st.warning("⚠️  No suppliers yet. Go to Suppliers tab first.")
    else:
        up_sup  = st.selectbox("Which supplier does this file belong to? *", ["— Select —"] + sup_names)
        up_file = st.file_uploader("Choose a file", type=["csv","txt","pdf","docx","md"])
        up_by   = st.text_input("Your name *", placeholder="e.g. Maria", key="up_by")

        if up_file and up_by and up_sup != "— Select —":
            if st.button("🤖  Analyze & Extract Information", type="primary"):
                raw   = up_file.read()
                fhash = file_hash(raw)
                dup   = file_already_uploaded(fhash)
                if dup:
                    st.error(f"⚠️  This exact file was already uploaded on {str(dup.get('uploaded_at',''))[:10]} by **{dup.get('uploaded_by','')}** for **{dup.get('supplier_name','')}**. Cancelled.")
                else:
                    with st.spinner("Reading file..."):
                        text = read_bytes(raw, up_file.name)
                    if text.startswith("ERROR"):
                        st.error(text)
                    else:
                        st.info("✅  File read. Analyzing with AI...")
                        with st.spinner("Extracting information (20–30 seconds)..."):
                            entries = extract_entries(text)
                        valid = [e for e in entries if e.get("property_name","").strip() and e.get("question","").strip() and e.get("answer","").strip()]
                        if not valid:
                            st.warning("⚠️  No clear property Q&A found.")
                        else:
                            st.success(f"✅  Found **{len(valid)} entries** for **{up_sup}**")
                            st.session_state.update({
                                "ex_entries":valid,"ex_file":up_file.name,
                                "ex_supplier":up_sup,"ex_by":up_by,"ex_hash":fhash
                            })

        if st.session_state.get("ex_entries"):
            valid    = st.session_state["ex_entries"]
            filename = st.session_state["ex_file"]
            supplier = st.session_state["ex_supplier"]
            by       = st.session_state["ex_by"]
            fhash    = st.session_state["ex_hash"]
            st.markdown("---")
            st.markdown("**Review entries — then click Save All:**")
            for e in valid:
                with st.expander(f"🏠  {e.get('property_name','')[:50]}  |  {e.get('question','')[:60]}"):
                    c1,c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Property:** {e.get('property_name','')}")
                        if e.get('vhc_id'):     st.markdown(f"**VHC ID:** {e['vhc_id']}")
                        if e.get('unit_label'): st.markdown(f"**Unit:** {e['unit_label']}")
                        st.markdown(f"**Supplier:** {supplier}")
                    with c2:
                        st.markdown(f"**Category:** {categorize(e.get('question',''))}")
                    st.markdown(f"**Q:** {e.get('question','')}")
                    st.markdown(f"**A:** {e.get('answer','')}")
            st.markdown("---")
            if st.button(f"💾  Save All {len(valid)} Entries to Knowledge Base", type="primary"):
                saved = skipped = 0
                for e in valid:
                    prop = e.get("property_name","")
                    q    = e.get("question","")
                    vhc  = e.get("vhc_id","")
                    if is_duplicate(prop, q, vhc):
                        skipped += 1; continue
                    try:
                        save_entry(vhc, prop, q, e.get("answer",""), f"File: {filename}", by, supplier, e.get("unit_label",""))
                        saved += 1
                    except Exception as ex: st.error(f"Error: {ex}")
                register_file(fhash, filename, supplier, by)
                msg = f"🎉  Saved {saved} entries for {supplier}!"
                if skipped: msg += f" ({skipped} duplicate{'s' if skipped>1 else ''} skipped)"
                st.success(msg)
                for k in ["ex_entries","ex_file","ex_supplier","ex_by","ex_hash"]:
                    st.session_state.pop(k, None)
                st.balloons()
        elif up_file and not up_by: st.warning("Enter your name.")
        elif up_file and up_sup == "— Select —": st.warning("Select a supplier.")

# ══ ADD ENTRY ═════════════════════════════════════════════════════════════════
with tab_add:
    st.subheader("Add property information")
    st.caption("Fill in the property details below. Questions & answers are optional — save now and add them later if needed.")

    sup_names = get_supplier_names()

    # ── Property details ──
    st.markdown("**Property details**")
    c1, c2 = st.columns(2)
    with c1:
        na_sup = st.selectbox("Supplier *", ["— Select —"] + sup_names + ["+ Type new supplier"], key="na_sup")
        if na_sup == "+ Type new supplier":
            na_sup = st.text_input("Type supplier name:", key="na_sup_txt")
        na_vhc  = st.text_input("VHC ID",         placeholder="e.g.  402129")
        na_unit = st.text_input("Unit Label",      placeholder="e.g.  Unit 2B / Villa 3")
        na_prop = st.text_input("Property Name *", placeholder="e.g.  66 Snapper St, Santa Rosa Beach, FL")
    with c2:
        na_main_url  = st.text_input("🌐  Supplier main website",        placeholder="https://blueswellrentals.com")
        na_sup_url   = st.text_input("🔗  Link to property on supplier site", placeholder="https://blueswellrentals.com/property/sands-of-time")
        na_sent_url  = st.text_input("🔗  Link to property in Sentinel",      placeholder="https://sentinel.vacayhomeconnect.com/suppliers/39/properties/402129")
        na_src = st.selectbox("Source *", SOURCE_OPTS)
        if na_src == "Other":
            na_src_detail = st.text_input("Please specify source *", placeholder="e.g.  https://vrbo.com/123456 or 'Manager phone call'")
        else:
            na_src_detail = ""
        na_by = st.text_input("Your name *", placeholder="e.g.  Maria")

    st.markdown("---")

    # ── Dynamic Q&A pairs ──
    st.markdown("**Questions & answers** — *optional. Add as many as you need.*")

    # Use stable pair IDs so indices don't break when removing
    if "qa_pairs" not in st.session_state:
        st.session_state["qa_pairs"] = [{"id": 0}]
        st.session_state["qa_counter"] = 1

    pairs_meta = st.session_state["qa_pairs"]
    to_remove  = None

    for i, pair in enumerate(pairs_meta):
        pid  = pair["id"]
        qkey = f"qa_q_{pid}"
        akey = f"qa_a_{pid}"
        if qkey not in st.session_state: st.session_state[qkey] = ""
        if akey not in st.session_state: st.session_state[akey] = ""

        st.markdown(f"<div style='background:#f8f8f8;border-radius:8px;padding:14px;margin-bottom:10px;'>", unsafe_allow_html=True)
        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown(f"<div style='font-size:12px;color:gray;margin-bottom:2px;font-weight:500;'>Question {i+1}</div>", unsafe_allow_html=True)
            st.text_area("Q", placeholder="e.g.  Are pets allowed?",  height=90, key=qkey, label_visibility="collapsed")
        with pc2:
            st.markdown(f"<div style='font-size:12px;color:gray;margin-bottom:2px;font-weight:500;'>Answer {i+1}</div>", unsafe_allow_html=True)
            st.text_area("A", placeholder="e.g.  Yes, $150 per stay.", height=90, key=akey, label_visibility="collapsed")
        if len(pairs_meta) > 1:
            if st.button(f"✕  Remove pair {i+1}", key=f"rm_{pid}"):
                to_remove = i
        st.markdown("</div>", unsafe_allow_html=True)

    if to_remove is not None:
        removed = st.session_state["qa_pairs"].pop(to_remove)
        st.session_state.pop(f"qa_q_{removed['id']}", None)
        st.session_state.pop(f"qa_a_{removed['id']}", None)
        st.rerun()

    if st.button("➕  Add another question & answer"):
        counter = st.session_state.get("qa_counter", len(pairs_meta))
        st.session_state["qa_pairs"].append({"id": counter})
        st.session_state["qa_counter"] = counter + 1
        st.rerun()

    st.markdown("---")

    if st.button("✅  Save to Knowledge Base", type="primary", use_container_width=True):
        final_src = na_src_detail.strip() if na_src == "Other" else na_src
        if na_prop.strip() and na_sup not in ["— Select —",""] and final_src and na_by.strip():
            ensure_supplier(na_sup)
            # Update supplier website if provided
            if na_main_url.strip():
                try:
                    supabase.table("suppliers").update({"website": na_main_url.strip()}).eq("name", na_sup.strip()).execute()
                    get_suppliers.clear()
                except: pass
            # Read Q&A values from session state (stable key approach)
            valid_pairs = []
            for pair in st.session_state.get("qa_pairs", []):
                pid = pair["id"]
                q_val = st.session_state.get(f"qa_q_{pid}", "").strip()
                a_val = st.session_state.get(f"qa_a_{pid}", "").strip()
                if q_val and a_val:
                    valid_pairs.append({"q": q_val, "a": a_val})
            if valid_pairs:
                saved = skipped = 0
                for p in valid_pairs:
                    if is_duplicate(na_prop, p["q"], na_vhc):
                        skipped += 1; continue
                    save_entry(na_vhc, na_prop, p["q"], p["a"], final_src, na_by, na_sup, na_unit, na_sup_url, na_sent_url)
                    saved += 1
                msg = f"✅  Saved {saved} Q&A pair{'s' if saved!=1 else ''} for **{na_prop}**!"
                if skipped: msg += f" ({skipped} duplicate{'s' if skipped>1 else ''} skipped)"
                st.success(msg)
            else:
                save_entry(na_vhc, na_prop, "", "", final_src, na_by, na_sup, na_unit, na_sup_url, na_sent_url)
                st.success(f"✅  Property **{na_prop}** registered. Come back to add questions & answers later.")
            # Reset Q&A pairs
            for pair in st.session_state.get("qa_pairs", []):
                pid = pair["id"]
                st.session_state.pop(f"qa_q_{pid}", None)
                st.session_state.pop(f"qa_a_{pid}", None)
            st.session_state["qa_pairs"]   = [{"id": 0}]
            st.session_state["qa_counter"] = 1
            st.balloons()
        else:
            if na_src == "Other" and not na_src_detail.strip():
                st.error("Please specify the source when selecting 'Other'.")
            else:
                st.error("Please fill in: Supplier, Property Name, Source, and Your Name.")

# ══ SUPPLIERS ═════════════════════════════════════════════════════════════════
with tab_suppliers:
    st.subheader("Manage Your Suppliers")
    st.caption("Add suppliers here first — they appear in all dropdowns across the app.")
    with st.form("add_sup_form"):
        fc1, fc2 = st.columns(2)
        with fc1: new_name = st.text_input("Supplier Name *", placeholder="e.g.  Blue Swell Rentals")
        with fc2: new_web  = st.text_input("Main Website URL", placeholder="e.g.  https://blueswellrentals.com")
        if st.form_submit_button("➕  Add Supplier", type="primary"):
            if new_name.strip():
                try:
                    supabase.table("suppliers").insert({"name":new_name.strip(),"website":new_web.strip()}).execute()
                    get_suppliers.clear()
                    st.success(f"✅  Added **{new_name}**!")
                    st.rerun()
                except Exception as e:
                    st.warning("Already exists." if "unique" in str(e).lower() else f"Error: {e}")
            else: st.error("Enter a supplier name.")
    st.markdown("---")
    sups = get_suppliers()
    st.markdown(f"**{len(sups)} supplier{'s' if len(sups)!=1 else ''}**")
    for s in sups:
        with st.expander(f"🏢  {s['name']}"):
            c1,c2 = st.columns(2)
            with c1:
                st.markdown(f"**Name:** {s['name']}")
                web = s.get('website') or ''
                if web:
                    st.markdown(f"**Website:** [{web}]({web})")
                else:
                    st.markdown("**Website:** —")
            with c2:
                st.markdown(f"**Added:** {(s.get('created_at') or '')[:10] or '—'}")
            if st.button("🗑️  Delete supplier", key=f"delsup_{s['id']}"):
                supabase.table("suppliers").delete().eq("id", s["id"]).execute()
                get_suppliers.clear()
                st.success("Deleted.")
                st.rerun()

# ══ VIEW / EDIT ALL ═══════════════════════════════════════════════════════════
with tab_view:
    st.subheader("All Knowledge Base Entries")
    sup_names = get_supplier_names()
    f1,f2,f3 = st.columns(3)
    with f1: f_sup  = st.selectbox("Filter by supplier", ["All"] + sup_names)
    with f2: f_cat  = st.selectbox("Filter by category", CAT_OPTS)
    with f3: f_prop = st.text_input("Search by property name", placeholder="Type to filter...")
    if st.button("🔄  Refresh"): st.rerun()

    rows = supabase.table("knowledge_base").select("*").order("created_at", desc=True).execute().data
    if f_sup  != "All":  rows = [r for r in rows if r.get("supplier_name","") == f_sup]
    if f_cat  != "All":  rows = [r for r in rows if r.get("question_category","") == f_cat]
    if f_prop.strip():   rows = [r for r in rows if f_prop.lower() in (r.get("property_name","") or "").lower()]

    if "selected_ids" not in st.session_state: st.session_state["selected_ids"] = set()
    sel = st.session_state["selected_ids"]

    ba1,ba2,ba3,ba4 = st.columns([1.5,1.5,2,5])
    with ba1:
        if st.button("☑️  Select all"):
            st.session_state["selected_ids"] = {r["id"] for r in rows}
            for r in rows: st.session_state[f"chk_{r['id']}"] = True
            st.rerun()
    with ba2:
        if st.button("⬜  Clear all"):
            st.session_state["selected_ids"] = set()
            for r in rows: st.session_state[f"chk_{r['id']}"] = False
            st.rerun()
    with ba3:
        if sel:
            if st.button(f"🗑️  Delete selected ({len(sel)})", type="primary"):
                for rid in sel: delete_entry(rid)
                st.session_state["selected_ids"] = set()
                st.success(f"Deleted {len(sel)} entries.")
                st.rerun()
    with ba4:
        if sel: st.markdown(f"<span style='color:gray;font-size:13px;'>{len(sel)} selected</span>", unsafe_allow_html=True)

    st.markdown(f"**{len(rows)} entr{'y' if len(rows)==1 else 'ies'} found**")

    if not rows:
        st.info("No entries yet. Add a supplier, then upload a file or add entries manually.")
    else:
        # Pre-load supplier websites for fast lookup
        sup_lookup = {s["name"]: s.get("website","") or "" for s in get_suppliers()}

        h0,h1,h2,h3,h4,h5 = st.columns([0.4,1.8,2.5,3,1.2,1])
        for h,lbl in zip([h0,h1,h2,h3,h4,h5],["","SUPPLIER","PROPERTY","QUESTION / ANSWER","CATEGORY","ACTIONS"]):
            with h: st.markdown(f"<span style='font-size:11px;color:gray;font-weight:600;'>{lbl}</span>", unsafe_allow_html=True)
        st.markdown("<hr style='margin:4px 0;border:none;border-top:1px solid #eee;'>", unsafe_allow_html=True)

        for row in rows:
            eid      = row["id"]
            edit_key = f"edit_mode_{eid}"
            open_key = f"open_{eid}"
            if edit_key not in st.session_state: st.session_state[edit_key] = False
            if open_key not in st.session_state: st.session_state[open_key] = False

            if not st.session_state[edit_key]:
                sup      = row.get("supplier_name","") or ""
                cat      = row.get("question_category","") or "Other"
                vhc      = row.get("vhc_id","") or ""
                unit     = row.get("unit_label","") or ""
                prop     = (row.get("property_name","") or "")[:45]
                q        = (row.get("question","") or "")
                ans      = (row.get("answer","") or "")
                sup_lnk  = row.get("supplier_url","") or ""
                sent_lnk = row.get("sentinel_url","") or ""
                checked  = eid in sel

                r0,r1,r2,r3,r4,r5 = st.columns([0.4,1.8,2.5,3,1.2,1])
                with r0:
                    chk = st.checkbox("", value=checked, key=f"chk_{eid}", label_visibility="collapsed")
                    if chk: sel.add(eid)
                    else:   sel.discard(eid)
                with r1:
                    if sup:
                        st.markdown(f"<span style='display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:500;{badge_style(sup)}'>{sup}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span style='color:gray;font-size:12px;'>—</span>", unsafe_allow_html=True)
                with r2:
                    sub = " | ".join(filter(None,[f"VHC: {vhc}" if vhc else "", f"Unit: {unit}" if unit else ""]))
                    if st.button(f"🏠 {prop}", key=f"open_btn_{eid}", help="Click to expand full details"):
                        st.session_state[open_key] = not st.session_state[open_key]
                        st.rerun()
                    if sub: st.markdown(f"<span style='font-size:11px;color:gray;'>{sub}</span>", unsafe_allow_html=True)
                    # All 3 links always visible
                    sup_main = sup_lookup.get(sup, "")
                    row_links = []
                    if sup_main:  row_links.append(f"<a href='{sup_main}' target='_blank' style='font-size:11px;'>🌐 Supplier site</a>")
                    if sup_lnk:  row_links.append(f"<a href='{sup_lnk}'  target='_blank' style='font-size:11px;'>🔗 Property page</a>")
                    if sent_lnk: row_links.append(f"<a href='{sent_lnk}' target='_blank' style='font-size:11px;'>🔗 Sentinel</a>")
                    if row_links:
                        st.markdown(" &nbsp;·&nbsp; ".join(row_links), unsafe_allow_html=True)
                with r3:
                    if q:
                        st.markdown(f"<span style='font-size:13px;font-weight:500;'>{q[:70]}</span>", unsafe_allow_html=True)
                        st.markdown(f"<span style='font-size:12px;color:gray;'>{ans[:100]}{'...' if len(ans)>100 else ''}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span style='font-size:12px;color:gray;font-style:italic;'>Property registered — no Q&A yet</span>", unsafe_allow_html=True)
                with r4:
                    st.markdown(f"<span style='display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;background:#f0f0f0;color:#555;'>{cat}</span>", unsafe_allow_html=True)
                with r5:
                    bc1,bc2 = st.columns(2)
                    with bc1:
                        if st.button("✏️", key=f"editbtn_{eid}", help="Edit"):
                            st.session_state[edit_key] = True
                            st.session_state[open_key] = False
                            st.rerun()
                    with bc2:
                        if st.button("🗑️", key=f"delbtn_{eid}", help="Delete"):
                            delete_entry(eid)
                            sel.discard(eid)
                            st.rerun()

                # ── Expanded detail panel ──
                if st.session_state[open_key]:
                    sup_main = get_supplier_website(sup) if sup else ""
                    links_html = ""
                    if sup_main:  links_html += f"<a href='{sup_main}' target='_blank' style='font-size:13px;margin-right:16px;'>🌐 {sup} main website</a>"
                    if sup_lnk:  links_html += f"<a href='{sup_lnk}'  target='_blank' style='font-size:13px;margin-right:16px;'>🔗 View on supplier site</a>"
                    if sent_lnk: links_html += f"<a href='{sent_lnk}' target='_blank' style='font-size:13px;'>🔗 View in Sentinel</a>"

                    st.markdown(f"""
<div style='background:#f8f9fa;border-left:4px solid #4A90D9;border-radius:0 8px 8px 0;padding:16px 20px;margin:4px 0 8px 0;'>
<div style='font-size:15px;font-weight:600;margin-bottom:10px;'>🏠 {row.get('property_name','')} {'&nbsp;<span style="font-size:12px;font-weight:400;color:gray;">VHC: '+vhc+'</span>' if vhc else ''}</div>
<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;font-size:13px;margin-bottom:10px;'>
<div><b>Supplier:</b> {row.get('supplier_name') or '—'}</div>
<div><b>Unit Label:</b> {row.get('unit_label') or '—'}</div>
<div><b>Category:</b> {cat}</div>
<div><b>Source:</b> {row.get('source') or '—'}</div>
<div><b>Added by:</b> {row.get('added_by') or '—'}</div>
<div><b>Date:</b> {(row.get('created_at') or '')[:10] or '—'}</div>
</div>
{'<div style="font-size:13px;margin-bottom:6px;"><b>Question:</b> '+q+'</div>' if q else ''}
{'<div style="font-size:13px;margin-bottom:10px;"><b>Answer:</b> '+ans+'</div>' if ans else ''}
{'<div style="margin-top:8px;padding-top:8px;border-top:0.5px solid #ddd;">'+links_html+'</div>' if links_html else ''}
</div>
""", unsafe_allow_html=True)

            else:
                # ── EDIT FORM ──
                st.markdown(f"**✏️  Editing: {(row.get('property_name','') or '')[:50]}**")
                all_sups = get_supplier_names()
                cur_sup  = row.get("supplier_name","")
                sup_opts = ["— Select —"] + all_sups + ["+ Type new supplier"]
                cur_idx  = sup_opts.index(cur_sup) if cur_sup in sup_opts else 0
                ec1,ec2  = st.columns(2)
                with ec1:
                    e_sup  = st.selectbox("Supplier", sup_opts, index=cur_idx, key=f"e_sup_{eid}")
                    if e_sup == "+ Type new supplier":
                        e_sup = st.text_input("Type supplier name:", key=f"e_sup_txt_{eid}")
                    e_vhc  = st.text_input("VHC ID",        value=row.get("vhc_id",""),       key=f"e_vhc_{eid}")
                    e_unit = st.text_input("Unit Label",    value=row.get("unit_label",""),    key=f"e_unit_{eid}")
                    e_prop = st.text_input("Property Name", value=row.get("property_name",""), key=f"e_prop_{eid}")
                    e_q    = st.text_input("Question",      value=row.get("question",""),      key=f"e_q_{eid}")
                    e_sup_url  = st.text_input("🔗 Supplier property URL", value=row.get("supplier_url",""),  key=f"e_supurl_{eid}")
                    e_sent_url = st.text_input("🔗 Sentinel URL",          value=row.get("sentinel_url",""),  key=f"e_senturl_{eid}")
                with ec2:
                    e_ans  = st.text_area("Answer", value=row.get("answer",""), height=130,    key=f"e_ans_{eid}")
                    cur_src = row.get("source","") or ""
                    src_idx = SOURCE_OPTS.index(cur_src) if cur_src in SOURCE_OPTS else len(SOURCE_OPTS)-1
                    e_src  = st.selectbox("Source", SOURCE_OPTS, index=src_idx,               key=f"e_src_{eid}")
                    if e_src == "Other":
                        e_src_detail = st.text_input("Specify source:", key=f"e_src_txt_{eid}")
                    else:
                        e_src_detail = ""
                    e_by   = st.text_input("Updated by", value=row.get("added_by",""),        key=f"e_by_{eid}")
                sc1,sc2 = st.columns(2)
                with sc1:
                    if st.button("💾  Save Changes", type="primary", key=f"save_edit_{eid}"):
                        final_src = e_src_detail.strip() if e_src == "Other" else e_src
                        ensure_supplier(e_sup if e_sup not in ["— Select —",""] else "")
                        update_entry(eid,{
                            "supplier_name": e_sup if e_sup not in ["— Select —",""] else "",
                            "vhc_id":        e_vhc, "unit_label":    e_unit,
                            "property_name": e_prop,"question":      e_q,
                            "answer":        e_ans, "source":        final_src,
                            "added_by":      e_by,  "supplier_url":  e_sup_url,
                            "sentinel_url":  e_sent_url,
                        })
                        st.session_state[edit_key] = False
                        st.success("✅  Updated!")
                        st.rerun()
                with sc2:
                    if st.button("✖️  Cancel", key=f"cancel_{eid}"):
                        st.session_state[edit_key] = False
                        st.rerun()

            st.markdown("<hr style='margin:2px 0;border:none;border-top:1px solid #eee;'>", unsafe_allow_html=True)
