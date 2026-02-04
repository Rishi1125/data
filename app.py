import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from io import BytesIO
import hashlib
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import time

# Email Configuration
EMAIL_ADDRESS = "stockyy007@gmail.com"
EMAIL_PASSWORD = "yuqf hnwk rmxf hsgb"

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'chat_df' not in st.session_state:
    st.session_state.chat_df = None
if 'otp_verified' not in st.session_state:
    st.session_state.otp_verified = False
if 'pending_registration' not in st.session_state:
    st.session_state.pending_registration = None
if 'otp_code' not in st.session_state:
    st.session_state.otp_code = None
if 'otp_expiry' not in st.session_state:
    st.session_state.otp_expiry = None

# File paths for data storage
USERS_FILE = 'users.json'
DATA_FILE = 'data_entries.json'
FORM_FIELDS_FILE = 'form_fields.json'

# Gemini API Configuration
GEMINI_API_KEY = "AIzaSyCScLzMG_I3n7CvnfhXd0-hrd5clzYK9CE"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# Initialize files if they don't exist
def init_files():
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {
                "password": hashlib.sha256("admin123".encode()).hexdigest(),
                "role": "admin",
                "user_id": "USR001",
                "email": "admin@example.com",
                "enabled": True
            }
        }
        with open(USERS_FILE, 'w') as f:
            json.dump(default_users, f, indent=2)
    
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump([], f)
    
    if not os.path.exists(FORM_FIELDS_FILE):
        default_fields = [
            {"field_id": "FLD001", "field_name": "Date", "field_type": "date", "required": True, "options": [], "placeholder": "", "order": 1},
            {"field_id": "FLD002", "field_name": "Shift", "field_type": "dropdown", "required": True, "options": ["Morning", "Evening", "Night"], "placeholder": "", "order": 2},
            {"field_id": "FLD003", "field_name": "Building Name", "field_type": "dropdown", "required": True, "options": ["Building A", "Building B", "Building C", "Building D"], "placeholder": "", "order": 3},
            {"field_id": "FLD004", "field_name": "Contractor Name", "field_type": "dropdown", "required": True, "options": ["Contractor 1", "Contractor 2", "Contractor 3"], "placeholder": "", "order": 4},
            {"field_id": "FLD005", "field_name": "Labour Category", "field_type": "dropdown", "required": True, "options": ["Skilled", "Semi-Skilled", "Unskilled"], "placeholder": "", "order": 5},
            {"field_id": "FLD006", "field_name": "Job-1", "field_type": "number", "required": False, "options": [], "placeholder": "Number of workers", "order": 6},
            {"field_id": "FLD007", "field_name": "Job-2", "field_type": "number", "required": False, "options": [], "placeholder": "Number of workers", "order": 7},
            {"field_id": "FLD008", "field_name": "Job-3", "field_type": "number", "required": False, "options": [], "placeholder": "Number of workers", "order": 8}
        ]
        with open(FORM_FIELDS_FILE, 'w') as f:
            json.dump(default_fields, f, indent=2)

def load_users():
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def load_data_entries():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data_entries(entries):
    with open(DATA_FILE, 'w') as f:
        json.dump(entries, f, indent=2)

def load_form_fields():
    with open(FORM_FIELDS_FILE, 'r') as f:
        fields = json.load(f)
        return sorted(fields, key=lambda x: x.get('order', 999))

def save_form_fields(fields):
    with open(FORM_FIELDS_FILE, 'w') as f:
        json.dump(fields, f, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username, password):
    users = load_users()
    if username in users:
        user = users[username]
        if user['password'] == hash_password(password) and user.get('enabled', True):
            return True, user['role'], user['user_id']
    return False, None, None

# OTP Functions
def generate_otp():
    """Generate 6-digit OTP"""
    return str(random.randint(100000, 999999))

def send_otp_email(recipient_email, otp_code, username):
    """Send OTP via Gmail"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient_email
        msg['Subject'] = "Your OTP for Data Entry System Registration"
        
        body = f"""
        Hello {username},
        
        Your OTP for registration is: {otp_code}
        
        This OTP will expire in 5 minutes.
        
        If you did not request this, please ignore this email.
        
        Best regards,
        Data Entry System Team
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True, "OTP sent successfully"
    except Exception as e:
        return False, f"Failed to send OTP: {str(e)}"

