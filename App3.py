import streamlit as st
import json
import pandas as pd
import base64
import io
import random
import time
import smtplib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import requests
from email.message import EmailMessage

class OTPManager:
    """Handle OTP generation and email sending for APH portal"""
    
    AUTHORIZED_EMAILS = [
        "CHNG0145@e.ntu.edu.sg",
        "admin@example.com",
        "admin2@example.com"
    ]
    
    def __init__(self):
        self.active_otps = {}
        self.from_mail = "CHNG0145@gmail.com"
        self.app_password = "ipes azzy jxbf cnzj"
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
    
    def is_authorized_email(self, email: str) -> bool:
        return email.lower() in [auth_email.lower() for auth_email in self.AUTHORIZED_EMAILS]
    
    def generate_otp(self) -> str:
        return "".join([str(random.randint(0, 9)) for _ in range(6)])
    
    def send_otp_email(self, to_email: str, otp: str) -> tuple[bool, str]:
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.from_mail, self.app_password)
            
            msg = EmailMessage()
            msg['Subject'] = "🐉 Dragonboat Portal - Your OTP Code"
            msg['From'] = self.from_mail
            msg['To'] = to_email
            
            email_body = f"""🐉 Dragonboat Team Portal - OTP Verification

Your OTP code is: {otp}

⏰ This code is valid for 5 minutes only.
🔒 Do not share this code with anyone.

If you didn't request this code, please ignore this email.

---
Dragonboat Team Portal Security System"""
            
            msg.set_content(email_body)
            server.send_message(msg)
            server.quit()
            
            return True, "OTP sent successfully"
            
        except Exception as e:
            return False, f"Failed to send email: {str(e)}"
    
    def generate_and_send_otp(self, email: str) -> tuple[bool, str]:
        if not self.is_authorized_email(email):
            return False, f"Email '{email}' is not authorized to receive OTP codes"
        
        otp = self.generate_otp()
        self.active_otps[email.lower()] = {
            'otp': otp,
            'expires': time.time() + 300
        }
        
        success, message = self.send_otp_email(email, otp)
        if not success and email.lower() in self.active_otps:
            del self.active_otps[email.lower()]
        
        return success, message
    
    def verify_otp(self, email: str, entered_otp: str) -> tuple[bool, str]:
        email = email.lower()
        
        if email not in self.active_otps:
            return False, "No OTP found for this email"
        
        otp_data = self.active_otps[email]
        
        if time.time() > otp_data['expires']:
            del self.active_otps[email]
            return False, "OTP has expired. Please request a new one."
        
        if otp_data['otp'] == entered_otp.strip():
            del self.active_otps[email]
            return True, "OTP verified successfully"
        else:
            return False, "Invalid OTP code"

