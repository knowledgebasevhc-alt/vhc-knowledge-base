import streamlit as st
from groq import Groq
from supabase import create_client
import requests
from bs4 import BeautifulSoup
import json, hashlib, io, re
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="VacayHome Knowledge Base", page_icon="🏠", layout="wide")

# Add branded header
st.markdown("""
<div style='background: linear-gradient(135deg, #1956d2 0%, #0f3a7d 100%);
            padding: 20px 0;
            margin: -1.5rem -1.5rem 2rem -1.5rem;
            border-bottom: 3px solid #5a9e8f;'>
    <div style='max-width: 1400px; margin: 0 auto; padding: 0 2rem;'>
        <div style='display: flex; align-items: center; gap: 16px;'>
            <div style='font-size: 32px;'>🏠</div>
            <div>
                <h1 style='margin: 0; color: white; font-size: 28px; font-weight: 600;'>VacayHome Knowledge Base</h1>
                <p style='margin: 4px 0 0 0; color: rgba(255,255,255,0.9); font-size: 13px;'>Manage properties, suppliers, and team knowledge</p>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# VACAYHOME BRAND DESIGN THEME
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* VacayHome Brand Color Scheme */
:root {
    --corporate-navy: #1956d2;
    --corporate-teal: #5a9e8f;
    --corporate-success: #4caf50;
    --corporate-danger: #e74c3c;
    --corporate-gray: #f5f5f5;
    --corporate-border: #e0e0e0;
}

/* Main app container */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1200px;
}

/* Headers and titles */
h1, h2, h3 {
    color: var(--corporate-navy) !important;
    font-weight: 500 !important;
}

h1 { font-size: 28px !important; }
h2 { font-size: 20px !important; }
h3 { font-size: 18px !important; }

/* Tabs - Corporate style */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background-color: white;
    border-bottom: 2px solid var(--corporate-border);
    padding: 0;
}

.stTabs [data-baseweb="tab"] {
    height: 50px;
    background-color: white;
    border: 1px solid var(--corporate-border);
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    color: #666;
    padding: 0 24px;
    font-size: 14px;
    font-weight: 500;
}

.stTabs [aria-selected="true"] {
    background-color: var(--corporate-navy) !important;
    color: white !important;
    border-color: var(--corporate-navy) !important;
}

/* Buttons - Teal primary action */
.stButton > button {
    background-color: var(--corporate-teal) !important;
    color: white !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 12px 24px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    transition: background-color 0.2s;
}

.stButton > button:hover {
    background-color: #007567 !important;
}

/* Secondary buttons */
.stButton > button[kind="secondary"] {
    background-color: white !important;
    color: var(--corporate-navy) !important;
    border: 1px solid var(--corporate-border) !important;
}

/* Text inputs */
.stTextInput > div > div > input,
.stTextArea textarea,
.stSelectbox > div > div > div {
    border: 1px solid #ccc !important;
    border-radius: 4px !important;
    padding: 10px 12px !important;
    font-size: 14px !important;
}

.stTextInput > div > div > input:focus,
.stTextArea textarea:focus {
    border-color: var(--corporate-teal) !important;
    box-shadow: 0 0 0 1px var(--corporate-teal) !important;
}

/* Labels */
.stTextInput > label,
.stTextArea > label,
.stSelectbox > label,
.stFileUploader > label,
.stNumberInput > label {
    color: var(--corporate-navy) !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    margin-bottom: 8px !important;
}

/* Info/warning/success boxes */
.stAlert {
    border-radius: 4px !important;
    border-left: 4px solid !important;
}

[data-baseweb="notification"] > div {
    border-radius: 4px !important;
}

/* Success messages */
.stSuccess {
    background-color: #e8f5e9 !important;
    border-left-color: var(--corporate-success) !important;
}

/* Cards and expanders */
.streamlit-expanderHeader {
    background-color: var(--corporate-gray) !important;
    border: 1px solid var(--corporate-border) !important;
    border-radius: 4px !important;
    color: var(--corporate-navy) !important;
    font-weight: 500 !important;
}

/* File uploader */
.stFileUploader {
    border: 1px dashed #ccc !important;
    border-radius: 4px !important;
    padding: 20px !important;
}

/* Radio buttons */
.stRadio > div {
    gap: 12px;
}

.stRadio > div > label {
    background-color: var(--corporate-gray) !important;
    border: 1px solid var(--corporate-border) !important;
    border-radius: 4px !important;
    padding: 12px 16px !important;
    cursor: pointer;
}

/* Selectbox */
.stSelectbox > div > div {
    border-radius: 4px !important;
}

/* Tight row spacing - like Excel/Google Sheets */
.element-container {
    margin-bottom: 2px !important;
}

/* Forms */
.stForm {
    background-color: var(--corporate-gray);
    border: 1px solid var(--corporate-border);
    border-radius: 8px;
    padding: 1.5rem;
}

/* Spacing improvements */
.stMarkdown {
    margin-bottom: 1px !important;
}

/* Number input */
.stNumberInput > div > div > input {
    border: 1px solid #ccc !important;
    border-radius: 4px !important;
}
</style>
""", unsafe_allow_html=True)


# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Badge pill style */
.badge-pill {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    margin-right: 6px;
    margin-bottom: 4px;
}

.metric-card {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.metric-value {
    font-size: 32px;
    font-weight: 600;
    color: #1956d2;
    margin: 12px 0;
}

.metric-label {
    font-size: 14px;
    color: #666;
    font-weight: 500;
}

.divider {
    border-top: 1px solid #e0e0e0;
    margin: 20px 0;
}

.answer-box {
    background-color: #f0f4f8;
    border-left: 4px solid #1956d2;
    padding: 16px;
    border-radius: 4px;
    margin: 12px 0;
    font-size: 14px;
    line-height: 1.6;
}

.property-chip {
    display: inline-block;
    background: #E6F1FB;
    color: #0C447C;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    margin-right: 6px;
    margin-bottom: 4px;
}

.supplier-chip {
    display: inline-block;
    background: #E1F5EE;
    color: #085041;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    margin-right: 6px;
    margin-bottom: 4px;
}

.info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin: 12px 0;
}

.info-item {
    background: #f5f5f5;
    padding: 10px 12px;
    border-radius: 4px;
    font-size: 13px;
}

.info-label {
    color: #666;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 2px;
}

.info-value {
    color: #333;
    font-size: 14px;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# GROQ + SUPABASE SETUP
# ════════════════════════════════════════════════════════════════════════════════

# Initialize secrets
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

# Session state initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "client" not in st.session_state:
    st.session_state.client = Groq(api_key=GROQ_API_KEY)
if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

client = st.session_state.client
supabase = st.session_state.supabase

def ask_ai(prompt: str) -> str:
    """Ask Groq AI (NOT Streamlit chat - direct API call)"""
    try:
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"ERROR: {str(e)}"

# ════════════════════════════════════════════════════════════════════════════════
# EXTRACT FUNCTIONS (Phone, URLs, Metadata from PDFs/CSVs)
# ════════════════════════════════════════════════════════════════════════════════

def extract_phone_numbers(text: str) -> list:
    """Extract phone numbers from text"""
    patterns = [
        r'\+?1?[-.\s]?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\+?1?[-.\s]?[2-9]\d{2}[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
    ]
    numbers = []
    for pattern in patterns:
        numbers.extend(re.findall(pattern, text))
    return list(set(n.strip() for n in numbers if n))

def extract_urls(text: str) -> list:
    """Extract URLs from text"""
    pattern = r'https?://[^\s\)\\]+'
    return list(set(re.findall(pattern, text)))

def detect_supplier_metadata_file(text: str) -> dict:
    """Detect supplier name and metadata from file content"""
    lines = text.split('\n')[:20]
    text_upper = text.upper()
    
    for line in lines:
        if '@' in line:
            parts = line.split('@')
            if len(parts) == 2:
                domain = parts[1].strip().split()[0].lower()
                if domain and domain != 'example.com':
                    return {"supplier": domain, "type": "metadata"}
    
    for line in lines:
        words = line.split()
        if len(words) >= 2 and len(line) < 100:
            for word in words:
                if len(word) > 3 and word[0].isupper() and 'company' not in word.lower():
                    company_name = ' '.join(words[:3]).strip('.,;:')
                    if len(company_name) > 3:
                        return {"supplier": company_name, "type": "metadata"}
    
    return {}

def extract_qa_from_email_pdf(text: str) -> dict:
    """Extract Q&A from email PDF (forward from supplier)"""
    lines = text.split('\n')
    
    # Extract supplier from "From:" header
    supplier = ""
    for line in lines[:30]:
        if line.startswith('From:'):
            email_part = line.replace('From:', '').strip()
            email_addr = re.findall(r'[\w.-]+@[\w.-]+', email_part)
            if email_addr:
                supplier = email_addr[0].split('@')[1].replace('.com','').replace('.net','').title()
            break
    
    # Extract property from "Subject:" or signature
    property_id = ""
    for line in lines[:30]:
        if line.startswith('Subject:'):
            subj = line.replace('Subject:','').strip()
            # Look for patterns like "RE: Unit 6457", "Property 21607", etc.
            match = re.search(r'(?:unit|property|apt|#)\s*:?\s*(\d+)', subj, re.IGNORECASE)
            if match:
                property_id = match.group(1)
            break
    
    # Find the email boundary
    boundary_idx = -1
    for i, line in enumerate(lines):
        if 'On ' in line and 'wrote:' in line:
            boundary_idx = i
            break
    
    if boundary_idx == -1:
        return {"success": False, "reason": "No email thread boundary found"}
    
    # Extract question (after "Hi team," in the quoted section, before "Regards,")
    question = ""
    answer = ""
    
    # Answer is BEFORE the boundary
    answer_lines = lines[:boundary_idx]
    # Skip header lines
    answer_lines = [l for l in answer_lines if l and not l.startswith(('From:','To:','Subject:','Date:','Sent:'))]
    answer = '\n'.join(answer_lines).strip()
    
    # Question is AFTER the boundary (in quoted section)
    quoted_lines = lines[boundary_idx:]
    question_start = -1
    for i, line in enumerate(quoted_lines):
        if 'Hi team,' in line or 'Hi ' in line:
            question_start = i + 1
            break
    
    if question_start > 0:
        question_lines = []
        for line in quoted_lines[question_start:]:
            if 'Regards' in line or 'Thanks' in line or 'Best' in line:
                break
            question_lines.append(line)
        question = '\n'.join(question_lines).strip()
    
    # Auto-categorize
    category = "Other"
    q_lower = (question + " " + answer).lower()
    if "pool" in q_lower:
        category = "Pool"
    elif any(w in q_lower for w in ["parking","garage","vehicle","car","drive"]):
        category = "Parking"
    elif any(w in q_lower for w in ["pet","dog","cat","animal"]):
        category = "Pets"
    elif any(w in q_lower for w in ["golf","cart"]):
        category = "Golf Cart"
    elif any(w in q_lower for w in ["hour","open","close","time"]):
        category = "Hours of Operation"
    elif any(w in q_lower for w in ["access","enter","code","key","door"]):
        category = "Access"
    
    if question and answer:
        return {
            "success": True,
            "supplier": supplier or "Unknown",
            "property_id": property_id or "Unknown",
            "category": category,
            "question": question[:500],
            "answer": answer[:1000]
        }
    
    return {"success": False, "reason": "Could not extract question and answer"}

def extract_entries_from_chunk(csv_text: str, filename: str) -> list:
    """Extract structured entries from CSV chunk"""
    lines = csv_text.strip().split('\n')
    if len(lines) < 2:
        return []
    
    try:
        reader_lines = lines
        header = reader_lines[0].split(',')
        
        # Map CSV columns
        col_map = {}
        for i, col in enumerate(header):
            col_lower = col.lower().strip('"').strip()
            if 'name' in col_lower and 'property' in col_lower:
                col_map['property_name'] = i
            elif 'vhc' in col_lower or 'id' in col_lower:
                col_map['vhc_id'] = i
            elif 'address' in col_lower:
                col_map['address'] = i
            elif 'city' in col_lower:
                col_map['city'] = i
            elif 'state' in col_lower:
                col_map['state'] = i
        
        entries = []
        for row_text in reader_lines[1:]:
            fields = row_text.split(',')
            if not any(fields):
                continue
            
            entry = {}
            if 'property_name' in col_map and col_map['property_name'] < len(fields):
                entry['property_name'] = fields[col_map['property_name']].strip('"').strip()
            if 'vhc_id' in col_map and col_map['vhc_id'] < len(fields):
                entry['vhc_id'] = fields[col_map['vhc_id']].strip('"').strip()
            if 'address' in col_map and col_map['address'] < len(fields):
                entry['address'] = fields[col_map['address']].strip('"').strip()
            if 'city' in col_map and col_map['city'] < len(fields):
                entry['city'] = fields[col_map['city']].strip('"').strip()
            if 'state' in col_map and col_map['state'] < len(fields):
                entry['state'] = fields[col_map['state']].strip('"').strip()
            
            if entry.get('property_name') or entry.get('vhc_id'):
                entries.append(entry)
        
        return entries
    except Exception as e:
        return []

# Auto-migrate address field (one-time migration)
@st.cache_data(ttl=None)
def run_address_migration():
    try:
        all_data = supabase.table("knowledge_base").select("*").execute().data or []
        migrated = 0
        for row in all_data:
            if (row.get("address") is None or row.get("address") == "") and row.get("vhc_id"):
                # Try to find address in other rows with same vhc_id
                same_vhc = [r for r in all_data if r.get("vhc_id") == row.get("vhc_id") and r.get("address")]
                if same_vhc:
                    addr = same_vhc[0].get("address", "")
                    try:
                        supabase.table("knowledge_base").update({"address": addr}).eq("id", row["id"]).execute()
                        migrated += 1
                    except:
                        pass
    except:
        pass

run_address_migration()

# ════════════════════════════════════════════════════════════════════════════════
# MAIN LAYOUT: TABS
# ════════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Search", "📤 Upload", "📋 Q&A Manager", "🏢 Suppliers", "📊 Dashboard"])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1: SEARCH
# ════════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Search the Knowledge Base")
    st.markdown("Ask a question about properties, suppliers, or team knowledge.")
    
    search_query = st.text_input(
        "Ask a question:",
        placeholder="E.g., 'Does Unit 6457 have a pool?' or 'Are any Blue Swell units pet friendly?'",
        label_visibility="collapsed"
    )
    
    col1, col2 = st.columns([3, 1])
    with col2:
        search_btn = st.button("🔍 Search", use_container_width=True)
    
    if search_btn and search_query:
        with st.spinner("Searching knowledge base..."):
            result = search_kb(search_query)
            
            if result.startswith("PROPERTY_FOUND"):
                parts = result.split("|")
                st.info(f"✅ Found property: **{parts[1]}**")
                st.markdown(f"**Supplier:** {parts[2]} | **VHC ID:** {parts[3]}")
                if parts[4]:
                    st.markdown(f"[View Supplier](url={parts[4]})")
                if parts[5]:
                    st.markdown(f"[View in Sentinel](url={parts[5]})")
                st.warning("No specific answer yet for this question. Please contact the supplier.")
            
            elif result == "NOT_FOUND":
                st.error("❌ No information found. Try a different question or add more data.")
            
            else:
                st.markdown("### Answer")
                st.markdown(result)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2: UPLOAD (Q&A from supplier email PDF, property list CSV, or supplier metadata)
# ════════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Upload & Extract Knowledge")
    st.markdown("Three ways to add data: **Email PDFs from suppliers**, **Property CSV files**, or **Supplier contact info**")
    
    uploaded_file = st.file_uploader(
        "Upload a file (PDF, CSV, or TXT):",
        type=["pdf", "csv", "txt"],
        label_visibility="collapsed"
    )
    
    if uploaded_file:
        raw_bytes = uploaded_file.read()
        fhash = file_hash(raw_bytes)
        
        # Check for duplicate
        existing = file_already_uploaded(fhash)
        if existing:
            st.warning(f"⚠️ This file was already uploaded on {existing.get('uploaded_at','Unknown date')}")
            if st.button("✅ Continue anyway"):
                pass
            else:
                st.stop()
        
        # Parse file
        if uploaded_file.type == "application/pdf":
            try:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(raw_bytes))
                text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            except:
                text = ""
        else:
            text = raw_bytes.decode('utf-8', errors='ignore')
        
        # ROUTE 1: Email PDF (Q&A extraction)
        if "@" in text and "From:" in text and "To:" in text:
            st.markdown("#### 📧 Email Q&A Extraction")
            qa_result = extract_qa_from_email_pdf(text)
            
            if qa_result.get("success"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Supplier", qa_result.get("supplier","?"))
                with col2:
                    st.metric("Property ID", qa_result.get("property_id","?"))
                with col3:
                    st.markdown(f"<div class='badge-pill' style='{badge_style(qa_result.get('category'))}'>{qa_result.get('category')}</div>", unsafe_allow_html=True)
                
                st.markdown("**Question:**")
                question_input = st.text_area("", value=qa_result.get("question",""), height=80, label_visibility="collapsed")
                
                st.markdown("**Answer:**")
                answer_input = st.text_area("", value=qa_result.get("answer",""), height=120, label_visibility="collapsed", key="answer_area")
                
                if st.button("💾 Save Q&A"):
                    supplier_name = qa_result.get("supplier","Unknown")
                    ensure_supplier(supplier_name)
                    save_entry(
                        vhc_id=qa_result.get("property_id",""),
                        property_name="",
                        question=question_input,
                        answer=answer_input,
                        source=f"Email PDF: {uploaded_file.name}",
                        added_by=st.session_state.get("user","Unknown"),
                        supplier_name=supplier_name,
                        knowledge_type="unit"
                    )
                    register_file(fhash, uploaded_file.name, supplier_name, st.session_state.get("user","Unknown"))
                    st.success(f"✅ Q&A saved!")
            else:
                st.error(f"❌ Could not extract Q&A: {qa_result.get('reason','Unknown error')}")
        
        # ROUTE 2: Property CSV (metadata extraction)
        elif uploaded_file.type == "text/csv":
            st.markdown("#### 📊 Property CSV")
            entries = extract_entries_from_chunk(text, uploaded_file.name)
            
            if entries:
                st.markdown(f"**Found {len(entries)} properties**")
                for i, entry in enumerate(entries[:5]):
                    with st.expander(f"Property {i+1}: {entry.get('property_name', entry.get('vhc_id', '?'))}"):
                        st.json(entry)
                
                if st.button("✅ Import all properties"):
                    for entry in entries:
                        try:
                            save_entry(
                                vhc_id=entry.get('vhc_id',''),
                                property_name=entry.get('property_name',''),
                                question="",
                                answer="",
                                source=f"CSV: {uploaded_file.name}",
                                added_by=st.session_state.get("user","Unknown"),
                                supplier_name="",
                                address=entry.get('address',''),
                                knowledge_type="property"
                            )
                        except:
                            pass
                    register_file(fhash, uploaded_file.name, "", st.session_state.get("user","Unknown"))
                    st.success(f"✅ Imported {len(entries)} properties!")
            else:
                st.error("❌ Could not parse CSV. Make sure it has property data.")
        
        # ROUTE 3: Supplier metadata file (phone/website extraction)
        else:
            st.markdown("#### 🏢 Supplier Metadata")
            metadata = detect_supplier_metadata_file(text)
            phones = extract_phone_numbers(text)
            urls = extract_urls(text)
            
            supplier_name = st.text_input("Supplier Name:", value=metadata.get("supplier",""))
            supplier_website = st.text_input("Website:", value=urls[0] if urls else "")
            supplier_phone = st.text_input("Phone:", value=phones[0] if phones else "")
            
            if st.button("💾 Save Supplier"):
                try:
                    ensure_supplier(supplier_name)
                    update_data = {}
                    if supplier_website:
                        update_data["website"] = supplier_website
                    if supplier_phone:
                        update_data["phone"] = supplier_phone
                    
                    if update_data:
                        supabase.table("suppliers").update(update_data).eq("name", supplier_name).execute()
                    
                    register_file(fhash, uploaded_file.name, supplier_name, st.session_state.get("user","Unknown"))
                    st.success(f"✅ Supplier '{supplier_name}' saved!")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 3: Q&A MANAGER (Manual entry + edit/delete)
# ════════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Q&A Knowledge Base Manager")
    
    subtab1, subtab2, subtab3 = st.tabs(["➕ Add New", "✏️ Edit", "🗑️ Delete"])
    
    # SUBTAB 1: ADD NEW
    with subtab1:
        st.markdown("#### Add a new Q&A entry")
        
        with st.form("add_qa_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                vhc_id = st.text_input("VHC ID (optional):")
                property_name = st.text_input("Property Name (optional):")
                supplier_name = st.selectbox("Supplier:", [""] + get_supplier_names())
            
            with col2:
                unit_label = st.text_input("Unit Label (optional):")
                knowledge_type = st.radio("Type:", ["unit", "supplier"], horizontal=True)
                category = st.text_input("Category (optional):")
            
            question = st.text_area("Question:", height=80)
            answer = st.text_area("Answer:", height=120)
            source = st.text_input("Source (e.g., Email, Manual):", value="Manual")
            
            added_by = st.text_input("Added by:", value=st.session_state.get("user",""))
            
            submitted = st.form_submit_button("💾 Save Entry")
            
            if submitted:
                if not question or not answer:
                    st.error("Question and Answer are required!")
                elif is_duplicate(property_name, question, vhc_id):
                    st.warning("⚠️ This Q&A already exists!")
                else:
                    save_entry(
                        vhc_id=vhc_id,
                        property_name=property_name,
                        question=question,
                        answer=answer,
                        source=source,
                        added_by=added_by,
                        supplier_name=supplier_name,
                        unit_label=unit_label,
                        knowledge_type=knowledge_type
                    )
                    st.success(f"✅ Entry saved!")
    
    # SUBTAB 2: EDIT
    with subtab2:
        st.markdown("#### Edit existing entries")
        
        all_entries = supabase.table("knowledge_base").select("id, property_name, question, answer").execute().data or []
        
        if all_entries:
            # Search for entry
            search_term = st.text_input("Search by property or question:")
            
            filtered = [e for e in all_entries
                       if search_term.lower() in (e.get("property_name","") or "").lower()
                       or search_term.lower() in (e.get("question","") or "").lower()]
            
            if filtered:
                selected_entry = st.selectbox(
                    "Select entry to edit:",
                    options=filtered,
                    format_func=lambda x: f"{x.get('property_name','')} - {x.get('question','')[:50]}"
                )
                
                if selected_entry:
                    entry_id = selected_entry["id"]
                    full_entry = supabase.table("knowledge_base").select("*").eq("id", entry_id).execute().data[0]
                    
                    with st.form("edit_form"):
                        new_question = st.text_area("Question:", value=full_entry.get("question",""))
                        new_answer = st.text_area("Answer:", value=full_entry.get("answer",""))
                        new_supplier = st.text_input("Supplier:", value=full_entry.get("supplier_name",""))
                        
                        if st.form_submit_button("💾 Update"):
                            update_entry(entry_id, {
                                "question": new_question,
                                "answer": new_answer,
                                "supplier_name": new_supplier
                            })
                            st.success("✅ Entry updated!")
        else:
            st.info("No entries yet.")
    
    # SUBTAB 3: DELETE
    with subtab3:
        st.markdown("#### Delete entries")
        st.warning("⚠️ This action cannot be undone!")
        
        all_entries = supabase.table("knowledge_base").select("id, property_name, question").execute().data or []
        
        if all_entries:
            selected = st.selectbox(
                "Select entry to delete:",
                options=all_entries,
                format_func=lambda x: f"{x.get('property_name','')} - {x.get('question','')[:50]}"
            )
            
            if st.button("🗑️ Delete this entry", type="secondary"):
                delete_entry(selected["id"])
                st.success("✅ Entry deleted!")
        else:
            st.info("No entries to delete.")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 4: SUPPLIERS
# ════════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### Manage Suppliers")
    
    subtab_add, subtab_view = st.tabs(["➕ Add Supplier", "👀 View All"])
    
    with subtab_add:
        with st.form("add_supplier_form"):
            supp_name = st.text_input("Supplier Name:")
            supp_website = st.text_input("Website:")
            supp_phone = st.text_input("Phone:")
            
            if st.form_submit_button("💾 Add Supplier"):
                if supp_name:
                    try:
                        supabase.table("suppliers").insert({
                            "name": supp_name,
                            "website": supp_website,
                            "phone": supp_phone
                        }).execute()
                        get_suppliers.clear()
                        st.success(f"✅ {supp_name} added!")
                    except Exception as e:
                        st.error(f"Error: {e}")
    
    with subtab_view:
        suppliers = get_suppliers()
        
        if suppliers:
            for supplier in suppliers:
                with st.expander(f"🏢 {supplier.get('name','')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Website:** {supplier.get('website','N/A')}")
                        st.markdown(f"**Phone:** {supplier.get('phone','N/A')}")
                    with col2:
                        # Count properties
                        props = supabase.table("knowledge_base").select("id").eq("supplier_name", supplier.get("name")).execute().data or []
                        st.metric("Properties", len(props))
        else:
            st.info("No suppliers yet.")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 5: DASHBOARD
# ════════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("### Knowledge Base Dashboard")
    
    # Get stats
    all_kb = supabase.table("knowledge_base").select("*").execute().data or []
    all_suppliers = get_suppliers()
    
    total_entries = len(all_kb)
    total_suppliers = len(all_suppliers)
    entries_with_answers = len([e for e in all_kb if (e.get("question") or "").strip() and (e.get("answer") or "").strip()])
    total_properties = len(set(e.get("property_name") for e in all_kb if e.get("property_name")))
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📚 Total Entries", total_entries)
    with col2:
        st.metric("✅ Q&A Entries", entries_with_answers)
    with col3:
        st.metric("🏢 Suppliers", total_suppliers)
    with col4:
        st.metric("🏠 Properties", total_properties)
    
    st.divider()
    
    # Category breakdown
    st.markdown("### Categories")
    categories = {}
    for entry in all_kb:
        cat = entry.get("question_category", "Other")
        categories[cat] = categories.get(cat, 0) + 1
    
    if categories:
        cat_df = pd.DataFrame(list(categories.items()), columns=["Category", "Count"])
        st.bar_chart(cat_df.set_index("Category"))
    
    st.divider()
    
    # Recent entries
    st.markdown("### Recent Entries")
    recent = sorted(all_kb, key=lambda x: x.get("updated_at", ""), reverse=True)[:10]
    
    for entry in recent:
        cols = st.columns([2, 1, 1])
        with cols[0]:
            st.markdown(f"**{entry.get('property_name', entry.get('vhc_id', '?'))}**")
            st.caption(entry.get("question", "No question")[:80])
        with cols[1]:
            st.caption(entry.get("supplier_name", "N/A"))
        with cols[2]:
            st.caption(entry.get("question_category", "Other"))

# ════════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def categorize(q: str) -> str:
    """Categorize a question"""
    q_lower = (q or "").lower()
    if any(w in q_lower for w in ["pool","swim","hot tub","jacuzzi"]):   return "Pool"
    elif any(w in q_lower for w in ["parking","garage","vehicle","car"]):return "Parking"
    elif any(w in q_lower for w in ["pet","dog","cat","animal"]):        return "Pets"
    elif any(w in q_lower for w in ["golf cart","cart"]):                return "Golf Cart"
    elif any(w in q_lower for w in ["access","enter","code","lock"]):    return "Access"
    elif any(w in q_lower for w in ["fee","cost","price","charge"]):                  return "Fees"
    elif "beach" in q:                                                          return "Beach"
    elif any(w in q for w in ["wifi","internet","wireless"]):                   return "WiFi"
    elif any(w in q for w in ["tv","television","streaming","cable","smart","netflix"]): return "TV & Entertainment"
    elif any(w in q for w in ["grill","bbq","barbecue"]):                       return "Grill"
    elif any(w in q for w in ["front desk","concierge","reception"]):           return "Front Desk"
    else:                                                                       return "Other"

def extract_bedrooms(prop_name: str) -> int:
    """Extract bedroom count from property name using regex"""
    import re
    if not prop_name or not isinstance(prop_name, str):
        return None
    name_lower = str(prop_name).lower()
    # Pattern: "3BR" or "3 BR" or "3-BR" or "3 bed"
    match = re.search(r'(\d+)\s*(?:br|bed|bedroom)', name_lower)
    if match:
        return int(match.group(1))
    return None

def construct_sentinel_url(supplier_id: int, vhc_id: str) -> str:
    """Build Sentinel URL from supplier ID and VHC ID"""
    if not supplier_id or not vhc_id:
        return ""
    return f"https://sentinel.vacayhomeconnect.com/suppliers/{supplier_id}/properties/{vhc_id}/overview"

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
               supplier_name="", unit_label="", supplier_url="", sentinel_url="",
               knowledge_type="unit", bedrooms=None, starter_kit="", coffee_machine_type="", address=""):
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
        "knowledge_type":    knowledge_type or "unit",
        "bedrooms":          bedrooms,
        "starter_kit":       starter_kit or "",
        "coffee_machine_type": coffee_machine_type or "",
        "address":           address or "",
        "updated_at":        datetime.utcnow().isoformat()
    }).execute()

