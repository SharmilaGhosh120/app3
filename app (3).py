# -*- coding: utf-8 -*-
"""app.py

Ky'ra Internship Dashboard for Streamlit Cloud.
Consolidates authentication, database, dashboard, and report generation with optimized queries and caching.
"""

import streamlit as st
import sqlite3
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import tempfile
import base64
import hashlib
import random
import uuid
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# --- Streamlit Config ---
st.set_page_config(page_title="Ky'ra Internship Dashboard", layout="wide", initial_sidebar_state="expanded")
sns.set_style("whitegrid")

# Hide Streamlit branding
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- Configuration ---
DB_PATH = os.path.join("/tmp", "internship_tracking.db")

# Ky'ra Brand Palette
PRIMARY_COLOR = "#50C878"  # Emerald Green
ACCENT_COLOR = "#FFD700"   # Soft Gold
BG_COLOR = "#FAF9F6"       # Light Ivory
TEXT_COLOR = "#333333"     # Deep Charcoal

# Custom CSS
st.markdown("""
<style>
body {font-family: 'Poppins', sans-serif; background-color: #FAF9F6; color: #333333;}
h1, h2, h3 {color: #50C878; font-weight: 600;}
.stButton>button {
    background-color: #50C878;
    color: white;
    border-radius: 8px;
    border: none;
    padding: 10px 20px;
}
.stButton>button:hover {
    background-color: #FFD700;
    color: #333333;
}
.sidebar .sidebar-content {background-color: #FAF9F6;}
.stMetric {background-color: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);}
</style>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# --- Mock Users (Replace with Firebase/Supabase in production) ---
USERS = {
    "student@example.com": {"name": "Alice", "password": hashlib.sha256("student123".encode()).hexdigest(), "role": "Student"},
    "college@example.com": {"name": "Prof. Smith", "password": hashlib.sha256("college123".encode()).hexdigest(), "role": "College"},
    "msme@example.com": {"name": "MSME Corp", "password": hashlib.sha256("msme123".encode()).hexdigest(), "role": "MSME"},
    "mentor@example.com": {"name": "Dr. Jones", "password": hashlib.sha256("mentor123".encode()).hexdigest(), "role": "Mentor"},
    "gov@example.com": {"name": "Gov Official", "password": hashlib.sha256("gov123".encode()).hexdigest(), "role": "Government"}
}

GREETINGS = {
    "Student": "Welcome, [Name]! Ky’ra is here to guide your journey. Let’s begin! \U0001F31F",
    "College": "Hello, [Name]! Ready to empower your students? Ky’ra is with you. \U0001F4DA",
    "MSME": "Hi, [Name]! Let’s transform your business with Ky’ra’s support! \U0001F680",
    "Mentor": "Welcome, [Name]! Your wisdom shapes futures. Let’s start! \U0001F4A1",
    "Government": "Greetings, [Name]! Driving impact with Ky’ra’s insights. \U0001F3DB"
}

MOTIVATIONAL_PROMPTS = {
    "no_progress": "You’re just starting! Log your first step with Ky’ra to shine! \U0001F680",
    "some_progress": "Great work! You’re moving forward – Ky’ra sees your progress! \U0001F4AA",
    "high_progress": "You’re a star! Keep shining with Ky’ra by your side! \U0001F31F"
}

# --- Authentication ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate_user(email, password, role):
    user_data = USERS.get(email)
    if user_data and user_data["password"] == hash_password(password) and user_data["role"] == role:
        try:
            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM users WHERE email = ?", (email,))
                user = cur.fetchone()
                if not user:
                    cur.execute("INSERT INTO users (name, email, role) VALUES (?, ?, ?)", 
                               (user_data["name"], email, role))
                    conn.commit()
                return {"email": email, "name": user_data["name"], "role": role}
        except sqlite3.Error as e:
            st.error(f"Database error during authentication: {str(e)}")
            return None
    return None

# --- Database Operations (SQLite as fallback, replace with Supabase) ---
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

@st.cache_data(ttl=3600)
def initialize_database():
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cur = conn.cursor()
            # Create tables
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    mobile TEXT,
                    role TEXT NOT NULL,
                    org TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    mentor_id INTEGER,
                    status TEXT,
                    FOREIGN KEY (mentor_id) REFERENCES users (user_id)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_mentor_id ON projects(mentor_id)")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS queries (
                    query_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    prompt TEXT,
                    response TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_queries_user_id ON queries(user_id)")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT,
                    summary TEXT,
                    week INTEGER
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_metrics_role ON metrics(role)")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS internships (
                    internship_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    company_name TEXT NOT NULL,
                    duration TEXT NOT NULL,
                    feedback TEXT,
                    msme_digitalized INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_internships_user_id ON internships(user_id)")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    rating INTEGER,
                    comments TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id)")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS courses (
                    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    course_name TEXT NOT NULL,
                    modules_completed INTEGER DEFAULT 0,
                    total_modules INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_courses_user_id ON courses(user_id)")
            
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database initialization error: {str(e)}")
        raise

@st.cache_data(ttl=300)
def fetch_user_data(email):
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT u.user_id, u.name, u.role,
                       i.company_name, i.duration, i.feedback, i.msme_digitalized,
                       c.course_name, c.modules_completed, c.total_modules
                FROM users u
                LEFT JOIN internships i ON u.user_id = i.user_id
                LEFT JOIN courses c ON u.user_id = c.user_id
                WHERE u.email = ?
            """, (email,))
            rows = cur.fetchall()
            
            if not rows:
                return None
                
            user_id, name, role = rows[0][:3]
            internships = []
            courses = []
            
            for row in rows:
                if row[3]:  # Check if internship data exists
                    internships.append({
                        "company_name": row[3],
                        "duration": row[4],
                        "feedback": row[5],
                        "msme_digitalized": row[6]
                    })
                if row[7]:  # Check if course data exists
                    courses.append({
                        "course_name": row[7],
                        "modules_completed": row[8],
                        "total_modules": row[9]
                    })
            
            return {
                "user_id": user_id,
                "name": name,
                "role": role,
                "internships": internships,
                "courses": courses
            }
    except sqlite3.Error as e:
        st.error(f"Error fetching user data: {str(e)}")
        return None