class DataManager:
    """Handle data persistence and operations - fully dynamic portal support"""
    
    def __init__(self, filename="portal_data.json"):
        self.filename = filename
        self.data = self.load_data()
    
    def load_data(self) -> Dict:
        """Load data from file or create minimal structure"""
        if Path(self.filename).exists():
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._ensure_structure(data)
                    return data
            except Exception:
                pass
        
        # Minimal default structure - no hardcoded portals
        return {
            "passwords": {},  # APH uses OTP, no password stored
            "resources": {},
            "members": {"APH": ["admin"]},  # Only APH admin by default
            "user_progress": {},
            "announcements": {}
        }
    
    def _ensure_structure(self, data):
        """Ensure basic keys exist, but don't hardcode specific portals"""
        required_keys = ["passwords", "resources", "members", "user_progress", "announcements"]
        
        for key in required_keys:
            if key not in data:
                data[key] = {}
        
        # Ensure APH admin exists
        if "APH" not in data["members"]:
            data["members"]["APH"] = ["admin"]
    
    def _ensure_portal_structure(self, role: str):
        """Ensure a portal has all required data structures"""
        for key in ["resources", "members", "user_progress", "announcements"]:
            if role not in self.data[key]:
                if key in ["resources", "members", "announcements"]:
                    self.data[key][role] = []
                else:  # user_progress
                    self.data[key][role] = {}
    
    def save_data(self) -> bool:
        try:
            tmp_path = Path(self.filename + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, default=str, ensure_ascii=False)
            tmp_path.replace(Path(self.filename))
            return True
        except Exception as e:
            if hasattr(st, 'error'):
                st.error(f"Save failed: {e}")
            return False
    
    def get_all_portals(self) -> List[str]:
        """Get all portal names (from passwords + APH)"""
        portals = set(self.data["passwords"].keys())
        portals.add("APH")
        return sorted(list(portals))
    
    def add_portal(self, role: str, password: str):
        """Add new portal with password"""
        self.data["passwords"][role] = password
        self._ensure_portal_structure(role)
        self.save_data()
    
    def add_member(self, role: str, name: str):
        """Add member to portal"""
        name = name.strip()
        if not name:
            return
        
        self._ensure_portal_structure(role)
        
        if name not in self.data["members"][role]:
            self.data["members"][role].append(name)
            self.data["user_progress"][role][name] = {}
            
            # Initialize progress for existing completable tasks
            for resource in self.data["resources"][role]:
                if resource.get("requires_completion", True):
                    self.data["user_progress"][role][name][resource["name"]] = "Pending"
        
        self.save_data()
    
    def add_resource(self, role: str, name: str, url: str, desc: str, priority: str, deadline: str, requires_completion: bool = True):
        """Add resource/task to portal"""
        self._ensure_portal_structure(role)
        
        resource = {
            "name": name,
            "url": url,
            "description": desc,
            "priority": priority.lower(),
            "deadline": deadline,
            "requires_completion": requires_completion
        }
        
        self.data["resources"][role].append(resource)
        
        # Add to existing members' progress if completable
        if requires_completion:
            for member in self.data["members"][role]:
                if member not in self.data["user_progress"][role]:
                    self.data["user_progress"][role][member] = {}
                self.data["user_progress"][role][member][name] = "Pending"
        
        self.save_data()
    
    def update_progress(self, role: str, member: str, task: str, status: str):
        """Update member's task progress"""
        if (role in self.data["user_progress"] and member in self.data["user_progress"][role]):
            self.data["user_progress"][role][member][task] = status
            self.save_data()
    
    def add_announcement(self, role: str, title: str, content: str, image_data: str = None):
        """Add announcement to portal"""
        self._ensure_portal_structure(role)
        
        announcement = {
            "title": title,
            "content": content,
            "image_data": image_data,
            "timestamp": datetime.now().isoformat()
        }
        self.data["announcements"][role].append(announcement)
        self.save_data()
    
    def remove_portal(self, role: str):
        """Remove portal and all associated data"""
        for key in ["passwords", "resources", "members", "user_progress", "announcements"]:
            if role in self.data.get(key, {}):
                del self.data[key][role]
        self.save_data()
    
    def remove_member(self, role: str, name: str):
        """Remove member from portal"""
        if role in self.data["members"] and name in self.data["members"][role]:
            self.data["members"][role].remove(name)
            if role in self.data["user_progress"] and name in self.data["user_progress"][role]:
                del self.data["user_progress"][role][name]
            self.save_data()
    
    def remove_task(self, role: str, task_name: str):
        """Remove task from portal"""
        task_name_clean = task_name.strip().lower()
        if role in self.data.get("resources", {}):
            self.data["resources"][role] = [
                r for r in self.data["resources"][role]
                if r.get("name", "").strip().lower() != task_name_clean
            ]
            
            # Remove from progress tracking
            for member_progress in self.data.get("user_progress", {}).get(role, {}).values():
                keys_to_delete = [k for k in list(member_progress.keys()) if k.strip().lower() == task_name_clean]
                for k in keys_to_delete:
                    del member_progress[k]
            
            self.save_data()

    def remove_announcement(self, role: str, title: str):
        """Remove an announcement by title from a portal"""
        if role in self.data.get("announcements", {}):
            self.data["announcements"][role] = [
                ann for ann in self.data["announcements"][role] 
                if ann.get("title", "").strip().lower() != title.strip().lower()
            ]
            self.save_data()
    
    def get_progress_dataframe(self, role: str) -> pd.DataFrame:
        """Get progress as DataFrame for visualization"""
        if role not in self.data["members"] or role not in self.data["resources"]:
            return pd.DataFrame()
        
        members = self.data["members"][role]
        resources = [r for r in self.data["resources"][role] if r.get("requires_completion", True)]
        
        if not members or not resources:
            return pd.DataFrame()
        
        progress_data = []
        for member in members:
            row = {"Member": member}
            for resource in resources:
                status = self.data["user_progress"].get(role, {}).get(member, {}).get(resource["name"], "Pending")
                row[resource["name"]] = status
            progress_data.append(row)
        
        return pd.DataFrame(progress_data).set_index("Member")