def update_entry(row_id, data: dict):
    data["question_category"] = categorize(data.get("question","")) if data.get("question") else "Other"
    data["updated_at"]        = datetime.utcnow().isoformat()
    if "knowledge_type" not in data:
        data["knowledge_type"] = "unit"
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

    q_lower  = query.lower()
    q_words  = set(q_lower.split())
    stop_words = {"a","an","the","is","are","do","does","can","for","of","to","in",
                  "at","on","it","i","we","my","what","how","when","where","who",
                  "which","this","that","with","have","has","be","was","will","would",
                  "there","their","they","your","get","any","all","some","just","not"}
    keywords = [w.strip("?.,!") for w in q_words
                if len(w.strip("?.,!")) > 2 and w.strip("?.,!") not in stop_words]

    def score_row(r):
        # Combine all text fields for matching
        text = " ".join(str(v) for v in [
            r.get("property_name",""), r.get("unit_label",""),
            r.get("vhc_id",""), r.get("supplier_name",""),
            r.get("question",""), r.get("answer","")
        ] if v).lower()
        
        # Boost score for VHC ID exact matches
        score = 0
        vhc_id = (r.get("vhc_id","") or "").strip()
        if vhc_id and query.strip() == vhc_id:
            return 1000  # Exact VHC ID match gets highest priority
        
        # Regular keyword scoring
        score += sum(2 if kw in (r.get("property_name","") or "").lower()
                     else 1 for kw in keywords if kw in text)
        return score

    scored = sorted(rows, key=score_row, reverse=True)

    # Split: rows with answers vs property-only registrations
    with_answers    = [r for r in scored if (r.get("question") or "").strip() and (r.get("answer") or "").strip()]
    without_answers = [r for r in scored if not (r.get("question") or "").strip()]
    supplier_rows   = [r for r in rows   if r.get("knowledge_type") == "supplier"
                       and (r.get("answer") or "").strip()]

    # Top candidates with answers
    candidates = with_answers[:40]
    # Always include supplier Q&A
    for sr in supplier_rows:
        if sr not in candidates:
            candidates.append(sr)
    candidates = candidates[:60]

    # Check if any property NAMES match the query (even without answers)
    matched_props = [r for r in without_answers
                     if score_row(r) >= 2][:5]

    # Step 1: try to find an answer
    if candidates:
        prompt = f"""You are an intelligent assistant for a vacation rental company called VacayHome.
A team member asked: "{query}"

Below are relevant knowledge base entries:
{json.dumps(candidates, indent=2, default=str)[:9000]}

Instructions:
- Search for entries that answer the question directly OR contain related information.
- Supplier-level entries (knowledge_type=supplier) apply to ALL units from that supplier.
- Unit-level entries (knowledge_type=unit) apply to one specific property.

INTELLIGENT SYNTHESIS:
- If multiple units from the same supplier have the same answer, synthesize: "All [Supplier] units [answer]" or "None of the [Supplier] units [answer]"
- Example: Query "Are any AlpenGlo units pet friendly?" + Data shows all AlpenGlo units say "No pets" → Answer: "None of the AlpenGlo units are pet friendly. All AlpenGlo properties prohibit pets."
- If you find patterns across multiple units, summarize them intelligently.
- If you find a clear direct answer, provide it with property name, supplier, and links.

RESPONSE FORMAT:
- If you can answer (directly or by synthesis), provide a clear natural language response.
- Include this footer on a new line:
  META: {{"supplier":"...","added_by":"...","source":"...","date":"...","supplier_url":"...","sentinel_url":"..."}}
- ONLY respond "NO_ANSWER" if the entries contain NO information related to the query at all.
- Never invent information not in the entries."""
        result = ask_ai(prompt)
        if "NO_ANSWER" not in result and "NOT_FOUND" not in result:
            return result

    # Step 2: property is registered but no answer yet
    if matched_props:
        prop = matched_props[0]
        pname  = prop.get("property_name","") or ""
        sup    = prop.get("supplier_name","")  or ""
        vhc    = prop.get("vhc_id","")         or ""
        slnk   = prop.get("supplier_url","")   or ""
        senlnk = prop.get("sentinel_url","")   or ""
        return (f"PROPERTY_FOUND|{pname}|{sup}|{vhc}|{slnk}|{senlnk}")

    return "NOT_FOUND"