# AI Chatbot Functions
def get_data_context():
    """Prepare data context for AI"""
    entries = load_data_entries()
    df = pd.DataFrame(entries)
    
    if df.empty:
        return "No data available", "[]"
    
    summary = f"""
    Total entries: {len(df)}
    Date range: {df.get('Date', pd.Series()).min() if 'Date' in df.columns else 'N/A'} to {df.get('Date', pd.Series()).max()}
    Columns: {list(df.columns)}
    """
    
    sample_data = df.head(10).to_json(orient='records', date_format='iso')
    
    return summary, sample_data

def ai_analyze_data(question):
    """Use Gemini AI to analyze data"""
    try:
        context, sample_data = get_data_context()
        
        full_prompt = f"""
        You are an expert data analyst for a construction labor management system.
        
        DATA CONTEXT:
        {context}
        
        SAMPLE DATA (first 10 rows):
        {sample_data}
        
        USER QUESTION: {question}
        
        INSTRUCTIONS:
        1. Analyze the labor tracking data (Date, Shift, Building, Contractor, Labour Category, Job counts)
        2. Provide clear, actionable insights with exact numbers
        3. Use tables for comparisons and summaries
        4. Suggest visualizations or exports when relevant
        5. If asked for reports, format as CSV-ready tables
        6. Be concise but comprehensive
        
        Respond with analysis, insights, and recommendations.
        """
        
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"AI Analysis Error: {str(e)}. Please check your API key or try a simpler question."