class ChatGPTHelper:
    """Helper for ChatGPT API integration"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
    
    def analyze_data(self, df: pd.DataFrame, prompt: str) -> str:
        if not self.api_key:
            return "API key required"
        
        csv_text = df.to_csv()
        full_prompt = f"{prompt}\n\nData:\n{csv_text}"
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": full_prompt}],
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"API Error: {response.status_code}"
        except Exception as e:
            return f"Error: {str(e)}"

def authenticate_user(credential: str, data_manager: DataManager, otp_manager: OTPManager, otp_code: str = None) -> Optional[str]:
    """Authenticate user - OTP for APH, password for others"""
    if '@' in credential and otp_manager.is_authorized_email(credential):
        if otp_code:
            success, message = otp_manager.verify_otp(credential, otp_code)
            if success:
                return "APH"
        return None
    
    for role, password in data_manager.data["passwords"].items():
        if credential == password:
            return role
    return None

def render_announcements(role: str, data_manager: DataManager):
    """Render announcements section"""
    announcements = data_manager.data["announcements"].get(role, [])
    if not announcements:
        return
    
    st.markdown("### 📢 Announcements")
    for ann in reversed(announcements[-5:]):
        with st.expander(f"📅 {ann['title']} ({ann['timestamp'][:10]})"):
            if ann.get("image_data"):
                try:
                    image_bytes = base64.b64decode(ann["image_data"])
                    st.image(image_bytes, use_column_width=True)
                except:
                    st.error("Image display failed")
            st.write(ann["content"])
    st.markdown("---")

def render_login_page():
    """Login page with OTP and password options"""
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0;">
        <h1>🐉 Dragonboat Team Portal</h1>
        <p style="font-size: 1.2rem; color: #666;">Secure team management system</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🛡️ APH Admin Login")
        
        email_input = st.text_input("Email Address", placeholder="Enter your authorized email")
        
        if st.button("Send OTP", key="send_otp"):
            if email_input:
                if "otp_manager" not in st.session_state:
                    st.session_state.otp_manager = OTPManager()
                
                success, message = st.session_state.otp_manager.generate_and_send_otp(email_input)
                
                if success:
                    st.session_state.email_for_otp = email_input
                    st.success(f"✅ {message}")
                    st.info("📱 Check your email for the 6-digit OTP code")
                else:
                    st.error(f"❌ {message}")
            else:
                st.warning("⚠️ Please enter your email address")
        
        if "email_for_otp" in st.session_state:
            st.markdown("---")
            st.markdown("### 🔢 Enter OTP Code")
            
            otp_input = st.text_input("OTP Code", placeholder="Enter 6-digit code", max_chars=6)
            
            col_verify, col_resend = st.columns(2)
            
            with col_verify:
                if st.button("Verify OTP", key="verify_otp", type="primary"):
                    if otp_input:
                        role = authenticate_user(
                            st.session_state.email_for_otp, 
                            st.session_state.data_manager, 
                            st.session_state.otp_manager, 
                            otp_input
                        )
                        if role:
                            st.session_state.role = role
                            st.success("✅ Welcome to APH Portal!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid or expired OTP")
                    else:
                        st.warning("⚠️ Please enter the OTP code")
            
            with col_resend:
                if st.button("Resend OTP", key="resend_otp"):
                    success, message = st.session_state.otp_manager.generate_and_send_otp(
                        st.session_state.email_for_otp
                    )
                    if success:
                        st.success("✅ New OTP sent!")
                    else:
                        st.error(f"❌ {message}")
        
        st.markdown("---")
        st.markdown("### 🔑 Team Member Login")
        password = st.text_input("Team Password", type="password")
        
        if st.button("Login", type="primary", use_container_width=True):
            if password:
                role = authenticate_user(password, st.session_state.data_manager, st.session_state.otp_manager)
                if role:
                    st.session_state.role = role
                    st.success(f"✅ Welcome to {role} Portal!")
                    st.rerun()
                else:
                    st.error("❌ Invalid password")
            else:
                st.warning("Enter password")

def render_progress_visualization(role: str, data_manager: DataManager):
    """Render progress table with status emojis"""
    df = data_manager.get_progress_dataframe(role)
    if df.empty:
        st.info("No progress data available")
        return

    status_mapping = {"Completed": "🟢 Completed", "Pending": "🔴 Pending", "In Progress": "🟡 In Progress"}
    df_display = df.applymap(lambda v: status_mapping.get(v, v))
    st.dataframe(df_display, use_container_width=True)

def render_data_analysis():
    """Render CSV upload and ChatGPT analysis"""
    st.markdown("### 📊 Data Analysis")
    
    tab1, tab2 = st.tabs(["Upload CSV", "Paste Data"])
    df = None
    
    with tab1:
        uploaded_file = st.file_uploader("Choose CSV file", type="csv")
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.dataframe(df)
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
    
    with tab2:
        pasted_data = st.text_area("Paste CSV data", height=200)
        if pasted_data:
            try:
                df = pd.read_csv(io.StringIO(pasted_data))
                st.dataframe(df)
            except Exception as e:
                st.error(f"Invalid CSV format: {e}")
    
    if df is not None:
        st.markdown("### 🤖 ChatGPT Analysis")
        api_key = st.text_input("OpenAI API Key", type="password")
        prompt = st.text_area("Analysis Prompt", value="Analyze this data and provide insights:")
        
        if st.button("Analyze", type="primary"):
            if api_key and prompt:
                chatgpt = ChatGPTHelper(api_key)
                with st.spinner("Analyzing..."):
                    result = chatgpt.analyze_data(df, prompt)
                    st.markdown("#### 🔍 Result")
                    st.write(result)
            else:
                st.warning("Provide API key and prompt")

def render_name_selection():
    """Name selection for team members"""
    role = st.session_state.role
    data_manager = st.session_state.data_manager
    
    st.markdown(f"### Welcome to {role} Portal")
    st.markdown("Please select or enter your name:")
    
    existing_members = data_manager.data["members"].get(role, [])
    
    if existing_members:
        selected_name = st.selectbox("Select existing member:", [""] + existing_members)
        if selected_name:
            st.session_state.name = selected_name
            st.rerun()
    
    st.markdown("Or enter new name:")
    new_name = st.text_input("Your name:")
    
    if st.button("Continue"):
        if new_name:
            data_manager.add_member(role, new_name)
            st.session_state.name = new_name
            st.rerun()
        else:
            st.warning("Please enter your name")

def render_aph_dashboard():
    """APH admin dashboard"""
    data_manager = st.session_state.data_manager
    
    st.markdown("""
    <div style="background: linear-gradient(90deg, #8b0000, #dc143c); 
                color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;">
        <h1>🛡️ APH Admin Portal</h1>
        <p>Administrative Portal Handler</p>
    </div>
    """, unsafe_allow_html=True)
    
    render_announcements("APH", data_manager)
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Progress Overview", "Task Management", "Portal Management", 
        "Member Management", "Announcements", "Data Analysis"
    ])
    
    with tab1:
        all_portals = data_manager.get_all_portals()
        for role in all_portals:
            if role in data_manager.data["members"] and data_manager.data["members"][role]:
                st.markdown(f"#### {role} Team Progress")
                render_progress_visualization(role, data_manager)
            else:
                st.markdown(f"#### {role} Team - No members yet")
    
    with tab2:
        st.markdown("### 📋 Task Management")
        
        all_portals = data_manager.get_all_portals()
        
        # Add Task
        with st.form("add_task_form"):
            col1, col2 = st.columns(2)
            with col1:
                task_role = st.selectbox("Portal", all_portals)
                task_name = st.text_input("Task Name")
                task_url = st.text_input("URL (optional)")
                task_desc = st.text_area("Description")
            with col2:
                priority = st.selectbox("Priority", ["Low", "Medium", "High"])
                deadline = st.date_input("Deadline")
                requires_completion = st.checkbox("Requires Completion", value=True)
            
            if st.form_submit_button("Add Task"):
                if task_role and task_name and task_desc:
                    data_manager.add_resource(
                        task_role, task_name, task_url or "#", task_desc,
                        priority, deadline.strftime("%Y-%m-%d"), requires_completion
                    )
                    st.success(f"✅ Task added to {task_role}!")
                    st.rerun()
                else:
                    st.warning("⚠️ Fill in all required fields")
        
        # Remove Task
        st.markdown("### 🗑️ Remove Task")
        portal_for_task = st.selectbox("Select Portal", [""] + all_portals, key="task_portal")
        
        if portal_for_task and portal_for_task in data_manager.data.get("resources", {}):
            tasks = [r["name"] for r in data_manager.data["resources"][portal_for_task]]
            if tasks:
                task_to_remove = st.selectbox("Select Task", tasks, key="task_to_remove")
                if st.button("Remove Task", type="secondary"):
                    data_manager.remove_task(portal_for_task, task_to_remove)
                    st.success(f"✅ Task '{task_to_remove}' removed!")
                    st.rerun()
            else:
                st.info("No tasks in this portal")
    
    with tab3:
        st.markdown("### 🏢 Portal Management")
        
        # Add Portal
        with st.form("add_portal_form"):
            st.markdown("#### Create New Portal")
            new_role = st.text_input("Portal Name")
            new_password = st.text_input("Portal Password", type="password")
            
            if st.form_submit_button("Create Portal"):
                if new_role and new_password:
                    data_manager.add_portal(new_role, new_password)
                    st.success(f"✅ Portal '{new_role}' created!")
                    st.rerun()
                else:
                    st.warning("⚠️ Fill in both fields")
        
        # Remove Portal
        st.markdown("#### Remove Portal")
        removable_portals = list(data_manager.data["passwords"].keys())  # Exclude APH
        
        if removable_portals:
            portal_to_remove = st.selectbox("Select Portal to Remove", removable_portals, key="remove_portal")
            if st.button("Remove Portal", type="secondary"):
                data_manager.remove_portal(portal_to_remove)
                st.success(f"✅ Portal '{portal_to_remove}' removed!")
                st.rerun()
        else:
            st.info("No removable portals (APH cannot be removed)")
    
    with tab4:
        st.markdown("### 👥 Member Management")
        
        all_portals = data_manager.get_all_portals()
        
        # Add Member
        with st.form("add_member_form"):
            st.markdown("#### Add Member")
            member_role = st.selectbox("Portal", all_portals)
            member_name = st.text_input("Member Name")
            
            if st.form_submit_button("Add Member"):
                if member_role and member_name:
                    data_manager.add_member(member_role, member_name)
                    st.success(f"✅ Member added to {member_role}!")
                    st.rerun()
                else:
                    st.warning("⚠️ Please fill in both fields")
        
        # Remove Member
        st.markdown("#### Remove Member")
        portal_for_member = st.selectbox("Select Portal", [""] + all_portals, key="member_portal")
        
        if portal_for_member and portal_for_member in data_manager.data.get("members", {}):
            members = data_manager.data["members"][portal_for_member]
            if members:
                member_to_remove = st.selectbox("Select Member", [""] + members, key="member_to_remove")
                if member_to_remove and st.button("Remove Member", type="secondary"):
                    data_manager.remove_member(portal_for_member, member_to_remove)
                    st.success(f"✅ Member '{member_to_remove}' removed!")
                    st.rerun()
            else:
                st.info("No members in this portal")
    
    with tab5:
        st.markdown("### 📢 Announcement Management")
        
        all_portals = data_manager.get_all_portals()
        
        with st.form("add_announcement"):
            ann_role = st.selectbox("Target Portal", all_portals)
            ann_title = st.text_input("Title")
            ann_content = st.text_area("Content", height=150)
            ann_image = st.file_uploader("Image (optional)", type=['png', 'jpg', 'jpeg'])
            
            if st.form_submit_button("Post Announcement", type="primary"):
                if ann_title and ann_content:
                    image_data = None
                    if ann_image:
                        try:
                            image_data = base64.b64encode(ann_image.read()).decode()
                        except Exception as e:
                            st.error(f"Error processing image: {e}")
                    
                    data_manager.add_announcement(ann_role, ann_title, ann_content, image_data)
                    st.success(f"✅ Posted to {ann_role}!")
                    st.rerun()
                else:
                    st.warning("⚠️ Please fill in title and content")

            # Remove Announcement
            st.markdown("### 🗑️ Remove Announcement")
            all_portals = data_manager.get_all_portals()
            portal_for_ann = st.selectbox("Select Portal", [""] + all_portals, key="remove_ann_portal")

            if portal_for_ann and portal_for_ann in data_manager.data.get("announcements", {}):
                announcements = data_manager.data["announcements"][portal_for_ann]
                if announcements:
                    ann_titles = [ann["title"] for ann in announcements]
                    ann_to_remove = st.selectbox("Select Announcement to Remove", [""] + ann_titles, key="ann_to_remove")
                    
                    if ann_to_remove and st.button("Remove Announcement", type="secondary"):
                        data_manager.remove_announcement(portal_for_ann, ann_to_remove)
                        st.success(f"✅ Announcement '{ann_to_remove}' removed from {portal_for_ann}!")
                        st.rerun()
                else:
                    st.info("No announcements in this portal")

    
    with tab6:
        render_data_analysis()

def render_team_dashboard():
    """Team member dashboard"""
    data_manager = st.session_state.data_manager
    role = st.session_state.role
    name = st.session_state.name
    
    st.markdown(f"# {role} Portal - Welcome {name}!")
    
    render_announcements(role, data_manager)
    
    st.markdown("### 📋 Resources & Tasks")
    resources = data_manager.data["resources"].get(role, [])
    
    if not resources:
        st.info("No resources available")
        return
    
    for i, resource in enumerate(resources):
        priority_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        priority_icon = priority_colors.get(resource.get('priority', 'medium').lower(), "🟡")
        
        with st.expander(f"{priority_icon} {resource['name']} ({resource.get('priority', 'Medium').title()} Priority)"):
            st.write(resource['description'])
            
            if resource.get('url') and resource['url'] != '#':
                st.markdown(f"🔗 [Open Resource]({resource['url']})")
            
            if resource.get('deadline'):
                st.write(f"📅 Deadline: {resource['deadline']}")
            
            if resource.get('requires_completion', True):
                # Ensure user progress structure exists
                if role not in data_manager.data["user_progress"]:
                    data_manager.data["user_progress"][role] = {}
                if name not in data_manager.data["user_progress"][role]:
                    data_manager.data["user_progress"][role][name] = {}
                
                current_status = data_manager.data["user_progress"][role][name].get(resource['name'], 'Pending')
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    status_colors = {"Completed": "🟢", "In Progress": "🟡", "Pending": "🔴"}
                    status_icon = status_colors.get(current_status, "🔴")
                    st.write(f"Status: {status_icon} **{current_status}**")
                
                with col2:
                    options = ["Pending", "In Progress", "Completed"]
                    try:
                        default_index = options.index(current_status)
                    except ValueError:
                        default_index = 0

                    # Create unique key using hash of resource name to avoid conflicts
                    resource_key = f"status_{hash(resource['name'])}_{i}"
                    new_status = st.selectbox(
                        "Update Status",
                        options,
                        index=default_index,
                        key=resource_key
                    )

                    update_key = f"update_{hash(resource['name'])}_{i}"
                    if st.button("Update", key=update_key):
                        try:
                            data_manager.update_progress(role, name, resource['name'], new_status)
                            st.success("Status updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating status: {str(e)}")
            else:
                st.info("ℹ️ This is an informational resource (no completion required)")

def init_session_state():
    """Initialize session state"""
    if "role" not in st.session_state:
        st.session_state.role = None
    if "name" not in st.session_state:
        st.session_state.name = None
    if "data_manager" not in st.session_state:
        st.session_state.data_manager = DataManager()
    if "otp_manager" not in st.session_state:
        st.session_state.otp_manager = OTPManager()

def main():
    """Main application"""
    st.set_page_config(
        page_title="Dragonboat Team Portal",
        page_icon="🐉",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    st.markdown("""
    <style>
    .stApp > header {visibility: hidden;}
    .stDeployButton {display: none;}
    footer {visibility: hidden;}
    .stForm {
        border: 1px solid #e0e0e0;
        padding: 1rem;
        border-radius: 8px;
        background-color: #f9f9f9;
    }
    </style>
    """, unsafe_allow_html=True)
    
    init_session_state()
    
    try:
        if st.session_state.role is None:
            render_login_page()
        else:
            if st.session_state.role == "APH":
                render_aph_dashboard()
            else:
                if st.session_state.name is None:
                    render_name_selection()
                else:
                    render_team_dashboard()
        
        # Footer with logout
        if st.session_state.role is not None:
            st.markdown("---")
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.markdown("<small>🐉 Dragonboat Team Portal v8.0 - Dynamic Edition</small>", 
                           unsafe_allow_html=True)
            
            with col2:
                if st.session_state.role != "APH":
                    st.markdown(f"<small>Logged in as: **{st.session_state.get('name', 'Unknown')}** ({st.session_state.role})</small>", 
                               unsafe_allow_html=True)
                else:
                    st.markdown("<small>Logged in as: **APH Administrator**</small>", 
                               unsafe_allow_html=True)
            
            with col3:
                if st.button("🔓 Logout"):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()
    
    except Exception as e:
        st.error(f"Application Error: {str(e)}")
        st.error("Please refresh the page or contact support.")
        
        if st.checkbox("Show Debug Info"):
            st.exception(e)

if __name__ == "__main__":
    main()