def log_internship(email, company, duration, feedback, msme_digitalized):
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM users WHERE email = ?", (email,))
            user = cur.fetchone()
            if not user:
                name = email.split("@")[0].capitalize()
                cur.execute("INSERT INTO users (name, email, role) VALUES (?, ?, ?)", (name, email, "Student"))
                conn.commit()
                cur.execute("SELECT user_id FROM users WHERE email = ?", (email,))
                user = cur.fetchone()
            user_id = user[0]
            cur.execute("""
                INSERT INTO internships (user_id, company_name, duration, feedback, msme_digitalized)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, company, duration, feedback, msme_digitalized))
            conn.commit()
            fetch_user_data.clear()
            return True
    except sqlite3.Error as e:
        st.error(f"Error logging internship: {str(e)}")
        return False

def log_course_progress(email, course_name, modules_completed, total_modules):
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM users WHERE email = ?", (email,))
            user = cur.fetchone()
            if user:
                user_id = user[0]
                cur.execute("""
                    INSERT OR REPLACE INTO courses (user_id, course_name, modules_completed, total_modules)
                    VALUES (?, ?, ?, ?)
                """, (user_id, course_name, modules_completed, total_modules))
                conn.commit()
                fetch_user_data.clear()
                return True
            return False
    except sqlite3.Error as e:
        st.error(f"Error logging course progress: {str(e)}")
        return False

@st.cache_data(ttl=300)
def fetch_metrics(role):
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM internships WHERE user_id IN (SELECT user_id FROM users WHERE role = ?)) AS total_internships,
                    (SELECT SUM(msme_digitalized) FROM internships WHERE user_id IN (SELECT user_id FROM users WHERE role = ?)) AS total_msmes,
                    (SELECT COUNT(*) FROM courses WHERE user_id IN (SELECT user_id FROM users WHERE role = ?)) AS total_courses
            """, (role, role, role))
            result = cur.fetchone()
            return {
                "total_internships": result[0],
                "total_msmes": result[1] or 0,
                "total_courses": result[2]
            }
    except sqlite3.Error as e:
        st.error(f"Error fetching metrics: {str(e)}")
        return {"total_internships": 0, "total_msmes": 0, "total_courses": 0}