# Login page
def login_page():
    st.title("🔐 Data Entry System - Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("---")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        col_login, col_register = st.columns(2)
        
        with col_login:
            if st.button("Login", use_container_width=True):
                if username and password:
                    success, role, user_id = authenticate(username, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user_role = role
                        st.session_state.username = username
                        st.session_state.user_id = user_id
                        st.rerun()
                    else:
                        st.error("Invalid credentials or account disabled")
                else:
                    st.warning("Please enter both username and password")
        
        with col_register:
            if st.button("Register", use_container_width=True):
                st.session_state.show_register = True
                st.rerun()
        
        st.markdown("---")
        st.info("**Default Admin:** Username: `admin` | Password: `admin123`")

# Registration page with OTP
def register_page():
    st.title("📝 Register New User")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Step 1: Enter Details
        if not st.session_state.pending_registration:
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            col_back, col_submit = st.columns(2)
            
            with col_back:
                if st.button("Back to Login", use_container_width=True):
                    st.session_state.show_register = False
                    st.rerun()
            
            with col_submit:
                if st.button("Send OTP", use_container_width=True):
                    if not all([username, email, password, confirm_password]):
                        st.error("All fields are required")
                    elif password != confirm_password:
                        st.error("Passwords don't match")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters")
                    elif '@' not in email:
                        st.error("Invalid email format")
                    else:
                        users = load_users()
                        if username in users:
                            st.error("Username already exists")
                        else:
                            # Generate and send OTP
                            otp = generate_otp()
                            success, message = send_otp_email(email, otp, username)
                            
                            if success:
                                st.session_state.otp_code = otp
                                st.session_state.otp_expiry = time.time() + 300  # 5 minutes
                                st.session_state.pending_registration = {
                                    "username": username,
                                    "email": email,
                                    "password": hash_password(password)
                                }
                                st.success("✅ OTP sent to your email! Check your inbox.")
                                st.rerun()
                            else:
                                st.error(message)
        
        # Step 2: Verify OTP
        else:
            st.info(f"📧 OTP sent to: {st.session_state.pending_registration['email']}")
            
            otp_input = st.text_input("Enter 6-digit OTP", max_chars=6, key="otp_input")
            
            col_back, col_verify = st.columns(2)
            
            with col_back:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.pending_registration = None
                    st.session_state.otp_code = None
                    st.session_state.otp_expiry = None
                    st.rerun()
            
            with col_verify:
                if st.button("Verify OTP", use_container_width=True):
                    if time.time() > st.session_state.otp_expiry:
                        st.error("❌ OTP expired. Please register again.")
                        st.session_state.pending_registration = None
                        st.session_state.otp_code = None
                    elif otp_input == st.session_state.otp_code:
                        # Register user
                        users = load_users()
                        user_count = len(users)
                        user_id = f"USR{str(user_count + 1).zfill(3)}"
                        
                        users[st.session_state.pending_registration['username']] = {
                            "password": st.session_state.pending_registration['password'],
                            "role": "user",
                            "user_id": user_id,
                            "email": st.session_state.pending_registration['email'],
                            "enabled": True
                        }
                        save_users(users)
                        
                        st.success("✅ Registration successful! You can now login.")
                        st.session_state.show_register = False
                        st.session_state.pending_registration = None
                        st.session_state.otp_code = None
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Invalid OTP. Please try again.")
            
            # Show remaining time
            remaining_time = int(st.session_state.otp_expiry - time.time())
            if remaining_time > 0:
                st.caption(f"⏱️ OTP expires in: {remaining_time} seconds")

# Render dynamic form field
def render_field(field, key_prefix=""):
    field_name = field['field_name']
    field_type = field['field_type']
    required = field.get('required', False)
    options = field.get('options', [])
    placeholder = field.get('placeholder', '')
    
    label = f"{field_name} {'*' if required else ''}"
    
    if field_type == "text":
        return st.text_input(label, placeholder=placeholder, key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "textarea":
        return st.text_area(label, placeholder=placeholder, key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "number":
        return st.number_input(label, min_value=0.0, step=1.0, key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "decimal":
        return st.number_input(label, min_value=0.0, step=0.01, format="%.2f", key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "dropdown":
        return st.selectbox(label, options if options else ["No options"], key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "multiselect":
        return st.multiselect(label, options if options else ["No options"], key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "radio":
        return st.radio(label, options if options else ["No options"], key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "checkbox":
        return st.checkbox(label, key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "date":
        return st.date_input(label, key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "time":
        return st.time_input(label, key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "file":
        return st.file_uploader(label, key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "email":
        return st.text_input(label, placeholder=placeholder or "example@email.com", key=f"{key_prefix}_{field['field_id']}")
    elif field_type == "phone":
        return st.text_input(label, placeholder=placeholder or "+91 XXXXX XXXXX", key=f"{key_prefix}_{field['field_id']}")
    else:
        return st.text_input(label, key=f"{key_prefix}_{field['field_id']}")

# Data entry page with Edit/Delete
def data_entry_page():
    st.title("📊 Data Entry Form")
    st.markdown(f"**Logged in as:** {st.session_state.username} ({st.session_state.user_id})")
    
    fields = load_form_fields()
    
    if not fields:
        st.warning("No form fields configured. Please contact admin.")
        return
    
    with st.form("data_entry_form"):
        st.subheader("Enter Your Data")
        
        form_data = {}
        
        col1, col2 = st.columns(2)
        
        for idx, field in enumerate(fields):
            with col1 if idx % 2 == 0 else col2:
                value = render_field(field, "entry")
                form_data[field['field_id']] = {
                    'field_name': field['field_name'],
                    'value': value,
                    'required': field.get('required', False)
                }
        
        submitted = st.form_submit_button("Submit Entry", use_container_width=True)
        
        if submitted:
            missing_fields = []
            for field_id, data in form_data.items():
                if data['required'] and (data['value'] is None or data['value'] == "" or 
                                        (isinstance(data['value'], list) and len(data['value']) == 0)):
                    missing_fields.append(data['field_name'])
            
            if missing_fields:
                st.error(f"Please fill required fields: {', '.join(missing_fields)}")
            else:
                entry = {
                    "entry_id": f"ENT{len(load_data_entries()) + 1:05d}",
                    "user_id": st.session_state.user_id,
                    "username": st.session_state.username,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                for field_id, data in form_data.items():
                    value = data['value']
                    if hasattr(value, 'name'):
                        entry[data['field_name']] = value.name
                    elif isinstance(value, list):
                        entry[data['field_name']] = ", ".join(value)
                    elif hasattr(value, 'isoformat'):
                        entry[data['field_name']] = str(value)
                    else:
                        entry[data['field_name']] = value
                
                entries = load_data_entries()
                entries.append(entry)
                save_data_entries(entries)
                
                st.success("✅ Data entry submitted successfully!")
                st.balloons()
    
    st.markdown("---")
    st.subheader("Your Recent Entries")
    
    entries = load_data_entries()
    user_entries = [e for e in entries if e['user_id'] == st.session_state.user_id]
    
    if user_entries:
        for entry in user_entries[-10:][::-1]:
            with st.expander(f"Entry: {entry['entry_id']} - {entry.get('Date', 'N/A')}", expanded=False):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    for key, value in entry.items():
                        if key not in ['entry_id', 'user_id', 'username']:
                            st.write(f"**{key}:** {value}")
                
                with col2:
                    if st.button("✏️ Edit", key=f"edit_{entry['entry_id']}"):
                        st.session_state.edit_entry = entry
                        st.rerun()
                    
                    if st.button("🗑️ Delete", key=f"del_{entry['entry_id']}"):
                        all_entries = load_data_entries()
                        all_entries = [e for e in all_entries if e['entry_id'] != entry['entry_id']]
                        save_data_entries(all_entries)
                        st.success(f"Deleted entry {entry['entry_id']}")
                        st.rerun()
        
        # Edit Entry Dialog
        if 'edit_entry' in st.session_state:
            st.markdown("---")
            st.subheader(f"✏️ Edit Entry: {st.session_state.edit_entry['entry_id']}")
            
            with st.form("edit_entry_form"):
                edit_data = {}
                
                for field in fields:
                    field_name = field['field_name']
                    current_value = st.session_state.edit_entry.get(field_name, "")
                    
                    if field['field_type'] == "date":
                        edit_data[field_name] = st.date_input(field_name, value=pd.to_datetime(current_value) if current_value else datetime.now())
                    elif field['field_type'] == "number":
                        edit_data[field_name] = st.number_input(field_name, value=float(current_value) if current_value else 0.0)
                    elif field['field_type'] == "dropdown":
                        options = field.get('options', [])
                        index = options.index(current_value) if current_value in options else 0
                        edit_data[field_name] = st.selectbox(field_name, options, index=index)
                    else:
                        edit_data[field_name] = st.text_input(field_name, value=current_value)
                
                col_cancel, col_save = st.columns(2)
                
                with col_cancel:
                    if st.form_submit_button("Cancel", use_container_width=True):
                        del st.session_state.edit_entry
                        st.rerun()
                
                with col_save:
                    if st.form_submit_button("Save Changes", use_container_width=True):
                        all_entries = load_data_entries()
                        for entry in all_entries:
                            if entry['entry_id'] == st.session_state.edit_entry['entry_id']:
                                for key, value in edit_data.items():
                                    entry[key] = str(value)
                                entry['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                break
                        
                        save_data_entries(all_entries)
                        st.success("✅ Entry updated successfully!")
                        del st.session_state.edit_entry
                        st.rerun()
    else:
        st.info("No entries yet. Start by submitting your first entry!")

# AI Chatbot Page
def ai_chatbot_page():
    st.title("🤖 AI Data Analyst Assistant")
    st.markdown("**Ask me anything about your labor data!** 💬📊")
    
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("report_data"):
                st.dataframe(pd.read_json(message["report_data"]))
            if message.get("download_key"):
                st.download_button(
                    label="📥 Download Report",
                    data=message["download_data"],
                    file_name=message["download_key"],
                    mime="text/csv"
                )
    
    if prompt := st.chat_input("e.g., 'Show total workers by building', 'Contractor performance report'..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("🤖 AI is analyzing your data..."):
                response = ai_analyze_data(prompt)
                st.markdown(response)
                
                st.session_state.chat_history.append({
                    "role": "assistant", 
                    "content": response,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
        
        st.rerun()

# Form builder for admin
def form_builder_page():
    st.title("🔧 Form Builder")
    st.markdown("Create and manage form fields that users will fill out")
    
    tab1, tab2 = st.tabs(["📋 Current Fields", "➕ Add/Edit Field"])
    
    with tab1:
        fields = load_form_fields()
        
        if fields:
            st.subheader("Current Form Fields")
            
            for idx, field in enumerate(fields):
                with st.expander(f"{idx+1}. {field['field_name']} ({field['field_type']})", expanded=False):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        st.write(f"**Field ID:** {field['field_id']}")
                        st.write(f"**Type:** {field['field_type']}")
                        st.write(f"**Required:** {'Yes' if field.get('required', False) else 'No'}")
                    
                    with col2:
                        if field.get('options'):
                            st.write(f"**Options:** {', '.join(field['options'])}")
                        if field.get('placeholder'):
                            st.write(f"**Placeholder:** {field['placeholder']}")
                    
                    with col3:
                        col_up, col_down, col_del = st.columns(3)
                        
                        with col_up:
                            if idx > 0:
                                if st.button("⬆️", key=f"up_{field['field_id']}", help="Move up"):
                                    fields[idx], fields[idx-1] = fields[idx-1], fields[idx]
                                    for i, f in enumerate(fields):
                                        f['order'] = i + 1
                                    save_form_fields(fields)
                                    st.rerun()
                        
                        with col_down:
                            if idx < len(fields) - 1:
                                if st.button("⬇️", key=f"down_{field['field_id']}", help="Move down"):
                                    fields[idx], fields[idx+1] = fields[idx+1], fields[idx]
                                    for i, f in enumerate(fields):
                                        f['order'] = i + 1
                                    save_form_fields(fields)
                                    st.rerun()
                        
                        with col_del:
                            if st.button("🗑️", key=f"del_{field['field_id']}", help="Delete field"):
                                fields.pop(idx)
                                for i, f in enumerate(fields):
                                    f['order'] = i + 1
                                save_form_fields(fields)
                                st.success(f"Deleted field: {field['field_name']}")
                                st.rerun()
        else:
            st.info("No fields configured yet. Add your first field!")
    
    with tab2:
        st.subheader("Add New Field")
        
        with st.form("add_field_form"):
            field_name = st.text_input("Field Name *", placeholder="e.g., Customer Name")
            
            field_type = st.selectbox("Field Type *", [
                "text", "textarea", "number", "decimal", "dropdown",
                "multiselect", "radio", "checkbox", "date", "time",
                "file", "email", "phone"
            ])
            
            col1, col2 = st.columns(2)
            
            with col1:
                required = st.checkbox("Required Field", value=False)
            
            with col2:
                placeholder = st.text_input("Placeholder (optional)", placeholder="e.g., Enter your name")
            
            options = []
            if field_type in ["dropdown", "multiselect", "radio"]:
                st.markdown("**Options** (one per line)")
                options_text = st.text_area("", placeholder="Option 1\nOption 2\nOption 3", height=100)
                options = [opt.strip() for opt in options_text.split('\n') if opt.strip()]
            
            submitted = st.form_submit_button("Add Field", use_container_width=True)
            
            if submitted:
                if not field_name:
                    st.error("Field name is required")
                elif field_type in ["dropdown", "multiselect", "radio"] and not options:
                    st.error("Please provide options for this field type")
                else:
                    fields = load_form_fields()
                    
                    field_count = len(fields)
                    field_id = f"FLD{str(field_count + 1).zfill(3)}"
                    
                    new_field = {
                        "field_id": field_id,
                        "field_name": field_name,
                        "field_type": field_type,
                        "required": required,
                        "options": options,
                        "placeholder": placeholder,
                        "order": field_count + 1
                    }
                    
                    fields.append(new_field)
                    save_form_fields(fields)
                    
                    st.success(f"✅ Field '{field_name}' added successfully!")
                    st.rerun()

# Reports page
def reports_page():
    st.title("📊 Reports & Analytics")
    
    entries = load_data_entries()
    
    if not entries:
        st.warning("No data available for reports. Please add some entries first.")
        return
    
    df = pd.DataFrame(entries)
    
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
        df['Date_Display'] = df['Date'].dt.strftime('%Y-%m-%d')
    
    tab1, tab2, tab3 = st.tabs([
        "📅 Date-wise Report", 
        "🏢 Building-wise Report", 
        "📈 Summary Dashboard"
    ])
    
    with tab1:
        st.subheader("Date-wise Total Report")
        col1, col2 = st.columns(2)
        
        with col1:
            if 'Date' in df.columns:
                date_range = st.date_input(
                    "Select Date Range",
                    value=(df['Date'].min().date(), df['Date'].max().date()),
                    key="date_range_1"
                )
        
        with col2:
            if 'Building Name' in df.columns:
                buildings = ["All"] + list(df['Building Name'].unique())
                selected_building = st.selectbox("Filter by Building", buildings, key="date_building")
        
        filtered_df = df.copy()
        
        if 'Date' in df.columns and len(date_range) == 2:
            filtered_df = filtered_df[
                (filtered_df['Date'].dt.date >= date_range[0]) &
                (filtered_df['Date'].dt.date <= date_range[1])
            ]
        
        if 'Building Name' in df.columns and selected_building != "All":
            filtered_df = filtered_df[filtered_df['Building Name'] == selected_building]
        
        if not filtered_df.empty and 'Date' in filtered_df.columns:
            job_columns = [col for col in filtered_df.columns if col.startswith('Job-')]
            
            date_summary = filtered_df.groupby('Date_Display').agg({
                'entry_id': 'count',
                **{col: 'sum' for col in job_columns if col in filtered_df.columns}
            }).reset_index()
            
            date_summary.columns = ['Date', 'Total Entries'] + [f'Total {col}' for col in job_columns]
            
            st.dataframe(date_summary, use_container_width=True, hide_index=True)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                date_summary.to_excel(writer, index=False, sheet_name='Date-wise Report')
            output.seek(0)
            
            st.download_button(
                label="📥 Download Date-wise Report",
                data=output,
                file_name=f"datewise_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with tab2:
        st.subheader("Building-wise Summary")
        if 'Building Name' in df.columns:
            building_summary = df.groupby('Building Name').agg({
                'entry_id': 'count'
            }).reset_index()
            building_summary.columns = ['Building', 'Total Entries']
            st.dataframe(building_summary, use_container_width=True, hide_index=True)
    
    with tab3:
        st.subheader("Overall Statistics")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Entries", len(df))
        with col2:
            st.metric("Total Users", df['user_id'].nunique() if 'user_id' in df.columns else 0)
        with col3:
            if 'Building Name' in df.columns:
                st.metric("Buildings", df['Building Name'].nunique())

# Admin Data Management
def admin_data_management():
    st.title("📊 Data Entries Management")
    
    entries = load_data_entries()
    
    if not entries:
        st.info("No data entries yet.")
        return
    
    df = pd.DataFrame(entries)
    
    st.subheader("All Data Entries")
    
    for entry in entries[::-1]:
        with st.expander(f"Entry: {entry['entry_id']} - User: {entry.get('username', 'N/A')}", expanded=False):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                for key, value in entry.items():
                    st.write(f"**{key}:** {value}")
            
            with col2:
                if st.button("🗑️ Delete", key=f"admin_del_{entry['entry_id']}"):
                    all_entries = load_data_entries()
                    all_entries = [e for e in all_entries if e['entry_id'] != entry['entry_id']]
                    save_data_entries(all_entries)
                    st.success(f"Deleted entry {entry['entry_id']}")
                    st.rerun()

# User Management
def user_management_page():
    st.title("👥 User Management")
    
    users = load_users()
    
    st.subheader("All Users")
    
    for username, user_data in users.items():
        with st.expander(f"{username} - {user_data['role'].upper()}", expanded=False):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**User ID:** {user_data['user_id']}")
                st.write(f"**Email:** {user_data['email']}")
                st.write(f"**Role:** {user_data['role']}")
                st.write(f"**Status:** {'Enabled' if user_data.get('enabled', True) else 'Disabled'}")
            
            with col2:
                if username != "admin":
                    if st.button("🗑️ Delete", key=f"del_user_{username}"):
                        del users[username]
                        save_users(users)
                        st.success(f"Deleted user: {username}")
                        st.rerun()
                    
                    current_status = user_data.get('enabled', True)
                    toggle_text = "Disable" if current_status else "Enable"
                    if st.button(f"🔄 {toggle_text}", key=f"toggle_{username}"):
                        users[username]['enabled'] = not current_status
                        save_users(users)
                        st.success(f"{toggle_text}d user: {username}")
                        st.rerun()

# Admin dashboard
def admin_dashboard():
    st.title("👨‍💼 Admin Dashboard")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🔧 Form Builder", 
        "📊 Data Entries", 
        "🤖 AI Chatbot",
        "📈 Reports",
        "👥 User Management", 
        "📥 Export Data"
    ])
    
    with tab1: form_builder_page()
    with tab2: admin_data_management()
    with tab3: ai_chatbot_page()
    with tab4: reports_page()
    with tab5: user_management_page()
    with tab6:
        st.subheader("Export All Data")
        entries = load_data_entries()
        if entries:
            df = pd.DataFrame(entries)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='All Data')
            output.seek(0)
            st.download_button("📥 Download All Data", data=output, file_name="all_data.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Logout
def logout():
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.username = None
    st.session_state.user_id = None
    st.session_state.chat_history = []
    st.session_state.otp_verified = False
    st.session_state.pending_registration = None
    st.session_state.otp_code = None
    st.rerun()

# Main app
def main():
    st.set_page_config(
        page_title="Data Entry System",
        page_icon="📊",
        layout="wide"
    )
    
    init_files()
    
    if not st.session_state.logged_in:
        if st.session_state.get('show_register', False):
            register_page()
        else:
            login_page()
    else:
        with st.sidebar:
            st.title("📊 Data Entry System")
            st.markdown(f"**User:** {st.session_state.username}")
            st.markdown(f"**Role:** {st.session_state.user_role.upper()}")
            st.markdown("---")
            
            if st.button("🚪 Logout", use_container_width=True):
                logout()
        
        if st.session_state.user_role == 'admin':
            admin_dashboard()
        else:
            data_entry_page()

if __name__ == "__main__":
    main()