@st.cache_data(ttl=300)
def fetch_reports(role):
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT u.name, u.email, i.company_name, i.duration, i.feedback, i.msme_digitalized
                FROM users u
                LEFT JOIN internships i ON u.user_id = i.user_id
                WHERE u.role = ?
                LIMIT 100
            """, (role,))
            rows = cur.fetchall()
            return [{"name": r[0], "email": r[1], "company_name": r[2], "duration": r[3], "feedback": r[4], "msme_digitalized": r[5]} for r in rows]
    except sqlite3.Error as e:
        st.error(f"Error fetching reports: {str(e)}")
        return []

def log_feedback(user_id, rating, comments):
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO feedback (user_id, rating, comments) VALUES (?, ?, ?)", (user_id, rating, comments))
            conn.commit()
            return True
    except sqlite3.Error as e:
        st.error(f"Error logging feedback: {str(e)}")
        return False

# --- API Integration (Placeholder) ---
@st.cache_data(ttl=300)
def query_kyra_api(prompt, user_id):
    return "Ky’ra: This is a placeholder response. The API is currently disabled for testing."

# --- Report Generation (Using PIL for simple image-based report) ---
def generate_pdf_report(report_data):
    try:
        width, height = 595, 842  # A4 size in pixels at 72 DPI
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        
        draw.text((100, 50), "Ky'ra Internship Report", fill='black', font=font)
        
        y = 100
        for entry in report_data:
            text = f"Name: {entry['name']}, Company: {entry['company_name'] or 'N/A'}, Duration: {entry['duration'] or 'N/A'}"
            draw.text((100, y), text, fill='black', font=font)
            y += 20
            if y > height - 50:
                break
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        pdf_buffer = BytesIO()
        pdf_img = Image.open(buffer)
        pdf_img.save(pdf_buffer, format="PDF")
        
        return pdf_buffer.getvalue()
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        return None

# --- Dashboard Rendering ---
def render_ticker():
    metrics = fetch_metrics("Student")
    ticker_html = """
    <div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px;'>
        <marquee behavior='scroll' direction='left'>
            \U0001F31F {internships} Internships Completed | \U0001F680 {msmes} MSMEs Supported | \U0001F4DA {courses} Courses Enrolled
        </marquee>
    </div>
    """.format(
        internships=metrics["total_internships"],
        msmes=metrics["total_msmes"],
        courses=metrics["total_courses"]
    )
    st.markdown(ticker_html, unsafe_allow_html=True)

def display_motivational_prompt(user_data, role):
    if role == "Student":
        internships = len(user_data.get("internships", []))
        if internships >= 3:
            prompt = MOTIVATIONAL_PROMPTS["high_progress"]
        elif internships > 0:
            prompt = MOTIVATIONAL_PROMPTS["some_progress"]
        else:
            prompt = MOTIVATIONAL_PROMPTS["no_progress"]
        st.info(prompt)

def render_student_dashboard(user):
    email = user["email"]
    user_data = fetch_user_data(email)
    
    if not user_data:
        st.error("User data not found. Please try logging in again.")
        return
    
    st.markdown(f"### Welcome, {user_data['name']}! Ky’ra is here to guide you.")
    display_motivational_prompt(user_data, "Student")
    
    st.sidebar.header("Your Journey")
    menu = ["Progress", "Log Internship", "Courses", "Feedback", "Ky’ra Chat", "Generate Report"]
    choice = st.sidebar.selectbox("Navigate", menu, format_func=lambda x: f"📍 {x}")

    metrics = fetch_metrics("Student")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Internships Completed", metrics.get("total_internships", 0))
    with col2:
        st.metric("MSMEs Supported", metrics.get("total_msmes", 0))
    with col3:
        st.metric("Courses Enrolled", metrics.get("total_courses", 0))

    if choice == "Progress":
        st.header("📈 Your Progress")
        if user_data["internships"]:
            df = pd.DataFrame(user_data["internships"])
            st.dataframe(df)
            fig, ax = plt.subplots()
            sns.countplot(x="msme_digitalized", data=df, ax=ax, palette="viridis")
            st.pyplot(fig)
        if user_data["courses"]:
            df = pd.DataFrame(user_data["courses"])
            st.dataframe(df)
        if not user_data["internships"] and not user_data["courses"]:
            st.info("No progress yet. Log an internship or enroll in a course! 😊")

    elif choice == "Log Internship":
        st.header("🛠️ Log Internship")
        with st.form("internship_form"):
            company = st.text_input("Company Name")
            duration = st.text_input("Duration (e.g., 3 months)")
            feedback = st.text_area("Feedback")
            msme_digitalized = st.number_input("MSMEs Digitalized", min_value=0)
            submit = st.form_submit_button("Submit Internship")
            if submit:
                if company and duration:
                    with st.spinner("Saving your internship..."):
                        success = log_internship(email, company, duration, feedback, msme_digitalized)
                        if success:
                            st.success("Internship logged! Ky’ra is proud of you! 🎉")
                            st.balloons()
                        else:
                            st.error("Failed to log internship.")
                else:
                    st.error("Please fill in all required fields.")

    elif choice == "Courses":
        st.header("📚 Your Courses")
        with st.form("course_form"):
            course_name = st.text_input("Course Name")
            modules_completed = st.number_input("Modules Completed", min_value=0)
            total_modules = st.number_input("Total Modules", min_value=1)
            submit = st.form_submit_button("Log Course Progress")
            if submit:
                if course_name and total_modules:
                    with st.spinner("Saving your course progress..."):
                        success = log_course_progress(email, course_name, modules_completed, total_modules)
                        if success:
                            st.success("Course progress logged! Keep learning with Ky’ra! 🌟")
                        else:
                            st.error("Failed to log course progress.")
                else:
                    st.error("Please fill in all required fields.")

    elif choice == "Feedback":
        st.header("🗣️ Share Feedback")
        if user_data:
            feedback_type = st.radio("Choose feedback method:", ["Star Rating", "Emoji Scale"])
            with st.form("feedback_form"):
                if feedback_type == "Star Rating":
                    rating = st.slider("Rate your experience", 1, 5, 3)
                    comments = st.text_area("Comments")
                else:
                    emoji_ratings = {"😊": 5, "🙂": 3, "😔": 1}
                    emoji = st.selectbox("How do you feel?", list(emoji_ratings.keys()))
                    rating = emoji_ratings[emoji]
                    comments = st.text_area("Comments (optional)")
                submit = st.form_submit_button("Submit Feedback")
                if submit:
                    with st.spinner("Submitting feedback..."):
                        success = log_feedback(user_data["user_id"], rating, comments)
                        if success:
                            st.success("Thanks for your feedback! Ky’ra appreciates you! \U0001F31F")
                        else:
                            st.error("Failed to submit feedback.")

    elif choice == "Ky’ra Chat":
        st.header("💬 Chat with Ky’ra")
        prompt = st.text_area("Ask Ky’ra anything about your journey!")
        if st.button("Send"):
            with st.spinner("Ky’ra is thinking..."):
                response = query_kyra_api(prompt, user_data["user_id"])
                st.markdown(f"**Ky’ra:** {response}")

    elif choice == "Generate Report":
        st.header("📄 Generate Report")
        with st.spinner("Generating your report..."):
            report_data = fetch_reports("Student")
            if report_data:
                pdf_bytes = generate_pdf_report(report_data)
                if pdf_bytes:
                    b64_pdf = base64.b64encode(pdf_bytes).decode()
                    href = f'<a href="data:application/octet-stream;base64,{b64_pdf}" download="internship_report.pdf">📥 Download Report</a>'
                    st.markdown(href, unsafe_allow_html=True)
                else:
                    st.error("Failed to generate report.")
            else:
                st.info("No report data available yet.")

def render_college_dashboard():
    st.header("📊 College Dashboard")
    st.markdown("### Welcome, College! Ky’ra supports your student success.")
    metrics = fetch_metrics("Student")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Students Participating", metrics.get("total_internships", 0))
    with col2:
        st.metric("Projects Submitted", metrics.get("total_msmes", 0))
    with col3:
        st.metric("Courses Enrolled", metrics.get("total_courses", 0))
    
    st.button("View Student Performance", key="college_cta")
    st.header("Reports")
    report_data = fetch_reports("Student")
    if report_data:
        df = pd.DataFrame(report_data)
        st.dataframe(df)

def render_mentor_dashboard():
    st.header("💡 Mentor Dashboard")
    st.markdown("### Welcome, Mentor! Ky’ra values your guidance.")
    metrics = fetch_metrics("Student")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Sessions Conducted", random.randint(10, 50))
    with col2:
        st.metric("Feedback Logged", random.randint(5, 30))
    
    st.button("Guide Your Students", key="mentor_cta")
    st.header("Student Progress")
    report_data = fetch_reports("Student")
    if report_data:
        df = pd.DataFrame(report_data)
        st.dataframe(df)

def render_msme_dashboard():
    st.header("🏢 MSME Dashboard")
    st.markdown("### Welcome, MSME! Ky’ra helps you digitize and grow.")
    metrics = fetch_metrics("Student")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Projects Received", metrics.get("total_msmes", 0))
    with col2:
        st.metric("Students Matched", random.randint(5, 20))
    
    st.header("Digitalization Tasks")
    with st.form("msme_task_form"):
        task = st.text_input("Task Description")
        timeline = st.date_input("Timeline")
        submit = st.form_submit_button("Submit Task")
        if submit:
            st.success("Task submitted! Ky’ra will match students soon.")

def render_government_dashboard():
    st.header("🏛️ Government Dashboard")
    st.markdown("### Welcome, Government! Ky’ra tracks your impact.")
    metrics = fetch_metrics("Student")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Colleges Onboarded", random.randint(10, 50))
    with col2:
        st.metric("Total Engagement", metrics.get("total_internships", 0))
    with col3:
        st.metric("Reports Downloaded", random.randint(5, 30))
    
    st.button("View Regional Impact", key="gov_cta")
    st.header("Program Reports")
    report_data = fetch_reports("Student")
    if report_data:
        df = pd.DataFrame(report_data)
        st.dataframe(df)

def render_dashboard(user, role):
    render_ticker()
    if role == "Student":
        render_student_dashboard(user)
    elif role == "College":
        render_college_dashboard()
    elif role == "Mentor":
        render_mentor_dashboard()
    elif role == "MSME":
        render_msme_dashboard()
    elif role == "Government":
        render_government_dashboard()

# --- Main Application ---
def main():
    st.title("🌟 Ky'ra: Your Internship Journey Mentor")
    try:
        initialize_database()
    except Exception as e:
        st.error(f"Failed to initialize database: {str(e)}")
        return

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.role = None

    if not st.session_state.authenticated:
        st.markdown("### Welcome to Ky’ra! Let’s begin your journey.")
        st.markdown("Select your role and log in to start with Ky’ra’s guidance.")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Student** \U0001F31F<br>Track internships & upskilling", unsafe_allow_html=True)
        with col2:
            st.markdown("**College/Mentor** \U0001F4DA<br>Guide student success", unsafe_allow_html=True)
        with col3:
            st.markdown("**MSME/Government** \U0001F680<br>Drive impact & digitalization", unsafe_allow_html=True)
        
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ["Student", "College", "MSME", "Mentor", "Government"])
            submit = st.form_submit_button("Login")
            if submit:
                with st.spinner("Ky’ra is authenticating..."):
                    user = authenticate_user(email, password, role)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.role = role
                        st.success(f"Welcome, {user['name']}! Ky’ra is ready to guide you! \U0001F33E")
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Try again with Ky’ra’s help.")
    else:
        user_name = st.session_state.user["name"]
        role = st.session_state.role
        greeting = GREETINGS.get(role, "Welcome back!").replace('[Name]', user_name)
        st.markdown(f"### {greeting}")
        render_dashboard(st.session_state.user, st.session_state.role)

if __name__ == "__main__":
    main()