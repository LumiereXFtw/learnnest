from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response, session, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import random
import string
import csv
from io import BytesIO, StringIO
import ast
import difflib
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import nltk
from nltk.tokenize import word_tokenize
import datetime
from werkzeug.utils import secure_filename
import secrets
from functools import wraps
from urllib.parse import urlparse
import re
import time
from dotenv import load_dotenv
import hmac
import hashlib
import base64
import uuid
from urllib.parse import urlencode
import requests
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from nltk.sentiment import SentimentIntensityAnalyzer
import google.generativeai as genai
import logging
import logging.config
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
import re
import json

# Load environment variables from .env file
load_dotenv()

nltk.download('vader_lexicon', quiet=True)

# Set Gemini API key from environment variable
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY not found in environment variables.")
    print("Please create a .env file with your Gemini API key:")
    print("1. Copy env.example to .env")
    print("2. Get a valid API key from: https://makersuite.google.com/app/apikey")
    print("3. Add it to your .env file as: GEMINI_API_KEY=your_actual_key_here")
    GEMINI_API_KEY = None  # No fallback - require valid key

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.0-flash')
else:
    gemini_model = None

def gemini_feedback(prompt):
    if not gemini_model:
        return "[Gemini AI feedback unavailable - please configure a valid API key in your .env file]"
    
    try:
        response = gemini_model.generate_content(prompt)
        return response.text if hasattr(response, 'text') else str(response)
    except Exception as e:
        return f"[Gemini error: {e}]"

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['ASSIGNMENT_UPLOAD_FOLDER'] = 'assignment_uploads'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-very-secret-key')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['WTF_CSRF_CHECK_DEFAULT'] = False
app.config['ALLOWED_SUBTITLE_EXTENSIONS'] = {'vtt', 'srt'}
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Create uploads and assignment uploads folders
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['ASSIGNMENT_UPLOAD_FOLDER']):
    os.makedirs(app.config['ASSIGNMENT_UPLOAD_FOLDER'])

# SQLite database setup
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Set up WAL mode for better concurrency
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA synchronous=NORMAL')
    c.execute('PRAGMA cache_size=10000')
    c.execute('PRAGMA temp_store=MEMORY')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, avatar TEXT, is_approved INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, display_name TEXT, bio TEXT, notif_forum INTEGER DEFAULT 1, notif_grades INTEGER DEFAULT 1, notif_announcements INTEGER DEFAULT 1, dark_mode INTEGER DEFAULT 0, badges TEXT, points INTEGER DEFAULT 0, api_token TEXT, is_blocked INTEGER DEFAULT 0, full_name TEXT, email TEXT, phone TEXT, institution TEXT, payment_screenshot TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS courses
                 (id INTEGER PRIMARY KEY, title TEXT, creator_id INTEGER, description TEXT, reference_file_path TEXT, meeting_link TEXT, outline TEXT, objectives TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS course_files
                 (id INTEGER PRIMARY KEY, course_id INTEGER, filename TEXT, file_type TEXT, subtitle_path TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS enrollments
                 (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER, enrollment_number TEXT UNIQUE, enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS threads
                 (id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT, creator_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, ext_url TEXT, ext_type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (id INTEGER PRIMARY KEY, thread_id INTEGER, user_id INTEGER, enrollment_number TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, ext_url TEXT, ext_type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS progress
                 (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER, assignment_name TEXT, status TEXT, grade INTEGER, file_path TEXT, ai_grade INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notes
                 (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS assignments
                 (id INTEGER PRIMARY KEY, course_id INTEGER, name TEXT, type TEXT, questions TEXT, correct_answers TEXT, due_date TIMESTAMP, meeting_link TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS assignment_keywords
                 (id INTEGER PRIMARY KEY, assignment_id INTEGER, keyword TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notifications
                 (id INTEGER PRIMARY KEY, user_id INTEGER, message TEXT, link TEXT, is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS resources_external
                 (id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT, url TEXT, type TEXT, transcript TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS lti_tools
                 (id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT, launch_url TEXT, consumer_key TEXT, consumer_secret TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS webhooks
                 (id INTEGER PRIMARY KEY, course_id INTEGER, url TEXT, event_type TEXT, last_status TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, username, role FROM users WHERE id = ?', (user_id,))
    user_data = c.fetchone()
    conn.close()
    if user_data:
        return User(user_data[0], user_data[1], user_data[2])
    return None

@app.context_processor
def inject_user_logo():
    """Inject user logo into all templates for creators"""
    if current_user.is_authenticated and current_user.role == 'creator':
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT logo FROM users WHERE id = ?', (current_user.id,))
        result = c.fetchone()
        conn.close()
        if result and result[0]:
            # Convert the stored path to a URL path for static files
            logo_path = result[0]
            # If the path starts with 'static/', remove it to make it a proper URL
            if logo_path.startswith('static/'):
                logo_path = '/' + logo_path
            return {'user_logo': logo_path}
    return {'user_logo': None}

# Generate random enrollment number
def generate_enrollment_number():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# AI grading function comparing student code to reference code
def ai_grade_code(student_code, reference_code):
    # AST structure comparison
    try:
        student_ast = ast.dump(ast.parse(student_code))
        ref_ast = ast.dump(ast.parse(reference_code))
        ast_score = difflib.SequenceMatcher(None, student_ast, ref_ast).ratio()
    except Exception:
        ast_score = 0
    surface_score = difflib.SequenceMatcher(None, student_code, reference_code).ratio()
    score = 0.7 * ast_score + 0.3 * surface_score
    feedback = f"Code structure similarity: {ast_score:.2f}, surface similarity: {surface_score:.2f}. "
    if score > 0.9:
        feedback += "Excellent! Your code closely matches the reference solution."
    elif score > 0.7:
        feedback += "Good job! Your code is similar, but could be improved."
    else:
        feedback += "Your code differs significantly from the reference. Review logic and structure."
    # Gemini feedback
    gemini_prompt = f"You are an expert Python tutor. Give detailed, constructive feedback for the following student code compared to the reference solution.\n\nStudent code:\n{student_code}\n\nReference code:\n{reference_code}\n\nFeedback:"
    feedback += "\nGemini AI: " + gemini_feedback(gemini_prompt)
    return round(score * 100), feedback

def ai_grade_text(student_text, keywords):
    found = [kw for kw in keywords if kw.lower() in student_text.lower()]
    coverage = len(found) / len(keywords) if keywords else 0
    sia = SentimentIntensityAnalyzer()
    sentiment = sia.polarity_scores(student_text)
    sentences = student_text.count('.') + student_text.count('!') + student_text.count('?')
    feedback = f"Keyword coverage: {coverage*100:.0f}%. Sentiment: {sentiment['compound']:.2f}. "
    if coverage > 0.8:
        feedback += "Great coverage of key points. "
    elif coverage > 0.5:
        feedback += "Partial coverage. Try to include more key concepts. "
    else:
        feedback += "Missing many key points. Review the material. "
    if sentiment['compound'] < 0:
        feedback += "Tone is negative; try to be more positive. "
    if sentences < 2:
        feedback += "Try to write more complete explanations."
    # Gemini feedback
    gemini_prompt = f"You are an expert tutor. Give detailed, constructive feedback for the following student answer.\n\nStudent answer:\n{student_text}\n\nKeywords: {', '.join(keywords)}\n\nFeedback:"
    feedback += "\nGemini AI: " + gemini_feedback(gemini_prompt)
    return round(coverage * 100), feedback

socketio = SocketIO(app)
user_sid_map = {}

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        user_sid_map[current_user.id] = request.sid

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated and current_user.id in user_sid_map:
        del user_sid_map[current_user.id]

# In-memory chat storage (for demo; replace with DB for persistence)
chat_messages = {}

ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg'}
DEFAULT_AVATAR = 'static/default_avatar.png'

def allowed_avatar(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS

def create_notification(user_id, message, link=None, notif_type=None):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Check user notification preferences
    if notif_type:
        c.execute('SELECT notif_forum, notif_grades, notif_announcements FROM users WHERE id = ?', (user_id,))
        prefs = c.fetchone()
        if prefs:
            if notif_type == 'forum' and not prefs[0]:
                conn.close()
                return
            if notif_type == 'grades' and not prefs[1]:
                conn.close()
                return
            if notif_type == 'announcements' and not prefs[2]:
                conn.close()
                return
    c.execute('INSERT INTO notifications (user_id, message, link) VALUES (?, ?, ?)', (user_id, message, link))
    conn.commit()
    conn.close()
    # Real-time notification
    sid = user_sid_map.get(user_id)
    if sid:
        socketio.emit('new_notification', {'message': message, 'link': link}, room=sid)

@app.route('/notifications')
@login_required
def notifications():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, message, link, is_read, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC', (current_user.id,))
    notifications = c.fetchall()
    c.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0', (current_user.id,))
    unread_notifications_count = c.fetchone()[0]
    conn.close()
    return render_template('notifications.html', notifications=notifications, unread_notifications_count=unread_notifications_count)

@app.route('/notifications/mark_read/<int:notification_id>')
@login_required
def mark_notification_read(notification_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notification_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))

@app.route('/')
def home():
    # Redirect to login page as the default landing page
    return redirect(url_for('login'))

@app.route('/home')
@login_required
def home_dashboard():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, title, description, creator_id, meeting_link FROM courses')
    courses = c.fetchall()
    enrolled_courses = []
    creator_courses = []
    upcoming_assignments = []
    overdue_assignments = []
    course_creators = {}
    unread_notifications_count = 0
    for course in courses:
        c.execute('SELECT username, avatar, display_name FROM users WHERE id = ?', (course[3],))
        u = c.fetchone()
        course_creators[course[0]] = {'username': u[0], 'avatar': u[1], 'display_name': u[2]} if u else {'username': '', 'avatar': '', 'display_name': ''}
    if current_user.is_authenticated:
        c.execute('SELECT course_id FROM enrollments WHERE user_id = ?', (current_user.id,))
        enrolled_courses = [row[0] for row in c.fetchall()]
        c.execute('SELECT id FROM courses WHERE creator_id = ?', (current_user.id,))
        creator_courses = [row[0] for row in c.fetchall()]
        import datetime
        today = datetime.date.today().isoformat()
        for course_id in enrolled_courses:
            c.execute('SELECT id, name, due_date FROM assignments WHERE course_id = ?', (course_id,))
            for row in c.fetchall():
                assignment_id, name, due_date = row
                if due_date:
                    if due_date >= today:
                        c.execute('SELECT 1 FROM progress WHERE user_id = ? AND course_id = ? AND assignment_name = ?', (current_user.id, course_id, name))
                        submitted = c.fetchone() is not None
                        upcoming_assignments.append({'course_id': course_id, 'assignment_id': assignment_id, 'name': name, 'due_date': due_date, 'submitted': submitted})
                    else:
                        c.execute('SELECT 1 FROM progress WHERE user_id = ? AND course_id = ? AND assignment_name = ?', (current_user.id, course_id, name))
                        submitted = c.fetchone() is not None
                        overdue_assignments.append({'course_id': course_id, 'assignment_id': assignment_id, 'name': name, 'due_date': due_date, 'submitted': submitted})
        # Fetch unread notifications count
        c.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0', (current_user.id,))
        unread_notifications_count = c.fetchone()[0]
    conn.close()
    return render_template('home.html', courses=courses, enrolled_courses=enrolled_courses, creator_courses=creator_courses, upcoming_assignments=upcoming_assignments, overdue_assignments=overdue_assignments, course_creators=course_creators, unread_notifications_count=unread_notifications_count)

@app.route('/user_directory')
@login_required
def user_directory():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT username, display_name, avatar, bio, role FROM users')
    users = c.fetchall()
    conn.close()
    return render_template('user_directory.html', users=users)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        institution = request.form['institution']
        role = 'student'
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        # Ensure new columns exist
        c.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in c.fetchall()]
        if 'full_name' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN full_name TEXT')
        if 'email' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN email TEXT')
        if 'phone' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN phone TEXT')
        if 'institution' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN institution TEXT')
        try:
            c.execute('INSERT INTO users (username, password, role, is_approved, full_name, email, phone, institution) VALUES (?, ?, ?, 0, ?, ?, ?, ?)', (username, password, role, full_name, email, phone, institution))
            conn.commit()
            flash('Registration successful! Awaiting admin approval.')
            return render_template('pending_approval.html')
        except sqlite3.IntegrityError:
            flash('Username already exists.')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT id, username, password, role, is_approved FROM users WHERE username = ?', (username,))
        user_data = c.fetchone()
        conn.close()
        if user_data and check_password_hash(user_data[2], password):
            if user_data[4] != 1:
                flash('Your account is pending admin approval.')
                return render_template('pending_approval.html')
            user = User(user_data[0], user_data[1], user_data[3])
            login_user(user)
            if user_data[3] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user_data[3] == 'creator':
                return redirect(url_for('instructor_enrollments'))
            return redirect(url_for('home_dashboard'))
        flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/create_course', methods=['GET', 'POST'])
@login_required
def create_course():
    if current_user.role != 'creator':
        flash('Only creators can create courses.')
        return redirect(url_for('home'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        outline = request.form.get('outline', '')
        objectives = request.form.get('objectives', '')
        meeting_link = request.form.get('meeting_link')
        reference_file = request.files.get('reference_file')
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        # Ensure new columns exist
        c.execute("PRAGMA table_info(courses)")
        columns = [col[1] for col in c.fetchall()]
        if 'outline' not in columns:
            c.execute('ALTER TABLE courses ADD COLUMN outline TEXT')
        if 'objectives' not in columns:
            c.execute('ALTER TABLE courses ADD COLUMN objectives TEXT')
        if 'live_session_start' not in columns:
            c.execute('ALTER TABLE courses ADD COLUMN live_session_start TEXT')
        if 'live_session_end' not in columns:
            c.execute('ALTER TABLE courses ADD COLUMN live_session_end TEXT')
        if 'live_days' not in columns:
            c.execute('ALTER TABLE courses ADD COLUMN live_days TEXT')
        
        # Get live session data
        live_session_start = request.form.get('live_session_start')
        live_session_end = request.form.get('live_session_end')
        live_days = request.form.getlist('live_days')
        live_days_str = ','.join(live_days) if live_days else ''
        
        # Create the course
        c.execute('INSERT INTO courses (title, creator_id, description, reference_file_path, meeting_link, outline, objectives, live_session_start, live_session_end, live_days) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                  (title, current_user.id, description, None, meeting_link, outline, objectives, live_session_start, live_session_end, live_days_str))
        course_id = c.lastrowid
        
        # Add chapter column to course_files if it doesn't exist
        c.execute("PRAGMA table_info(course_files)")
        columns = [col[1] for col in c.fetchall()]
        if 'chapter' not in columns:
            c.execute('ALTER TABLE course_files ADD COLUMN chapter INTEGER DEFAULT 0')
            conn.commit()
        
        # Handle multiple file uploads per chapter
        chapter_files = {}
        for key in request.files:
            if key.startswith('chapter_files_'):
                chapter_num = int(key.split('_')[-1]) - 1  # Convert to 0-based index
                files = request.files.getlist(key)
                chapter_files[chapter_num] = files
        
        # Save files for each chapter
        for chapter_num, files in chapter_files.items():
            for file in files:
                if file and file.filename:
                    filename = file.filename
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    c.execute('INSERT INTO course_files (course_id, filename, file_type, chapter) VALUES (?, ?, ?, ?)',
                              (course_id, filename, file.mimetype, chapter_num))
        
        # Handle reference file
        if reference_file and reference_file.filename:
            file_ext = os.path.splitext(reference_file.filename)[1].lower()
            if file_ext != '.py':
                conn.close()
                flash('Reference file must be a .py file.')
                return redirect(url_for('create_course'))
            if reference_file.content_length > 5 * 1024 * 1024:  # 5MB limit
                conn.close()
                flash('Reference file size exceeds 5MB limit.')
                return redirect(url_for('create_course'))
            filename = f"ref_{course_id}_{reference_file.filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            reference_file.save(file_path)
            c.execute('UPDATE courses SET reference_file_path = ? WHERE id = ?', (file_path, course_id))
        
        conn.commit()
        conn.close()
        flash('Course created successfully!')
        return redirect(url_for('home'))
    return render_template('create_course.html')

@app.route('/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if current_user.role != 'creator':
        flash('Only creators can edit courses.')
        return redirect(url_for('home'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, title, description, creator_id, reference_file_path, meeting_link FROM courses WHERE id = ?', (course_id,))
    course = c.fetchone()
    if not course:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    if course[3] != current_user.id:
        conn.close()
        flash('You are not the creator of this course.')
        return redirect(url_for('home'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        outline = request.form.get('outline', '')
        objectives = request.form.get('objectives', '')
        file = request.files.get('file')
        reference_file = request.files.get('reference_file')
        meeting_link = request.form.get('meeting_link')
        c.execute('UPDATE courses SET title = ?, description = ?, meeting_link = ?, outline = ?, objectives = ? WHERE id = ?',
                  (title, description, meeting_link, outline, objectives, course_id))
        if file:
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            c.execute('INSERT INTO course_files (course_id, filename, file_type) VALUES (?, ?, ?)',
                      (course_id, filename, file.mimetype))
        if reference_file and reference_file.filename:
            file_ext = os.path.splitext(reference_file.filename)[1].lower()
            if file_ext != '.py':
                conn.close()
                flash('Reference file must be a .py file.')
                return redirect(url_for('edit_course', course_id=course_id))
            if reference_file.content_length > 5 * 1024 * 1024:  # 5MB limit
                conn.close()
                flash('Reference file size exceeds 5MB limit.')
                return redirect(url_for('edit_course', course_id=course_id))
            # Delete existing reference file if it exists
            if course[4]:
                try:
                    os.remove(course[4])
                except OSError:
                    pass
            filename = f"ref_{course_id}_{reference_file.filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            reference_file.save(file_path)
            c.execute('UPDATE courses SET reference_file_path = ? WHERE id = ?', (file_path, course_id))
        conn.commit()
        conn.close()
        flash('Course updated successfully!')
        return redirect(url_for('home'))
    c.execute('SELECT id, filename, file_type FROM course_files WHERE course_id = ?', (course_id,))
    files = c.fetchall()
    reference_file = os.path.basename(course[4]) if course[4] else None
    conn.close()
    return render_template('edit_course.html', course_id=course_id, course_title=course[1], course_description=course[2], files=files, creator_id=course[3], reference_file=reference_file, meeting_link=course[5])

@app.route('/course/<int:course_id>/reference/delete', methods=['POST'])
@login_required
def delete_reference_file(course_id):
    if current_user.role != 'creator':
        flash('Only creators can delete reference files.')
        return redirect(url_for('home'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, creator_id, reference_file_path FROM courses WHERE id = ?', (course_id,))
    course = c.fetchone()
    if not course:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    if course[1] != current_user.id:
        conn.close()
        flash('You are not the creator of this course.')
        return redirect(url_for('home'))
    if not course[2]:
        conn.close()
        flash('No reference file to delete.')
        return redirect(url_for('edit_course', course_id=course_id))
    c.execute('UPDATE courses SET reference_file_path = NULL WHERE id = ?', (course_id,))
    conn.commit()
    conn.close()
    try:
        os.remove(course[2])
        flash('Reference file deleted successfully!')
    except OSError:
        flash('Reference file deleted from database, but could not remove from disk.')
    return redirect(url_for('edit_course', course_id=course_id))

@app.route('/course/<int:course_id>/file/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(course_id, file_id):
    if current_user.role != 'creator':
        flash('Only creators can delete files.')
        return redirect(url_for('home'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, creator_id FROM courses WHERE id = ?', (course_id,))
    course = c.fetchone()
    if not course:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    if course[1] != current_user.id:
        conn.close()
        flash('You are not the creator of this course.')
        return redirect(url_for('home'))
    c.execute('SELECT filename FROM course_files WHERE id = ? AND course_id = ?', (file_id, course_id))
    file_data = c.fetchone()
    if not file_data:
        conn.close()
        flash('File not found.')
        return redirect(url_for('edit_course', course_id=course_id))
    filename = file_data[0]
    c.execute('DELETE FROM course_files WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            flash('File deleted from database, but could not remove from disk.')
    flash('File deleted successfully!')
    return redirect(url_for('edit_course', course_id=course_id))

@app.route('/course/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    if current_user.role != 'creator':
        flash('Only creators can delete courses.')
        return redirect(url_for('home'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, reference_file_path FROM courses WHERE id = ?', (course_id,))
    course = c.fetchone()
    if not course:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    if course[1]:
        try:
            os.remove(course[1])
        except OSError:
            pass
    c.execute('DELETE FROM course_files WHERE course_id = ?', (course_id,))
    c.execute('DELETE FROM enrollments WHERE course_id = ?', (course_id,))
    c.execute('DELETE FROM threads WHERE course_id = ?', (course_id,))
    c.execute('DELETE FROM posts WHERE thread_id IN (SELECT id FROM threads WHERE course_id = ?)', (course_id,))
    c.execute('DELETE FROM progress WHERE course_id = ?', (course_id,))
    c.execute('DELETE FROM notes WHERE course_id = ?', (course_id,))
    c.execute('DELETE FROM assignments WHERE course_id = ?', (course_id,))
    c.execute('DELETE FROM assignment_keywords WHERE assignment_id IN (SELECT id FROM assignments WHERE course_id = ?)', (course_id,))
    c.execute('DELETE FROM resources_external WHERE course_id = ?', (course_id,))
    c.execute('DELETE FROM lti_tools WHERE course_id = ?', (course_id,))
    c.execute('DELETE FROM webhooks WHERE course_id = ?', (course_id,))
    c.execute('DELETE FROM courses WHERE id = ?', (course_id,))
    conn.commit()
    conn.close()
    flash('Course deleted successfully!')
    return redirect(url_for('home'))

@app.route('/course/<int:course_id>/thread/<int:thread_id>/delete', methods=['POST'])
@login_required
def delete_thread(course_id, thread_id):
    # Allow any user with role 'creator' or admin (username 'creator1')
    if current_user.role != 'creator' and current_user.username != 'creator1':
        flash('Only creators or admin can delete threads.')
        return redirect(url_for('home'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id FROM courses WHERE id = ?', (course_id,))
    course = c.fetchone()
    if not course:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    c.execute('SELECT id FROM threads WHERE id = ? AND course_id = ?', (thread_id, course_id))
    thread = c.fetchone()
    if not thread:
        conn.close()
        flash('Thread not found.')
        return redirect(url_for('forum', course_id=course_id))
    c.execute('DELETE FROM posts WHERE thread_id = ?', (thread_id,))
    c.execute('DELETE FROM threads WHERE id = ?', (thread_id,))
    conn.commit()
    conn.close()
    flash('Thread deleted successfully!' if current_user.username != 'creator1' else 'Thread deleted by admin!')
    return redirect(url_for('forum', course_id=course_id))

@app.route('/course/<int:course_id>/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(course_id, post_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Check if user is enrolled in the course
    c.execute('SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
    enrollment = c.fetchone()
    
    if not enrollment:
        flash('You must be enrolled in this course to delete posts.', 'danger')
        return redirect(url_for('forum', course_id=course_id))
    
    # Get the post
    c.execute('SELECT user_id, content FROM posts WHERE id = ? AND thread_id IN (SELECT id FROM threads WHERE course_id = ?)', (post_id, course_id))
    post = c.fetchone()
    
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('forum', course_id=course_id))
    
    post_user_id, post_content = post
    
    # Only allow the post creator or course creator to delete
    c.execute('SELECT creator_id FROM courses WHERE id = ?', (course_id,))
    course_creator = c.fetchone()[0]
    
    if current_user.id != post_user_id and current_user.id != course_creator and current_user.username != 'creator1':
        flash('You can only delete your own posts.', 'danger')
        return redirect(url_for('forum', course_id=course_id))
    
    # Delete the post
    c.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    
    flash('Post deleted successfully.', 'success')
    return redirect(url_for('forum', course_id=course_id))

@app.route('/course/<int:course_id>/thread/<int:thread_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_thread(course_id, thread_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Check if user is enrolled in the course
    c.execute('SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
    enrollment = c.fetchone()
    
    if not enrollment:
        flash('You must be enrolled in this course to edit threads.', 'danger')
        return redirect(url_for('forum', course_id=course_id))
    
    # Get the thread
    c.execute('SELECT title, content, creator_id FROM threads WHERE id = ? AND course_id = ?', (thread_id, course_id))
    thread = c.fetchone()
    
    if not thread:
        flash('Thread not found.', 'danger')
        return redirect(url_for('forum', course_id=course_id))
    
    title, content, creator_id = thread
    
    # Only allow the thread creator or course creator to edit
    c.execute('SELECT creator_id FROM courses WHERE id = ?', (course_id,))
    course_creator = c.fetchone()[0]
    
    if current_user.id != creator_id and current_user.id != course_creator and current_user.username != 'creator1':
        flash('You can only edit your own threads.', 'danger')
        return redirect(url_for('forum', course_id=course_id))
    
    if request.method == 'POST':
        new_title = request.form.get('title', '').strip()
        new_content = request.form.get('content', '').strip()
        
        if not new_title or not new_content:
            flash('Title and content are required.', 'danger')
            return render_template('edit_thread.html', course_id=course_id, thread_id=thread_id, title=title, content=content)
        
        # Update the thread
        c.execute('UPDATE threads SET title = ?, content = ? WHERE id = ?', (new_title, new_content, thread_id))
        conn.commit()
        conn.close()
        
        flash('Thread updated successfully.', 'success')
        return redirect(url_for('forum', course_id=course_id))
    
    conn.close()
    return render_template('edit_thread.html', course_id=course_id, thread_id=thread_id, title=title, content=content)

@app.route('/course/<int:course_id>/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(course_id, post_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Check if user is enrolled in the course
    c.execute('SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
    enrollment = c.fetchone()
    
    if not enrollment:
        flash('You must be enrolled in this course to edit posts.', 'danger')
        return redirect(url_for('forum', course_id=course_id))
    
    # Get the post
    c.execute('SELECT content, user_id FROM posts WHERE id = ? AND thread_id IN (SELECT id FROM threads WHERE course_id = ?)', (post_id, course_id))
    post = c.fetchone()
    
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('forum', course_id=course_id))
    
    content, user_id = post
    
    # Only allow the post creator or course creator to edit
    c.execute('SELECT creator_id FROM courses WHERE id = ?', (course_id,))
    course_creator = c.fetchone()[0]
    
    if current_user.id != user_id and current_user.id != course_creator and current_user.username != 'creator1':
        flash('You can only edit your own posts.', 'danger')
        return redirect(url_for('forum', course_id=course_id))
    
    if request.method == 'POST':
        new_content = request.form.get('content', '').strip()
        
        if not new_content:
            flash('Content is required.', 'danger')
            return render_template('edit_post.html', course_id=course_id, post_id=post_id, content=content)
        
        # Update the post
        c.execute('UPDATE posts SET content = ? WHERE id = ?', (new_content, post_id))
        conn.commit()
        conn.close()
        
        flash('Post updated successfully.', 'success')
        return redirect(url_for('forum', course_id=course_id))
    
    conn.close()
    return render_template('edit_post.html', course_id=course_id, post_id=post_id, content=content)

@app.route('/course/<int:course_id>/forum', methods=['GET', 'POST'])
@login_required
def forum(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("PRAGMA table_info(threads)")
    columns = [col[1] for col in c.fetchall()]
    if 'ext_url' not in columns:
        c.execute('ALTER TABLE threads ADD COLUMN ext_url TEXT')
        c.execute('ALTER TABLE threads ADD COLUMN ext_type TEXT')
        conn.commit()
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        thread_id = request.form.get('thread_id')
        ext_url = request.form.get('ext_url')
        ext_type = None
        
        if ext_url:
            if 'youtube.com' in ext_url or 'youtu.be' in ext_url:
                ext_type = 'youtube'
            elif 'docs.google.com' in ext_url:
                ext_type = 'gdoc'
            elif ext_url.lower().endswith('.pdf'):
                ext_type = 'pdf'
            else:
                ext_type = 'link'
        
        # If thread_id is provided, add a post to existing thread
        if thread_id:
            # Verify thread exists and user is enrolled
            c.execute('SELECT id FROM threads WHERE id = ? AND course_id = ?', (thread_id, course_id))
            thread = c.fetchone()
            if not thread:
                conn.close()
                flash('Thread not found.')
                return redirect(url_for('forum', course_id=course_id))
            
            # Get user's enrollment number
            c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
            enrollment = c.fetchone()
            if not enrollment:
                conn.close()
                flash('You must be enrolled to post in this forum.')
                return redirect(url_for('forum', course_id=course_id))
            
            # Add post to thread
            c.execute('INSERT INTO posts (thread_id, user_id, enrollment_number, content, ext_url, ext_type) VALUES (?, ?, ?, ?, ?, ?)', 
                     (thread_id, current_user.id, enrollment[0], content, ext_url, ext_type))
            conn.commit()
            conn.close()
            flash('Reply posted successfully!')
            return redirect(url_for('forum', course_id=course_id))
        
        # Otherwise, create a new thread
        elif title and content:
            # Get user's enrollment number
            c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
            enrollment = c.fetchone()
            if not enrollment:
                conn.close()
                flash('You must be enrolled to create threads.')
                return redirect(url_for('forum', course_id=course_id))
            
            # Create new thread
            c.execute('INSERT INTO threads (course_id, user_id, title, content, ext_url, ext_type) VALUES (?, ?, ?, ?, ?, ?)', 
                     (course_id, current_user.id, title, content, ext_url, ext_type))
            thread_id = c.lastrowid
            
            # Add the initial post to the thread
            c.execute('INSERT INTO posts (thread_id, user_id, enrollment_number, content, ext_url, ext_type) VALUES (?, ?, ?, ?, ?, ?)', 
                     (thread_id, current_user.id, enrollment[0], content, ext_url, ext_type))
            conn.commit()
            conn.close()
            flash('Thread created successfully!')
            return redirect(url_for('forum', course_id=course_id))
        else:
            conn.close()
            flash('Title and content are required for new threads.')
            return redirect(url_for('forum', course_id=course_id))
    
    # GET: show threads with their content and posts
    c.execute('SELECT id, title, content, created_at, ext_url, ext_type, user_id FROM threads WHERE course_id = ? ORDER BY created_at DESC', (course_id,))
    threads = c.fetchall()
    threads_with_posts = []
    
    for thread in threads:
        # Get the thread creator's info
        c.execute('SELECT username, avatar, display_name FROM users WHERE id = ?', (thread[6],))
        creator_info = c.fetchone()
        creator_username = creator_info[0] if creator_info else 'Unknown'
        creator_avatar = creator_info[1] if creator_info else ''
        creator_display_name = creator_info[2] if creator_info else creator_username
        
        # Get all posts for this thread
        c.execute('''SELECT p.id, p.enrollment_number, p.content, p.created_at, u.avatar, p.ext_url, p.ext_type, u.username, u.display_name
                     FROM posts p JOIN users u ON p.user_id = u.id
                     WHERE p.thread_id = ? ORDER BY p.created_at ASC''', (thread[0],))
        posts = c.fetchall()
        
        threads_with_posts.append({
            'thread': {
                'id': thread[0],
                'title': thread[1],
                'content': thread[2],
                'created_at': thread[3],
                'ext_url': thread[4],
                'ext_type': thread[5],
                'creator_username': creator_username,
                'creator_avatar': creator_avatar,
                'creator_display_name': creator_display_name
            },
            'posts': [
                {
                    'id': post[0],
                    'enrollment_number': post[1],
                    'content': post[2],
                    'created_at': post[3],
                    'avatar': post[4],
                    'ext_url': post[5],
                    'ext_type': post[6],
                    'username': post[7],
                    'display_name': post[8]
                } for post in posts
            ]
        })
    
    c.execute('SELECT title, creator_id FROM courses WHERE id = ?', (course_id,))
    course_data = c.fetchone()
    if not course_data:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    
    course_title = course_data[0]
    is_creator = current_user.is_authenticated and current_user.role == 'creator' and course_data[1] == current_user.id
    
    # Notifications for nav
    c.execute('SELECT id, message, link, is_read, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC', (current_user.id,))
    notifications = c.fetchall()
    c.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0', (current_user.id,))
    unread_notifications_count = c.fetchone()[0]
    conn.close()
    
    return render_template('forum.html', course_id=course_id, course_title=course_title, threads=threads_with_posts, is_creator=is_creator, notifications=notifications, unread_notifications_count=unread_notifications_count, user_role=current_user.role, username=current_user.username)

@app.route('/api/course/<int:course_id>/forum_data')
@login_required
def api_forum_data(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, title, content, created_at, ext_url, ext_type, user_id FROM threads WHERE course_id = ? ORDER BY created_at DESC', (course_id,))
    threads = c.fetchall()
    threads_with_posts = []
    
    for thread in threads:
        # Get the thread creator's info
        c.execute('SELECT username, avatar, display_name FROM users WHERE id = ?', (thread[6],))
        creator_info = c.fetchone()
        creator_username = creator_info[0] if creator_info else 'Unknown'
        creator_avatar = creator_info[1] if creator_info else ''
        creator_display_name = creator_info[2] if creator_info else creator_username
        
        # Get all posts for this thread
        c.execute('''SELECT p.id, p.enrollment_number, p.content, p.created_at, u.avatar, p.ext_url, p.ext_type, u.username, u.display_name, p.user_id
                     FROM posts p JOIN users u ON p.user_id = u.id
                     WHERE p.thread_id = ? ORDER BY p.created_at ASC''', (thread[0],))
        posts = c.fetchall()
        
        threads_with_posts.append({
            'thread': {
                'id': thread[0],
                'title': thread[1],
                'content': thread[2],
                'created_at': thread[3],
                'ext_url': thread[4],
                'ext_type': thread[5],
                'creator_id': thread[6],
                'creator_username': creator_username,
                'creator_avatar': creator_avatar,
                'creator_display_name': creator_display_name
            },
            'posts': [
                {
                    'id': post[0],
                    'enrollment_number': post[1],
                    'content': post[2],
                    'created_at': post[3],
                    'avatar': post[4],
                    'ext_url': post[5],
                    'ext_type': post[6],
                    'username': post[7],
                    'display_name': post[8],
                    'user_id': post[9]
                } for post in posts
            ]
        })
    
    conn.close()
    return jsonify({'threads': threads_with_posts})

def allowed_subtitle(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_SUBTITLE_EXTENSIONS']

def extract_youtube_id(url):
    """Extract YouTube video ID from various YouTube URL formats"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*v=([^&\n?#]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_youtube_transcript(video_id):
    """Get transcript for a YouTube video"""
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.fetch(video_id)
        # Combine all transcript parts into one text
        full_transcript = ' '.join([part.text for part in transcript_list])
        return full_transcript
    except Exception as e:
        return None

@app.route('/course/<int:course_id>/resources')
@login_required
def resources(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
    enrollment = c.fetchone()
    if not enrollment:
        conn.close()
        flash('You must be enrolled to access resources.')
        return redirect(url_for('home'))
    c.execute('SELECT title, meeting_link, outline, objectives, live_session_start, live_session_end, live_days FROM courses WHERE id = ?', (course_id,))
    course_data = c.fetchone()
    if not course_data:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    course_title, meeting_link, outline, objectives, live_session_start, live_session_end, live_days = course_data
    
    # Add chapter column to course_files if it doesn't exist
    c.execute("PRAGMA table_info(course_files)")
    columns = [col[1] for col in c.fetchall()]
    if 'chapter' not in columns:
        c.execute('ALTER TABLE course_files ADD COLUMN chapter INTEGER DEFAULT 0')
        conn.commit()
    
    # Get chapter progress for the user
    chapters = outline.split('\n') if outline else []
    c.execute("CREATE TABLE IF NOT EXISTS chapter_progress (user_id INTEGER, course_id INTEGER, chapter_idx INTEGER, completed INTEGER, PRIMARY KEY (user_id, course_id, chapter_idx))")
    chapter_progress = []
    for idx in range(len(chapters)):
        c.execute("SELECT completed FROM chapter_progress WHERE user_id=? AND course_id=? AND chapter_idx=?", (current_user.id, course_id, idx))
        row = c.fetchone()
        chapter_progress.append(bool(row and row[0]))
    
    # Determine which chapters are unlocked for the user
    unlocked_chapters = []
    for idx in range(len(chapters)):
        if idx == 0 or (idx > 0 and chapter_progress[idx-1]):  # First chapter is always unlocked, others require previous completion
            unlocked_chapters.append(idx)
    
    # Get files filtered by unlocked chapters
    if unlocked_chapters:
        placeholders = ','.join(['?' for _ in unlocked_chapters])
        c.execute(f'SELECT id, filename, file_type, subtitle_path, chapter FROM course_files WHERE course_id = ? AND chapter IN ({placeholders})', (course_id,) + tuple(unlocked_chapters))
        files = c.fetchall()
    else:
        files = []
    
    # Add chapter column to assignments if it doesn't exist
    c.execute("PRAGMA table_info(assignments)")
    columns = [col[1] for col in c.fetchall()]
    if 'chapter' not in columns:
        c.execute('ALTER TABLE assignments ADD COLUMN chapter INTEGER DEFAULT 0')
        conn.commit()
    
    # Get assignments filtered by unlocked chapters
    if unlocked_chapters:
        placeholders = ','.join(['?' for _ in unlocked_chapters])
        c.execute(f'SELECT id, name, type, due_date, meeting_link, chapter FROM assignments WHERE course_id = ? AND chapter IN ({placeholders}) ORDER BY due_date ASC', (course_id,) + tuple(unlocked_chapters))
        assignments_data = c.fetchall()
        assignments = [{'id': row[0], 'name': row[1], 'type': row[2], 'due_date': row[3], 'meeting_link': row[4], 'chapter': row[5]} for row in assignments_data]
    else:
        assignments = []
    
    # Check if transcript and chapter columns exist, add if not
    c.execute("PRAGMA table_info(resources_external)")
    columns = [col[1] for col in c.fetchall()]
    if 'transcript' not in columns:
        c.execute('ALTER TABLE resources_external ADD COLUMN transcript TEXT')
    if 'chapter' not in columns:
        c.execute('ALTER TABLE resources_external ADD COLUMN chapter INTEGER DEFAULT 0')
        conn.commit()
    
    # Get external resources filtered by unlocked chapters
    if unlocked_chapters:
        placeholders = ','.join(['?' for _ in unlocked_chapters])
        c.execute(f'SELECT id, title, url, type, transcript, chapter FROM resources_external WHERE course_id=? AND chapter IN ({placeholders}) ORDER BY created_at DESC', (course_id,) + tuple(unlocked_chapters))
        external_resources = c.fetchall()
    else:
        external_resources = []
    
    conn.close()
    return render_template('resources.html', 
                         course_id=course_id, 
                         course_title=course_title, 
                         files=files, 
                         assignments=assignments, 
                         external_resources=external_resources, 
                         meeting_link=meeting_link, 
                         outline=outline, 
                         objectives=objectives, 
                         chapter_progress=chapter_progress,
                         unlocked_chapters=unlocked_chapters,
                         chapters=chapters,
                         live_session_start=live_session_start,
                         live_session_end=live_session_end,
                         live_days=live_days)

@app.route('/download/<int:file_id>')
@login_required
def download(file_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT course_id, filename FROM course_files WHERE id = ?', (file_id,))
    file_data = c.fetchone()
    if not file_data:
        conn.close()
        flash('File not found.')
        return redirect(url_for('home'))
    course_id, filename = file_data
    c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?',
              (current_user.id, course_id))
    if not c.fetchone():
        conn.close()
        flash('You must be enrolled to download this file.')
        return redirect(url_for('home'))
    conn.close()
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    flash('File not available.')
    return redirect(url_for('home'))

@app.route('/course/<int:course_id>/enroll', methods=['GET', 'POST'])
@login_required
def enroll(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT title FROM courses WHERE id = ?', (course_id,))
    course_data = c.fetchone()
    if not course_data:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    course_title = course_data[0]
    c.execute('SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
    if c.fetchone():
        conn.close()
        flash('You are already enrolled in this course.')
        return redirect(url_for('home'))
    if request.method == 'POST':
        enrollment_number = generate_enrollment_number()
        c.execute('INSERT INTO enrollments (user_id, course_id, enrollment_number) VALUES (?, ?, ?)',
                  (current_user.id, course_id, enrollment_number))
        conn.commit()
        conn.close()
        flash('Successfully enrolled in the course!')
        return redirect(url_for('home'))
    conn.close()
    return render_template('enroll.html', course_id=course_id, course_title=course_title)

@app.route('/course/<int:course_id>/students')
@login_required
def students(course_id):
    if current_user.role != 'creator':
        flash('Only creators can view enrolled students.')
        return redirect(url_for('home'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT title, creator_id FROM courses WHERE id = ?', (course_id,))
    course_data = c.fetchone()
    if not course_data:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    course_title = course_data[0]
    c.execute('SELECT u.id, u.username, u.avatar, u.display_name, u.bio, e.enrollment_number FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.course_id = ?', (course_id,))
    students = c.fetchall()
    student_data = []
    grade_data = {'labels': [], 'values': []}
    completion_distribution = {'0-25': 0, '25-50': 0, '50-75': 0, '75-100': 0}
    for student in students:
        user_id, username, avatar, display_name, bio, enrollment_number = student
        c.execute('SELECT grade, status FROM progress WHERE user_id = ? AND course_id = ?', (user_id, course_id))
        progress = c.fetchall()
        total_grades = [p[0] for p in progress if p[0] is not None]
        avg_grade = sum(total_grades) / len(total_grades) if total_grades else 0
        completed = len([p for p in progress if p[1] == 'completed'])
        total_assignments = len(progress)
        completion_rate = (completed / total_assignments * 100) if total_assignments > 0 else 0
        student_data.append((username, enrollment_number, round(avg_grade, 2), round(completion_rate, 2), avatar, display_name, bio))
        grade_data['labels'].append(username)
        grade_data['values'].append(round(avg_grade, 2))
        if completion_rate <= 25:
            completion_distribution['0-25'] += 1
        elif completion_rate <= 50:
            completion_distribution['25-50'] += 1
        elif completion_rate <= 75:
            completion_distribution['50-75'] += 1
        else:
            completion_distribution['75-100'] += 1
    completion_data = {
        'labels': list(completion_distribution.keys()),
        'values': list(completion_distribution.values())
    }
    conn.close()
    return render_template('students.html', course_id=course_id, course_title=course_title, students=student_data, grade_data=grade_data, completion_data=completion_data)

@app.route('/course/<int:course_id>/students/export', methods=['GET'])
@login_required
def export_students(course_id):
    if current_user.role != 'creator':
        flash('Only creators can export student data.')
        return redirect(url_for('home'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT title FROM courses WHERE id = ?', (course_id,))
    course_data = c.fetchone()
    if not course_data:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    course_title = course_data[0]
    c.execute('SELECT u.id, u.username, e.enrollment_number FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.course_id = ?', (course_id,))
    students = c.fetchall()
    student_data = []
    for student in students:
        user_id, username, enrollment_number = student
        c.execute('SELECT grade, status FROM progress WHERE user_id = ? AND course_id = ?', (user_id, course_id))
        progress = c.fetchall()
        total_grades = [p[0] for p in progress if p[0] is not None]
        avg_grade = sum(total_grades) / len(total_grades) if total_grades else 0
        completed = len([p for p in progress if p[1] == 'completed'])
        total_assignments = len(progress)
        completion_rate = (completed / total_assignments * 100) if total_assignments > 0 else 0
        student_data.append((username, enrollment_number, round(avg_grade, 2), round(completion_rate, 2)))
    conn.close()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Username', 'Enrollment Number', 'Average Grade', 'Completion Rate (%)'])
    writer.writerows(student_data)
    output = si.getvalue().encode('utf-8')
    si.close()
    return send_file(
        BytesIO(output),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{course_title}_students.csv'
    )

@app.route('/course/<int:course_id>/progress')
@login_required
def progress(course_id):
    conn = None
    try:
        # Use WAL mode for better concurrency
        conn = sqlite3.connect('database.db', timeout=15.0)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA cache_size=10000')
        conn.execute('PRAGMA temp_store=MEMORY')
        
        c = conn.cursor()
        
        c.execute('SELECT title, creator_id, reference_file_path FROM courses WHERE id = ?', (course_id,))
        course_data = c.fetchone()
        if not course_data:
            flash('Course not found.')
            return redirect(url_for('home'))
        
        course_title = course_data[0]
        creator_id = course_data[1]
        reference_file = os.path.basename(course_data[2]) if course_data[2] else None
        
        c.execute('SELECT avatar, display_name FROM users WHERE id = ?', (creator_id,))
        creator_info = c.fetchone()
        creator_avatar = creator_info[0] if creator_info and creator_info[0] else DEFAULT_AVATAR
        creator_display_name = creator_info[1] if creator_info and creator_info[1] else 'Course Creator'
        
        c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?',
                  (current_user.id, course_id))
        enrollment = c.fetchone()
        if not enrollment and current_user.role != 'creator':
            flash('You must be enrolled or be the creator to view progress.')
            return redirect(url_for('home'))
        
        if current_user.role == 'creator':
            c.execute('''SELECT p.id, u.username, p.assignment_name, p.status, p.grade, p.file_path, p.ai_grade, u.avatar, u.display_name
                         FROM progress p JOIN users u ON p.user_id = u.id
                         WHERE p.course_id = ?''', (course_id,))
            progress_data = c.fetchall()
        else:
            c.execute('''SELECT p.id, u.username, p.assignment_name, p.status, p.grade, p.file_path, p.ai_grade, u.avatar, u.display_name
                         FROM progress p JOIN users u ON p.user_id = u.id
                         WHERE p.course_id = ? AND p.user_id = ?''', (course_id, current_user.id))
            progress_data = c.fetchall()
        
        is_creator = current_user.role == 'creator' and creator_id == current_user.id
        
        # Fetch assignments for this course, with due_date and sort
        c.execute('SELECT id, name, type, due_date FROM assignments WHERE course_id = ? ORDER BY due_date ASC', (course_id,))
        assignments = [{'id': row[0], 'name': row[1], 'type': row[2], 'due_date': row[3]} for row in c.fetchall()]
        
        # Fetch student progress for assignment status
        assignment_status = {}
        if not is_creator:
            for a in assignments:
                c.execute('SELECT status FROM progress WHERE user_id = ? AND course_id = ? AND assignment_name = ?', (current_user.id, course_id, a['name']))
                row = c.fetchone()
                assignment_status[a['id']] = row[0] if row else 'Not Submitted'
        
        # For each assignment, get latest AI feedback for this user
        for a in assignments:
            c.execute('SELECT ai_grade FROM progress WHERE user_id=? AND course_id=? AND assignment_name=? ORDER BY id DESC LIMIT 1', (current_user.id, course_id, a['name']))
            row = c.fetchone()
            a['ai_feedback'] = row[0] if row and row[0] else None
        
        return render_template('progress.html', course_id=course_id, course_title=course_title, progress_data=progress_data, is_creator=is_creator, is_enrolled=bool(enrollment), reference_file=reference_file, assignments=assignments, assignment_status=assignment_status, creator_avatar=creator_avatar, creator_display_name=creator_display_name)
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            flash('Database is temporarily busy. Please refresh the page in a moment.')
        else:
            flash('Database error occurred. Please try again.')
        return redirect(url_for('home'))
    except Exception as e:
        flash('An error occurred while loading progress. Please try again.')
        return redirect(url_for('home'))
    finally:
        if conn:
            conn.close()

@app.route('/course/<int:course_id>/progress/submit', methods=['POST'])
@login_required
def submit_assignment(course_id):
    if current_user.role == 'creator':
        flash('Creators cannot submit assignments.')
        return redirect(url_for('progress', course_id=course_id))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, reference_file_path FROM courses WHERE id = ?', (course_id,))
    course = c.fetchone()
    if not course:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
    enrollment = c.fetchone()
    if not enrollment:
        conn.close()
        flash('You must be enrolled to submit assignments.')
        return redirect(url_for('home'))
    if not course[1]:
        conn.close()
        flash('Cannot submit assignment: No reference file uploaded for AI grading.')
        return redirect(url_for('progress', course_id=course_id))
    assignment_name = request.form.get('assignment_name')
    file = request.files.get('file')
    if not assignment_name:
        conn.close()
        flash('Assignment name is required.')
        return redirect(url_for('progress', course_id=course_id))
    c.execute('SELECT id FROM progress WHERE user_id = ? AND course_id = ? AND assignment_name = ?',
              (current_user.id, course_id, assignment_name))
    if c.fetchone():
        conn.close()
        flash('Assignment already submitted.')
        return redirect(url_for('progress', course_id=course_id))
    file_path = None
    ai_grade = None
    if file and file.filename:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.pdf', '.txt', '.py']:
            conn.close()
            flash('Invalid file type. Only PDF, TXT, and PY files are allowed.')
            return redirect(url_for('progress', course_id=course_id))
        if file.content_length > 5 * 1024 * 1024:  # 5MB limit
            conn.close()
            flash('File size exceeds 5MB limit.')
            return redirect(url_for('progress', course_id=course_id))
        filename = f"{current_user.id}_{course_id}_{assignment_name.replace(' ', '_')}{file_ext}"
        file_path = os.path.join(app.config['ASSIGNMENT_UPLOAD_FOLDER'], filename)
        file.save(file_path)
        if file_ext == '.py':
            ai_grade = ai_grade_code(file_path, course_id)
    c.execute('INSERT INTO progress (user_id, course_id, assignment_name, status, grade, file_path, ai_grade) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (current_user.id, course_id, assignment_name, 'submitted', None, file_path, ai_grade))
    conn.commit()
    conn.close()
    flash('Assignment submitted successfully!')
    return redirect(url_for('progress', course_id=course_id))

@app.route('/course/<int:course_id>/progress/<int:progress_id>/download', methods=['GET'])
@login_required
def download_assignment(course_id, progress_id):
    if current_user.role != 'creator':
        flash('Only creators can download assignments.')
        return redirect(url_for('home'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, creator_id FROM courses WHERE id = ?', (course_id,))
    course = c.fetchone()
    if not course:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    if course[1] != current_user.id:
        conn.close()
        flash('You are not the creator of this course.')
        return redirect(url_for('progress', course_id=course_id))
    c.execute('SELECT file_path FROM progress WHERE id = ? AND course_id = ?', (progress_id, course_id))
    progress = c.fetchone()
    if not progress or not progress[0]:
        conn.close()
        flash('No file available for this assignment.')
        return redirect(url_for('progress', course_id=course_id))
    file_path = progress[0]
    conn.close()
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    flash('File not available.')
    return redirect(url_for('progress', course_id=course_id))

@app.route('/course/<int:course_id>/progress/<int:progress_id>/edit', methods=['POST'])
@login_required
def edit_progress(course_id, progress_id):
    if current_user.role != 'creator':
        flash('Only creators can edit progress.')
        return redirect(url_for('home'))
    
    # Use a simple retry mechanism for database operations
    import time
    import sqlite3
    
    max_retries = 3
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        conn = None
        try:
            # Connect with immediate mode to avoid locks
            conn = sqlite3.connect('database.db', timeout=30.0, isolation_level=None)
            conn.execute('PRAGMA journal_mode=WAL')  # Use WAL mode for better concurrency
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=10000')
            conn.execute('PRAGMA temp_store=MEMORY')
            
            c = conn.cursor()
            
            # Get course information
            c.execute('SELECT id, creator_id FROM courses WHERE id = ?', (course_id,))
            course = c.fetchone()
            if not course:
                flash('Course not found.')
                return redirect(url_for('home'))
            if course[1] != current_user.id:
                flash('You are not the creator of this course.')
                return redirect(url_for('progress', course_id=course_id))
            
            # Check if progress record exists
            c.execute('SELECT id FROM progress WHERE id = ? AND course_id = ?', (progress_id, course_id))
            progress = c.fetchone()
            if not progress:
                flash('Progress record not found.')
                return redirect(url_for('progress', course_id=course_id))
            
            # Validate form data
            status = request.form.get('status')
            grade = request.form.get('grade')
            if status not in ['submitted', 'completed', 'incomplete']:
                flash('Invalid status.')
                return redirect(url_for('progress', course_id=course_id))
            
            if grade:
                try:
                    grade = int(grade)
                    if not 0 <= grade <= 100:
                        flash('Grade must be between 0 and 100.')
                        return redirect(url_for('progress', course_id=course_id))
                except ValueError:
                    flash('Grade must be a number.')
                    return redirect(url_for('progress', course_id=course_id))
            else:
                grade = None
            
            # Start transaction
            conn.execute('BEGIN IMMEDIATE')
            
            # Update progress
            c.execute('UPDATE progress SET status = ?, grade = ? WHERE id = ?', (status, grade, progress_id))
            
            # Get student information for notification
            c.execute('SELECT user_id FROM progress WHERE id = ?', (progress_id,))
            student_row = c.fetchone()
            if not student_row:
                conn.rollback()
                flash('Student not found for this progress record.')
                return redirect(url_for('progress', course_id=course_id))
            
            student_id = student_row[0]
            c.execute('SELECT title FROM courses WHERE id = ?', (course_id,))
            course_title_row = c.fetchone()
            course_title = course_title_row[0] if course_title_row else 'Unknown Course'
            
            # Commit transaction
            conn.commit()
            
            # Create notification (outside transaction to avoid locks)
            try:
                create_notification(student_id, f'Your assignment grade was updated in {course_title}', url_for('progress', course_id=course_id), 'grades')
            except:
                pass  # Don't fail if notification creation fails
            
            flash('Progress updated successfully!')
            return redirect(url_for('progress', course_id=course_id))
            
        except sqlite3.OperationalError as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            conn.close()
            
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                flash('Database is temporarily busy. Please try again in a moment.')
                return redirect(url_for('progress', course_id=course_id))
                
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            conn.close()
            flash('An error occurred while updating progress. Please try again.')
            return redirect(url_for('progress', course_id=course_id))
        finally:
            if conn:
                conn.close()
    
    flash('Database is temporarily busy. Please try again in a moment.')
    return redirect(url_for('progress', course_id=course_id))

@app.route('/course/<int:course_id>/notes', methods=['GET', 'POST'])
@login_required
def notes(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT title, creator_id FROM courses WHERE id = ?', (course_id,))
    course_data = c.fetchone()
    if not course_data:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    course_title = course_data[0]
    creator_id = course_data[1]
    c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?',
              (current_user.id, course_id))
    enrollment = c.fetchone()
    if not enrollment and current_user.role != 'creator':
        conn.close()
        flash('You must be enrolled or be the creator to view notes.')
        return redirect(url_for('home'))
    if request.method == 'POST':
        content = request.form.get('content')
        if not content:
            conn.close()
            flash('Note content is required.')
            return redirect(url_for('notes', course_id=course_id))
        c.execute('INSERT INTO notes (user_id, course_id, content) VALUES (?, ?, ?)',
                  (current_user.id, course_id, content))
        conn.commit()
        flash('Note saved successfully!')
        conn.close()
        return redirect(url_for('notes', course_id=course_id))
    c.execute('SELECT id, content, created_at, updated_at FROM notes WHERE user_id = ? AND course_id = ?',
              (current_user.id, course_id))
    notes = c.fetchall()
    is_enrolled = bool(enrollment)
    # Add unread_notifications_count for template
    c.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0', (current_user.id,))
    unread_notifications_count = c.fetchone()[0]
    conn.close()
    return render_template('notes.html', course_id=course_id, course_title=course_title, notes=notes, is_enrolled=is_enrolled, unread_notifications_count=unread_notifications_count)

@app.route('/course/<int:course_id>/notes/edit', methods=['POST'])
@login_required
def edit_note(course_id):
    if current_user.role == 'creator':
        flash('Creators cannot edit notes.')
        return redirect(url_for('notes', course_id=course_id))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id FROM courses WHERE id = ?', (course_id,))
    if not c.fetchone():
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?',
              (current_user.id, course_id))
    if not c.fetchone():
        conn.close()
        flash('You must be enrolled to edit notes.')
        return redirect(url_for('home'))
    note_id = request.form.get('note_id')
    content = request.form.get('content')
    if not note_id or not content:
        conn.close()
        flash('Note ID and content are required.')
        return redirect(url_for('notes', course_id=course_id))
    c.execute('SELECT user_id FROM notes WHERE id = ? AND course_id = ?', (note_id, course_id))
    note = c.fetchone()
    if not note or note[0] != current_user.id:
        conn.close()
        flash('Note not found or you do not have permission to edit it.')
        return redirect(url_for('notes', course_id=course_id))
    c.execute('UPDATE notes SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (content, note_id))
    conn.commit()
    conn.close()
    flash('Note updated successfully!')
    return redirect(url_for('notes', course_id=course_id))

@app.route('/course/<int:course_id>/notes/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(course_id, note_id):
    if current_user.role == 'creator':
        flash('Creators cannot delete notes.')
        return redirect(url_for('notes', course_id=course_id))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id FROM courses WHERE id = ?', (course_id,))
    if not c.fetchone():
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?',
              (current_user.id, course_id))
    if not c.fetchone():
        conn.close()
        flash('You must be enrolled to delete notes.')
        return redirect(url_for('home'))
    c.execute('SELECT user_id FROM notes WHERE id = ? AND course_id = ?', (note_id, course_id))
    note = c.fetchone()
    if not note or note[0] != current_user.id:
        conn.close()
        flash('Note not found or you do not have permission to delete it.')
        return redirect(url_for('notes', course_id=course_id))
    c.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()
    flash('Note deleted successfully!')
    return redirect(url_for('notes', course_id=course_id))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.')
    return redirect(url_for('login'))

@app.route('/api/courses')
@login_required
def api_courses():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, title, description, creator_id FROM courses')
    courses = [
        {'id': row[0], 'title': row[1], 'description': row[2], 'creator_id': row[3]}
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify({'courses': courses})

@app.route('/api/course/<int:course_id>/enrollments')
@login_required
def api_course_enrollments(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT user_id, enrollment_number FROM enrollments WHERE course_id = ?', (course_id,))
    enrollments = [
        {'user_id': row[0], 'enrollment_number': row[1]}
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify({'enrollments': enrollments})

@app.route('/api/course/<int:course_id>/progress')
@login_required
def api_course_progress(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT p.id, p.user_id, u.username, p.assignment_name, p.status, p.grade, p.ai_grade
                 FROM progress p JOIN users u ON p.user_id = u.id
                 WHERE p.course_id = ?''', (course_id,))
    progress = [
        {
            'id': row[0],
            'user_id': row[1],
            'username': row[2],
            'assignment_name': row[3],
            'status': row[4],
            'grade': row[5],
            'ai_grade': row[6]
        }
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify({'progress': progress})

@app.route('/course/<int:course_id>/live_chat')
@login_required
def live_chat(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT title FROM courses WHERE id = ?', (course_id,))
    course = c.fetchone()
    c.execute('SELECT avatar FROM users WHERE id = ?', (current_user.id,))
    row = c.fetchone()
    avatar = row[0] if row else None
    conn.close()
    if not course:
        flash('Course not found.')
        return redirect(url_for('home'))
    avatar_url = avatar if avatar else DEFAULT_AVATAR
    return render_template('live_chat.html', course_id=course_id, course_title=course[0], username=current_user.username, avatar_url=avatar_url)

@socketio.on('join')
def handle_join(data):
    room = f"course_{data['course_id']}"
    join_room(room)
    emit('chat_history', chat_messages.get(room, []), room=request.sid)
    send({'msg': f"{data['username']} has joined the chat.", 'avatar_url': data.get('avatar_url', DEFAULT_AVATAR)}, room=room)
    # Emit a system message for user join
    socketio.emit('system_message', f"{data['username']} joined the chat.", room=room)

@socketio.on('send_message')
def handle_send_message(data):
    room = f"course_{data['course_id']}"
    msg = {'username': data['username'], 'msg': data['msg'], 'avatar_url': data.get('avatar_url', DEFAULT_AVATAR)}
    chat_messages.setdefault(room, []).append(msg)
    emit('receive_message', msg, room=room)

# Helper: grade MCQ answers
def grade_mcq(student_answers, correct_answers):
    correct = 0
    for s, c in zip(student_answers, correct_answers):
        if s.strip().lower() == c.strip().lower():
            correct += 1
    return int((correct / len(correct_answers)) * 100) if correct_answers else 0

# Helper: grade text answers with keywords
def grade_keywords(student_text, keywords):
    tokens = set(word_tokenize(student_text.lower()))
    found = sum(1 for kw in keywords if kw.lower() in tokens)
    return int((found / len(keywords)) * 100) if keywords else 0

@app.route('/course/<int:course_id>/create_assignment', methods=['GET', 'POST'])
@login_required
def create_assignment(course_id):
    if current_user.role != 'creator':
        flash('Only creators can create assignments.')
        return redirect(url_for('home'))
    if request.method == 'POST':
        name = request.form['name']
        type_ = request.form['type']
        if type_ == 'mcq':
            # Collect MCQ questions/options/correct answers as JSON
            questions = []
            idx = 0
            while True:
                q = request.form.get(f'question_{idx}')
                if not q:
                    break
                opts = [request.form.get(f'option_{idx}_{j}') for j in range(4)]
                correct = request.form.get(f'correct_{idx}')
                questions.append({'question': q, 'options': opts, 'correct': correct})
                idx += 1
            questions_json = json.dumps(questions)
            correct_answers = ''  # Not used for MCQ
        else:
            questions_json = request.form['questions']
            correct_answers = request.form.get('correct_answers', '')
        due_date = request.form.get('due_date')
        meeting_link = request.form.get('meeting_link')
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("PRAGMA table_info(assignments)")
        columns = [col[1] for col in c.fetchall()]
        if 'meeting_link' not in columns:
            c.execute('ALTER TABLE assignments ADD COLUMN meeting_link TEXT')
        if 'chapter' not in columns:
            c.execute('ALTER TABLE assignments ADD COLUMN chapter INTEGER DEFAULT 0')
            conn.commit()
        
        chapter = int(request.form.get('chapter', 0))  # Default to chapter 0
        c.execute('INSERT INTO assignments (course_id, name, type, questions, correct_answers, due_date, meeting_link, chapter) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                  (course_id, name, type_, questions_json, correct_answers, due_date, meeting_link, chapter))
        assignment_id = c.lastrowid
        if type_ == 'text':
            keywords = request.form.get('keywords', '').split(',')
            for kw in keywords:
                if kw.strip():
                    c.execute('INSERT INTO assignment_keywords (assignment_id, keyword) VALUES (?, ?)', (assignment_id, kw.strip()))
        conn.commit()
        conn.close()
        flash('Assignment created!')
        return redirect(url_for('progress', course_id=course_id))
    return render_template('create_assignment.html', course_id=course_id)

def add_points(user_id, amount):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE users SET points = COALESCE(points,0) + ? WHERE id=?', (amount, user_id))
    conn.commit()
    conn.close()

BADGE_DESCRIPTIONS = {
    'First Submission': 'Submitted your first assignment!',
    'High Grade': 'Scored above 90% on an assignment.',
    'Perfect Score': 'Scored 100% on an assignment.',
    'Forum Contributor': 'Posted in the forum.',
    'Course Completion': 'Completed all assignments in a course.',
    'Streak': 'Submitted assignments 3 days in a row.'
}

def award_badge(user_id, badge):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT 1 FROM badges WHERE user_id=? AND badge=?', (user_id, badge))
    if not c.fetchone():
        c.execute('INSERT INTO badges (user_id, badge) VALUES (?, ?)', (user_id, badge))
        # Notify user
        c.execute('INSERT INTO notifications (user_id, message, link) VALUES (?, ?, ?)', (user_id, f'You earned a badge: {badge}!', None))
        conn.commit()
    conn.close()

def get_user_badges(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT badge FROM badges WHERE user_id=?', (user_id,))
    badges = [row[0] for row in c.fetchall()]
    conn.close()
    return badges

def get_leaderboard(course_id=None, limit=10):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if course_id:
        c.execute('''SELECT u.username, u.points, u.avatar FROM users u JOIN enrollments e ON u.id=e.user_id WHERE e.course_id=? ORDER BY u.points DESC LIMIT ?''', (course_id, limit))
    else:
        c.execute('SELECT username, points, avatar FROM users ORDER BY points DESC LIMIT ?', (limit,))
    leaderboard = c.fetchall()
    conn.close()
    return leaderboard

# Award badges/points on assignment submission
@app.route('/course/<int:course_id>/submit_assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def submit_assignment_new(course_id, assignment_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT name, type, questions, correct_answers FROM assignments WHERE id = ?', (assignment_id,))
    assignment = c.fetchone()
    if not assignment:
        conn.close()
        flash('Assignment not found.')
        return redirect(url_for('progress', course_id=course_id))
    name, type_, questions, correct_answers = assignment
    import json
    questions_list = []
    if type_ == 'mcq' and questions:
        try:
            questions_list = json.loads(questions)
        except Exception:
            questions_list = []
    if request.method == 'POST':
        if type_ == 'mcq':
            questions_list = json.loads(questions)
            correct_count = 0
            for idx, q in enumerate(questions_list):
                selected = request.form.get(f'answer_{idx}')
                if selected == q['correct']:
                    correct_count += 1
            ai_grade = int((correct_count / len(questions_list)) * 100) if questions_list else 0
            c.execute('INSERT INTO progress (user_id, course_id, assignment_name, status, grade, file_path, ai_grade) VALUES (?, ?, ?, ?, ?, ?, ?)',
                      (current_user.id, course_id, name, 'submitted', None, None, ai_grade))
        elif type_ == 'text':
            student_text = request.form.get('answer_text', '')
            c.execute('SELECT keyword FROM assignment_keywords WHERE assignment_id = ?', (assignment_id,))
            keywords = [row[0] for row in c.fetchall()]
            ai_grade = grade_keywords(student_text, keywords)
            c.execute('INSERT INTO progress (user_id, course_id, assignment_name, status, grade, file_path, ai_grade) VALUES (?, ?, ?, ?, ?, ?, ?)',
                      (current_user.id, course_id, name, 'submitted', None, None, ai_grade))
        conn.commit()
        conn.close()
        flash('Assignment submitted!')
        return redirect(url_for('progress', course_id=course_id))
    conn.close()
    add_points(current_user.id, 10)
    award_badge(current_user.id, 'First Submission')
    return render_template('submit_assignment.html', course_id=course_id, assignment_id=assignment_id, name=name, type=type_, questions_list=questions_list, questions=questions, correct_answers=correct_answers)

@app.route('/course/<int:course_id>/edit_assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def edit_assignment(course_id, assignment_id):
    if current_user.role != 'creator':
        flash('Only creators can edit assignments.')
        return redirect(url_for('progress', course_id=course_id))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT name, type, questions, correct_answers, due_date, meeting_link FROM assignments WHERE id = ?', (assignment_id,))
    assignment = c.fetchone()
    if not assignment:
        conn.close()
        flash('Assignment not found.')
        return redirect(url_for('progress', course_id=course_id))
    if request.method == 'POST':
        name = request.form['name']
        type_ = request.form['type']
        questions = request.form['questions']
        correct_answers = request.form.get('correct_answers', '')
        due_date = request.form.get('due_date')
        meeting_link = request.form.get('meeting_link')
        c.execute('UPDATE assignments SET name=?, type=?, questions=?, correct_answers=?, due_date=?, meeting_link=? WHERE id=?',
                  (name, type_, questions, correct_answers, due_date, meeting_link, assignment_id))
        conn.commit()
        conn.close()
        flash('Assignment updated!')
        return redirect(url_for('progress', course_id=course_id))
    conn.close()
    return render_template('create_assignment.html', course_id=course_id, assignment_id=assignment_id, edit=True, assignment=assignment)

@app.route('/course/<int:course_id>/delete_assignment/<int:assignment_id>')
@login_required
def delete_assignment(course_id, assignment_id):
    if current_user.role != 'creator':
        flash('Only creators can delete assignments.')
        return redirect(url_for('progress', course_id=course_id))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM assignments WHERE id = ?', (assignment_id,))
    c.execute('DELETE FROM assignment_keywords WHERE assignment_id = ?', (assignment_id,))
    conn.commit()
    conn.close()
    flash('Assignment deleted!')
    return redirect(url_for('progress', course_id=course_id))

def api_token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return {'error': 'Missing or invalid API token'}, 401
        token = token.split(' ', 1)[1]
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE api_token = ?', (token,))
        user = c.fetchone()
        conn.close()
        if not user:
            return {'error': 'Invalid API token'}, 401
        return f(*args, **kwargs)
    return decorated

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    username_param = request.args.get('user')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Ensure columns exist
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    for col in ['notif_forum', 'notif_grades', 'notif_announcements', 'dark_mode']:
        if col not in columns:
            default = '0' if col == 'dark_mode' else '1'
            c.execute(f'ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT {default}')
    conn.commit()
    if username_param:
        c.execute('SELECT username, role, avatar, display_name, bio, notif_forum, notif_grades, notif_announcements, dark_mode, logo FROM users WHERE username = ?', (username_param,))
        user = c.fetchone()
        is_self = (username_param == current_user.username)
    else:
        c.execute('SELECT username, role, avatar, display_name, bio, notif_forum, notif_grades, notif_announcements, dark_mode, logo FROM users WHERE id = ?', (current_user.id,))
        user = c.fetchone()
        is_self = True
    avatar_url = user[2] if user and user[2] else DEFAULT_AVATAR
    logo_url = user[9] if user and user[9] else None
    notif_forum = bool(user[5]) if user else True
    notif_grades = bool(user[6]) if user else True
    notif_announcements = bool(user[7]) if user else True
    dark_mode = bool(user[8]) if user else False
    if request.method == 'POST' and is_self:
        file = request.files.get('avatar')
        logo_file = request.files.get('logo')
        new_display_name = request.form.get('display_name', '').strip()
        new_bio = request.form.get('bio', '').strip()
        notif_forum_val = 1 if request.form.get('notif_forum') else 0
        notif_grades_val = 1 if request.form.get('notif_grades') else 0
        notif_announcements_val = 1 if request.form.get('notif_announcements') else 0
        dark_mode_val = 1 if request.form.get('dark_mode') else 0
        
        # Handle avatar upload
        if file and allowed_avatar(file.filename):
            filename = secure_filename(f"avatar_{current_user.id}.{file.filename.rsplit('.', 1)[1].lower()}")
            filepath = os.path.join('static', 'uploads', filename)
            file.save(filepath)
            c.execute('UPDATE users SET avatar = ? WHERE id = ?', (filepath, current_user.id))
            conn.commit()
            flash('Avatar updated!')
        
        # Handle logo upload for creators
        if logo_file and current_user.role == 'creator':
            if logo_file.filename and logo_file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                # Check file size by reading the file content
                logo_file.seek(0, 2)  # Seek to end
                file_size = logo_file.tell()  # Get file size
                logo_file.seek(0)  # Reset to beginning
                
                if file_size <= 2 * 1024 * 1024:  # 2MB limit
                    filename = secure_filename(f"logo_{current_user.id}.{logo_file.filename.rsplit('.', 1)[1].lower()}")
                    filepath = os.path.join('static', 'uploads', filename)
                    logo_file.save(filepath)
                    c.execute('UPDATE users SET logo = ? WHERE id = ?', (filepath, current_user.id))
                    conn.commit()
                    flash('Logo updated!')
                else:
                    flash('Logo file size must be less than 2MB.')
            else:
                flash('Logo must be a PNG, JPG, or JPEG file.')
        
        # Handle logo removal
        if 'remove_logo' in request.form and current_user.role == 'creator':
            c.execute('SELECT logo FROM users WHERE id = ?', (current_user.id,))
            result = c.fetchone()
            if result and result[0]:
                # Delete the logo file
                try:
                    os.remove(result[0])
                except OSError:
                    pass  # File might not exist
                # Remove from database
                c.execute('UPDATE users SET logo = NULL WHERE id = ?', (current_user.id,))
                conn.commit()
                flash('Logo removed successfully!')
        
        if new_display_name:
            c.execute('UPDATE users SET display_name = ? WHERE id = ?', (new_display_name, current_user.id))
            conn.commit()
        if new_bio:
            c.execute('UPDATE users SET bio = ? WHERE id = ?', (new_bio, current_user.id))
            conn.commit()
        c.execute('UPDATE users SET notif_forum = ?, notif_grades = ?, notif_announcements = ?, dark_mode = ? WHERE id = ?',
                  (notif_forum_val, notif_grades_val, notif_announcements_val, dark_mode_val, current_user.id))
        conn.commit()
        c.execute('SELECT username, role, avatar, display_name, bio, notif_forum, notif_grades, notif_announcements, dark_mode, logo FROM users WHERE id = ?', (current_user.id,))
        user = c.fetchone()
        avatar_url = user[2] if user and user[2] else DEFAULT_AVATAR
        logo_url = user[9] if user and user[9] else None
        notif_forum = bool(user[5])
        notif_grades = bool(user[6])
        notif_announcements = bool(user[7])
        dark_mode = bool(user[8])
        if 'generate_token' in request.form:
            new_token = secrets.token_hex(32)
            c.execute('UPDATE users SET api_token = ? WHERE id = ?', (new_token, current_user.id))
            conn.commit()
        if 'revoke_token' in request.form:
            c.execute('UPDATE users SET api_token = NULL WHERE id = ?', (current_user.id,))
            conn.commit()
    c.execute('SELECT api_token FROM users WHERE id = ?', (current_user.id,))
    api_token = c.fetchone()[0]
    conn.close()
    return render_template('profile.html', username=user[0], role=user[1], avatar_url=avatar_url, logo_url=logo_url, display_name=user[3] or '', bio=user[4] or '', is_self=is_self, notif_forum=notif_forum, notif_grades=notif_grades, notif_announcements=notif_announcements, dark_mode=dark_mode, api_token=api_token)

@app.route('/course/<int:course_id>/announce', methods=['GET', 'POST'])
@login_required
def announce(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("PRAGMA table_info(announcements)")
    columns = [col[1] for col in c.fetchall()]
    if 'ext_url' not in columns:
        c.execute('ALTER TABLE announcements ADD COLUMN ext_url TEXT')
        c.execute('ALTER TABLE announcements ADD COLUMN ext_type TEXT')
        conn.commit()
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        ext_url = request.form.get('ext_url')
        ext_type = None
        if ext_url:
            if 'youtube.com' in ext_url or 'youtu.be' in ext_url:
                ext_type = 'youtube'
            elif 'docs.google.com' in ext_url:
                ext_type = 'gdoc'
            elif ext_url.lower().endswith('.pdf'):
                ext_type = 'pdf'
            else:
                ext_type = 'link'
        c.execute('INSERT INTO announcements (course_id, title, message, ext_url, ext_type) VALUES (?, ?, ?, ?, ?)', (course_id, title, message, ext_url, ext_type))
        conn.commit()
        conn.close()
        flash('Announcement posted!')
        return redirect(url_for('forum', course_id=course_id))
    # GET: show form
    return render_template('announce.html', course_id=course_id)

@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if current_user.role == 'creator':
        # Course stats
        c.execute('''SELECT c.id, c.title, COUNT(e.user_id), AVG(p.grade), AVG(CASE WHEN p.status='completed' THEN 1 ELSE 0 END)*100
                     FROM courses c LEFT JOIN enrollments e ON c.id=e.course_id
                     LEFT JOIN progress p ON c.id=p.course_id
                     WHERE c.creator_id=? GROUP BY c.id''', (current_user.id,))
        course_stats = [{'id': row[0], 'title': row[1], 'enrolled': row[2], 'avg_grade': row[3] or 0, 'completion_rate': row[4] or 0} for row in c.fetchall()]
        # Assignment stats
        c.execute('''SELECT c.title, a.name, AVG(p.grade), MIN(p.grade), MAX(p.grade), COUNT(p.id)
                     FROM assignments a JOIN courses c ON a.course_id=c.id
                     LEFT JOIN progress p ON a.name=p.assignment_name AND a.course_id=p.course_id
                     WHERE c.creator_id=? GROUP BY a.id''', (current_user.id,))
        assignment_stats = [{'course': row[0], 'assignment': row[1], 'avg': row[2] or 0, 'min': row[3], 'max': row[4], 'count': row[5]} for row in c.fetchall()]
        # At-risk students
        c.execute('''SELECT c.title, u.username, AVG(p.grade), SUM(CASE WHEN p.status!='completed' THEN 1 ELSE 0 END)
                     FROM progress p JOIN users u ON p.user_id=u.id JOIN courses c ON p.course_id=c.id
                     WHERE c.creator_id=? GROUP BY c.title, u.username HAVING AVG(p.grade)<60 OR SUM(CASE WHEN p.status!='completed' THEN 1 ELSE 0 END)>0''', (current_user.id,))
        at_risk_students = [{'course': row[0], 'username': row[1], 'avg_grade': row[2] or 0, 'incomplete': row[3]} for row in c.fetchall()]
        # Engagement over time (submissions per week for all creator's courses)
        c.execute('''SELECT strftime('%Y-%W', p.created_at), COUNT(*) FROM progress p JOIN courses c ON p.course_id=c.id WHERE c.creator_id=? GROUP BY strftime('%Y-%W', p.created_at) ORDER BY strftime('%Y-%W', p.created_at)''', (current_user.id,))
        engagement_labels = []
        engagement_counts = []
        for row in c.fetchall():
            engagement_labels.append(row[0])
            engagement_counts.append(row[1])
        # Assignment completion trends (percent completed per assignment)
        c.execute('''SELECT a.name, COUNT(p.id), SUM(CASE WHEN p.status='completed' THEN 1 ELSE 0 END) FROM assignments a LEFT JOIN progress p ON a.name=p.assignment_name AND a.course_id=p.course_id WHERE a.course_id IN (SELECT id FROM courses WHERE creator_id=?) GROUP BY a.id''', (current_user.id,))
        assignment_names = []
        assignment_completion_rates = []
        for row in c.fetchall():
            assignment_names.append(row[0])
            total = row[1]
            completed = row[2] or 0
            rate = (completed/total*100) if total else 0
            assignment_completion_rates.append(rate)
        # Active users per week (unique students submitting per week)
        c.execute('''SELECT strftime('%Y-%W', p.created_at), COUNT(DISTINCT p.user_id) FROM progress p JOIN courses c ON p.course_id=c.id WHERE c.creator_id=? GROUP BY strftime('%Y-%W', p.created_at) ORDER BY strftime('%Y-%W', p.created_at)''', (current_user.id,))
        active_labels = []
        active_counts = []
        for row in c.fetchall():
            active_labels.append(row[0])
            active_counts.append(row[1])
        conn.close()
        # Recent AI feedback (stub: last 3 feedbacks from progress)
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT ai_grade FROM progress WHERE user_id=? AND ai_grade IS NOT NULL ORDER BY id DESC LIMIT 3', (current_user.id,))
        ai_feedback = [row[0] for row in c.fetchall() if row[0]]
        conn.close()
        return render_template('dashboard.html', is_creator=True, course_stats=course_stats, assignment_stats=assignment_stats, at_risk_students=at_risk_students, recommend_resources=recommend_resources(current_user.id), recommend_assignments=recommend_assignments(current_user.id), ai_feedback=ai_feedback, engagement_labels=engagement_labels, engagement_counts=engagement_counts, assignment_names=assignment_names, assignment_completion_rates=assignment_completion_rates, active_labels=active_labels, active_counts=active_counts)
    else:
        # Student progress
        c.execute('''SELECT c.title, AVG(p.grade), AVG(CASE WHEN p.status='completed' THEN 1 ELSE 0 END)*100
                     FROM courses c JOIN enrollments e ON c.id=e.course_id
                     LEFT JOIN progress p ON c.id=p.course_id AND p.user_id=?
                     WHERE e.user_id=? GROUP BY c.id''', (current_user.id, current_user.id))
        progress_stats = [{'title': row[0], 'avg_grade': row[1] or 0, 'completion_rate': row[2] or 0} for row in c.fetchall()]
        # Grade trends
        c.execute('''SELECT a.name, p.grade FROM assignments a JOIN progress p ON a.name=p.assignment_name AND a.course_id=p.course_id WHERE p.user_id=? ORDER BY a.due_date''', (current_user.id,))
        grade_trends = [{'assignment': row[0], 'grade': row[1]} for row in c.fetchall()]
        # Completion timeline
        c.execute('''SELECT a.name, ROW_NUMBER() OVER (ORDER BY a.due_date) as idx FROM assignments a JOIN progress p ON a.name=p.assignment_name AND a.course_id=p.course_id WHERE p.user_id=? AND p.status='completed' ORDER BY a.due_date''', (current_user.id,))
        completion_timeline = [{'assignment': row[0], 'index': row[1]} for row in c.fetchall()]
        # Upcoming assignments
        c.execute('''SELECT a.name, a.due_date FROM assignments a JOIN enrollments e ON a.course_id=e.course_id WHERE e.user_id=? AND a.due_date>=date('now') ORDER BY a.due_date''', (current_user.id,))
        upcoming_assignments = [{'name': row[0], 'due_date': row[1]} for row in c.fetchall()]
        conn.close()
        return render_template('dashboard.html', is_creator=False, progress_stats=progress_stats, grade_trends=grade_trends, completion_timeline=completion_timeline, upcoming_assignments=upcoming_assignments)

@app.route('/dashboard/export_assignments')
@login_required
def export_assignments():
    if current_user.role != 'creator':
        return 'Forbidden', 403
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT c.title, a.name, AVG(p.grade), MIN(p.grade), MAX(p.grade), COUNT(p.id)
                 FROM assignments a JOIN courses c ON a.course_id=c.id
                 LEFT JOIN progress p ON a.name=p.assignment_name AND a.course_id=p.course_id
                 WHERE c.creator_id=? GROUP BY a.id''', (current_user.id,))
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Course', 'Assignment', 'Avg', 'Min', 'Max', 'Submissions'])
    for row in c.fetchall():
        writer.writerow(row)
    conn.close()
    output.seek(0)
    return (output.getvalue(), 200, {'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=assignment_stats.csv'})

@app.route('/dashboard/export_progress')
@login_required
def export_progress():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT c.title, a.name, p.grade, p.status FROM assignments a JOIN progress p ON a.name=p.assignment_name AND a.course_id=p.course_id JOIN courses c ON a.course_id=c.id WHERE p.user_id=?''', (current_user.id,))
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Course', 'Assignment', 'Grade', 'Status'])
    for row in c.fetchall():
        writer.writerow(row)
    conn.close()
    output.seek(0)
    return (output.getvalue(), 200, {'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=progress.csv'})

@app.route('/leaderboard')
@login_required
def leaderboard():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT username, display_name, points, badges FROM users ORDER BY points DESC LIMIT 20')
    users = c.fetchall()
    conn.close()
    return render_template('leaderboard.html', users=users)

@app.route('/api/docs')
def api_docs():
    return '''<h1>API Documentation</h1>
    <p>Authenticate with <b>Authorization: Bearer &lt;token&gt;</b> header.</p>
    <ul>
        <li>GET /api/courses</li>
        <li>GET /api/course/&lt;id&gt;/enrollments</li>
        <li>GET /api/course/&lt;id&gt;/progress</li>
        <li>... (see code for more endpoints)</li>
    </ul>
    '''

@app.route('/calendar/assignment/<int:assignment_id>.ics')
def calendar_assignment(assignment_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT a.name, a.due_date, c.title FROM assignments a JOIN courses c ON a.course_id = c.id WHERE a.id = ?', (assignment_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return 'Not found', 404
    name, due_date, course_title = row
    ics = f"""BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nSUMMARY:{course_title} - {name}\nDTSTART;VALUE=DATE:{due_date.replace('-','')}\nDTEND;VALUE=DATE:{due_date.replace('-','')}\nDESCRIPTION:Assignment due in {course_title}\nEND:VEVENT\nEND:VCALENDAR"""
    response = make_response(ics)
    response.headers['Content-Disposition'] = f'attachment; filename={name}.ics'
    response.headers['Content-Type'] = 'text/calendar'
    return response

@app.route('/course/<int:course_id>/add_external_resource', methods=['POST'])
@login_required
def add_external_resource(course_id):
    title = request.form.get('ext_title')
    url = request.form.get('ext_url')
    # Basic validation
    if not title or not url:
        flash('Title and URL are required for external resources.')
        return redirect(url_for('resources', course_id=course_id))
    # Sanitize and check URL
    parsed = urlparse(url)
    if not parsed.scheme.startswith('http'):
        flash('Invalid URL scheme.')
        return redirect(url_for('resources', course_id=course_id))
    
    # Determine type and handle YouTube transcripts
    transcript = None
    if 'youtube.com' in url or 'youtu.be' in url:
        type_ = 'youtube'
        # Extract YouTube video ID and get transcript
        video_id = extract_youtube_id(url)
        if video_id:
            transcript = get_youtube_transcript(video_id)
            if transcript:
                flash('YouTube video added with transcript!')
            else:
                flash('YouTube video added! (No transcript available)')
        else:
            flash('YouTube video added! (Could not extract video ID)')
    elif 'docs.google.com' in url:
        type_ = 'gdoc'
        flash('External resource added!')
    elif url.lower().endswith('.pdf'):
        type_ = 'pdf'
        flash('External resource added!')
    else:
        type_ = 'link'
        flash('External resource added!')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Check if transcript and chapter columns exist, add if not
    c.execute("PRAGMA table_info(resources_external)")
    columns = [col[1] for col in c.fetchall()]
    if 'transcript' not in columns:
        c.execute('ALTER TABLE resources_external ADD COLUMN transcript TEXT')
    if 'chapter' not in columns:
        c.execute('ALTER TABLE resources_external ADD COLUMN chapter INTEGER DEFAULT 0')
        conn.commit()
    
    # Get chapter from form or default to 0
    chapter = int(request.form.get('chapter', 0))
    
    c.execute('INSERT INTO resources_external (course_id, title, url, type, transcript, chapter) VALUES (?, ?, ?, ?, ?, ?)', 
              (course_id, title, url, type_, transcript, chapter))
    conn.commit()
    conn.close()
    return redirect(url_for('resources', course_id=course_id))

@app.route('/course/<int:course_id>/delete_external_resource/<int:res_id>', methods=['POST'])
@login_required
def delete_external_resource(course_id, res_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM resources_external WHERE id=? AND course_id=?', (res_id, course_id))
    conn.commit()
    conn.close()
    flash('External resource deleted.')
    return redirect(url_for('resources', course_id=course_id))

@app.route('/course/<int:course_id>/youtube_transcript/<int:res_id>')
@login_required
def get_youtube_transcript_data(course_id, res_id):
    """Get YouTube transcript data for a specific resource"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT transcript FROM resources_external WHERE id=? AND course_id=? AND type="youtube"', (res_id, course_id))
    result = c.fetchone()
    conn.close()
    
    if result and result[0]:
        return jsonify({'transcript': result[0]})
    else:
        return jsonify({'transcript': None, 'error': 'No transcript available'})

@app.route('/course/<int:course_id>/refresh_transcript/<int:res_id>', methods=['POST'])
@login_required
def refresh_youtube_transcript(course_id, res_id):
    """Refresh YouTube transcript for a specific resource"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT url FROM resources_external WHERE id=? AND course_id=? AND type="youtube"', (res_id, course_id))
    result = c.fetchone()
    
    if result:
        video_id = extract_youtube_id(result[0])
        if video_id:
            transcript = get_youtube_transcript(video_id)
            if transcript:
                c.execute('UPDATE resources_external SET transcript=? WHERE id=?', (transcript, res_id))
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': 'Transcript refreshed successfully!'})
            else:
                conn.close()
                return jsonify({'success': False, 'message': 'Could not fetch transcript. Video may not have captions.'})
        else:
            conn.close()
            return jsonify({'success': False, 'message': 'Could not extract video ID from URL.'})
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Resource not found.'})

@app.route('/course/<int:course_id>/add_note', methods=['POST'])
@login_required
def add_note(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("PRAGMA table_info(notes)")
    columns = [col[1] for col in c.fetchall()]
    if 'ext_url' not in columns:
        c.execute('ALTER TABLE notes ADD COLUMN ext_url TEXT')
        c.execute('ALTER TABLE notes ADD COLUMN ext_type TEXT')
        conn.commit()
    content = request.form.get('content')
    ext_url = request.form.get('ext_url')
    ext_type = None
    if ext_url:
        if 'youtube.com' in ext_url or 'youtu.be' in ext_url:
            ext_type = 'youtube'
        elif 'docs.google.com' in ext_url:
            ext_type = 'gdoc'
        elif ext_url.lower().endswith('.pdf'):
            ext_type = 'pdf'
        else:
            ext_type = 'link'
    c.execute('INSERT INTO notes (course_id, user_id, content, ext_url, ext_type) VALUES (?, ?, ?, ?, ?)', (course_id, current_user.id, content, ext_url, ext_type))
    conn.commit()
    conn.close()
    flash('Note added!')
    return redirect(url_for('notes', course_id=course_id))

@app.route('/course/<int:course_id>/add_lti_tool', methods=['POST'])
@login_required
def add_lti_tool(course_id):
    title = request.form.get('lti_title')
    launch_url = request.form.get('lti_url')
    consumer_key = request.form.get('lti_key')
    consumer_secret = request.form.get('lti_secret')
    if not title or not launch_url or not consumer_key or not consumer_secret:
        flash('All LTI tool fields are required.')
        return redirect(url_for('resources', course_id=course_id))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('INSERT INTO lti_tools (course_id, title, launch_url, consumer_key, consumer_secret) VALUES (?, ?, ?, ?, ?)', (course_id, title, launch_url, consumer_key, consumer_secret))
    conn.commit()
    conn.close()
    flash('LTI tool added!')
    return redirect(url_for('resources', course_id=course_id))

@app.route('/course/<int:course_id>/delete_lti_tool/<int:lti_id>', methods=['POST'])
@login_required
def delete_lti_tool(course_id, lti_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM lti_tools WHERE id=? AND course_id=?', (lti_id, course_id))
    conn.commit()
    conn.close()
    flash('LTI tool deleted.')
    return redirect(url_for('resources', course_id=course_id))

@app.route('/lti/launch/<int:lti_id>', methods=['POST'])
@login_required
def lti_launch(lti_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT launch_url, consumer_key, consumer_secret, title FROM lti_tools WHERE id=?', (lti_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return 'LTI tool not found', 404
    launch_url, consumer_key, consumer_secret, title = row
    # LTI 1.1 launch params
    params = {
        'lti_version': 'LTI-1p0',
        'lti_message_type': 'basic-lti-launch-request',
        'resource_link_id': str(uuid.uuid4()),
        'user_id': str(current_user.id),
        'roles': current_user.role,
        'lis_person_name_full': current_user.username,
        'lis_person_contact_email_primary': getattr(current_user, 'email', ''),
        'launch_presentation_locale': 'en-US',
        'oauth_consumer_key': consumer_key,
        'oauth_nonce': str(uuid.uuid4()),
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': str(int(time.time())),
        'oauth_version': '1.0',
    }
    # OAuth 1.0a signature
    base_items = [(k, params[k]) for k in sorted(params)]
    base_str = 'POST&' + urlencode({launch_url: ''})[:-1] + '&' + urlencode(base_items).replace('+', '%20').replace('%7E', '~')
    key = consumer_secret + '&'
    signature = base64.b64encode(hmac.new(key.encode(), base_str.encode(), hashlib.sha1).digest()).decode()
    params['oauth_signature'] = signature
    # Render auto-submitting form
    return render_template('lti_launch.html', launch_url=launch_url, params=params, title=title)

@app.route('/course/<int:course_id>/add_webhook', methods=['POST'])
@login_required
def add_webhook(course_id):
    url = request.form.get('webhook_url')
    event_type = request.form.get('webhook_event')
    if not url or not event_type:
        flash('Webhook URL and event type are required.')
        return redirect(url_for('resources', course_id=course_id))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('INSERT INTO webhooks (course_id, url, event_type, last_status) VALUES (?, ?, ?, ?)', (course_id, url, event_type, 'Never triggered'))
    conn.commit()
    conn.close()
    flash('Webhook added!')
    return redirect(url_for('resources', course_id=course_id))

@app.route('/course/<int:course_id>/delete_webhook/<int:webhook_id>', methods=['POST'])
@login_required
def delete_webhook(course_id, webhook_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM webhooks WHERE id=? AND course_id=?', (webhook_id, course_id))
    conn.commit()
    conn.close()
    flash('Webhook deleted.')
    return redirect(url_for('resources', course_id=course_id))

def trigger_webhooks(course_id, event_type, payload):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, url FROM webhooks WHERE course_id=? AND event_type=?', (course_id, event_type))
    webhooks = c.fetchall()
    for webhook_id, url in webhooks:
        try:
            resp = requests.post(url, json=payload, timeout=5)
            status = f'{resp.status_code} {resp.reason}'
        except Exception as e:
            status = f'Error: {e}'
        c.execute('UPDATE webhooks SET last_status=? WHERE id=?', (status, webhook_id))
    conn.commit()
    conn.close()

csrf = CSRFProtect(app)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[]
)

@app.route('/connect/google')
@login_required
def connect_google():
    # Redirect to Google OAuth (stub)
    return 'Google Drive integration coming soon!'

@app.route('/connect/slack')
@login_required
def connect_slack():
    # Redirect to Slack OAuth (stub)
    return 'Slack integration coming soon!'

@app.route('/oauth2callback/google')
def google_oauth_callback():
    # Handle Google OAuth callback (stub)
    return 'Google Drive OAuth callback!'

@app.route('/oauth2callback/slack')
def slack_oauth_callback():
    # Handle Slack OAuth callback (stub)
    return 'Slack OAuth callback!'

def recommend_resources(user_id):
    # Recommend resources based on enrolled courses and past activity (stub: top 3 most popular)
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT r.id, r.title, COUNT(p.id) as used FROM resources_external r LEFT JOIN progress p ON r.course_id=p.course_id GROUP BY r.id ORDER BY used DESC LIMIT 3''')
    recs = c.fetchall()
    conn.close()
    return recs

def recommend_assignments(user_id):
    # Recommend assignments not yet completed, sorted by due date
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT a.id, a.name, a.due_date FROM assignments a JOIN enrollments e ON a.course_id=e.course_id WHERE e.user_id=? AND a.id NOT IN (SELECT assignment_name FROM progress WHERE user_id=?) ORDER BY a.due_date''', (user_id, user_id))
    recs = c.fetchall()
    conn.close()
    return recs

def send_ai_feedback_notification(user_id, feedback):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('INSERT INTO notifications (user_id, message, link) VALUES (?, ?, ?)', (user_id, f'New AI feedback: {feedback[:80]}...', None))
    conn.commit()
    conn.close()

@csrf.exempt
@app.route('/ai_feedback_forum', methods=['POST'])
def ai_feedback_forum():
    print("DEBUG: /ai_feedback_forum endpoint hit")
    logging.debug(f"Headers: {dict(request.headers)}")
    logging.debug(f"Raw data: {request.data}")
    if not request.is_json:
        logging.error('Request to /ai_feedback_forum is not JSON. Headers: %s', dict(request.headers))
        print('ERROR: Request is not JSON')
        return jsonify({'feedback': 'Request must be JSON.'}), 400
    data = request.get_json(silent=True)
    logging.debug(f"Parsed JSON: {data}")
    if not data:
        logging.error('No JSON data received in /ai_feedback_forum. Raw data: %s', request.data)
        print('ERROR: No JSON data received')
        return jsonify({'feedback': 'No JSON data received.'}), 400
    content = data.get('content', '')
    logging.debug(f"Extracted content: {content}")
    if not content or not isinstance(content, str):
        logging.error('No valid content in /ai_feedback_forum. Data: %s', data)
        print('ERROR: No valid content provided')
        return jsonify({'feedback': 'No valid content provided.'}), 400
    prompt = (
        "You are a friendly, helpful tutor. Someone just posted this in a forum: "
        f"'{content}' "
        "Give them a helpful response that: "
        "1. Acknowledges their question or comment in a friendly way "
        "2. Explains the concept in simple, everyday language (like you're talking to a friend) "
        "3. Gives them a practical tip or example they can use "
        "Keep it conversational and natural. Don't use technical jargon unless necessary. "
        "Write as if you're having a casual chat with them."
    )
    feedback = gemini_feedback(prompt)
    # Remove asterisks and excessive whitespace from the response
    if feedback:
        feedback = feedback.replace('*', '').strip()
    print(f"DEBUG: Gemini feedback: {feedback}")
    return jsonify({'feedback': feedback})

@csrf.exempt
@app.route('/ai_feedback_note', methods=['POST'])
def ai_feedback_note():
    print("DEBUG: /ai_feedback_note endpoint hit")
    logging.debug(f"Headers: {dict(request.headers)}")
    logging.debug(f"Raw data: {request.data}")
    if not request.is_json:
        logging.error('Request to /ai_feedback_note is not JSON. Headers: %s', dict(request.headers))
        print('ERROR: Request is not JSON')
        return jsonify({'feedback': 'Request must be JSON.'}), 400
    data = request.get_json(silent=True)
    logging.debug(f"Parsed JSON: {data}")
    if not data:
        logging.error('No JSON data received in /ai_feedback_note. Raw data: %s', request.data)
        print('ERROR: No JSON data received')
        return jsonify({'feedback': 'No JSON data received.'}), 400
    content = data.get('content', '')
    note_id = data.get('note_id')
    logging.debug(f"Extracted content: {content}, note_id: {note_id}")
    if not content and not note_id:
        logging.error('No valid content or note_id in /ai_feedback_note. Data: %s', data)
        print('ERROR: No valid content or note_id provided')
        return jsonify({'feedback': 'No valid content or note_id provided.'}), 400
    if note_id and not content:
        # Fetch content from database using note_id
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT content FROM notes WHERE id = ?', (note_id,))
        note = c.fetchone()
        conn.close()
        if note:
            content = note[0]
        else:
            return jsonify({'feedback': 'Note not found.'}), 404
    if not content or not isinstance(content, str):
        logging.error('No valid content in /ai_feedback_note. Data: %s', data)
        print('ERROR: No valid content provided')
        return jsonify({'feedback': 'No valid content provided.'}), 400
    prompt = (
        "You are a friendly tutor helping a student with their notes. They wrote: "
        f"'{content}' "
        "Give them some helpful feedback that: "
        "1. Acknowledges what they've written in a friendly way "
        "2. Explains any concepts they might be confused about in simple terms "
        "3. Suggests how they could expand or improve their notes "
        "4. Encourages them to keep learning "
        "Write like you're talking to a friend - be encouraging and helpful, not formal."
    )
    feedback = gemini_feedback(prompt)
    # Remove asterisks and excessive whitespace from the response
    if feedback:
        feedback = feedback.replace('*', '').strip()
    print(f"DEBUG: Gemini feedback: {feedback}")
    return jsonify({'feedback': feedback})

# Serve service-worker.js and manifest.json from root
@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('.', 'service-worker.js')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')

# Ensure CSRFProtect is initialized and SECRET_KEY is set
from flask_wtf import CSRFProtect
app.secret_key = app.config.get('SECRET_KEY', 'your-very-secret-key')
csrf = CSRFProtect(app)

# Ensure threads table has user_id and content columns
conn = sqlite3.connect('database.db')
c = conn.cursor()
c.execute("PRAGMA table_info(threads)")
thread_columns = [col[1] for col in c.fetchall()]
if 'user_id' not in thread_columns:
    c.execute('ALTER TABLE threads ADD COLUMN user_id INTEGER')
if 'content' not in thread_columns:
    c.execute('ALTER TABLE threads ADD COLUMN content TEXT')
conn.commit()
conn.close()

CORS(app, resources={r"/ai_feedback_forum": {"origins": "*"}, r"/ai_feedback_note": {"origins": "*"}})

@app.route('/course/<int:course_id>/upload_subtitle', methods=['POST'])
@login_required
def upload_subtitle(course_id):
    if current_user.role != 'creator':
        flash('Only creators can upload subtitles.')
        return redirect(url_for('resources', course_id=course_id))
    file = request.files.get('subtitle_file')
    video_file_id = request.form.get('video_file_id')
    if not file or not video_file_id:
        flash('Subtitle file and video file ID must be provided.')
        return redirect(url_for('resources', course_id=course_id))
    if not allowed_subtitle(file.filename):
        flash('Only .vtt or .srt subtitle files are supported.')
        return redirect(url_for('resources', course_id=course_id))
    ext = os.path.splitext(file.filename)[1].lower()
    filename = f"subtitle_{course_id}_{video_file_id}{ext}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE course_files SET subtitle_path = ? WHERE id = ?', (file_path, video_file_id))
    conn.commit()
    conn.close()
    flash('Subtitle uploaded successfully!')
    return redirect(url_for('resources', course_id=course_id))

@app.route('/subtitles/<int:file_id>')
@login_required
def serve_subtitle(file_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT course_id, subtitle_path FROM course_files WHERE id = ?', (file_id,))
    file_data = c.fetchone()
    if not file_data:
        conn.close()
        flash('Subtitle file not found.')
        return redirect(url_for('home'))
    course_id, subtitle_path = file_data
    c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
    if not c.fetchone():
        conn.close()
        flash('You must be enrolled to access this subtitle file.')
        return redirect(url_for('home'))
    conn.close()
    if not subtitle_path or not os.path.exists(subtitle_path):
        flash('Subtitle file not available.')
        return redirect(url_for('home'))
    return send_file(subtitle_path, mimetype='text/vtt' if subtitle_path.endswith('.vtt') else 'application/x-subrip')

@app.route('/course/<int:course_id>/thread/<int:thread_id>/post', methods=['POST'])
@login_required
def add_post_to_thread(course_id, thread_id):
    """Add a post/reply to an existing thread"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Verify thread exists and belongs to this course
    c.execute('SELECT id FROM threads WHERE id = ? AND course_id = ?', (thread_id, course_id))
    thread = c.fetchone()
    if not thread:
        conn.close()
        flash('Thread not found.')
        return redirect(url_for('forum', course_id=course_id))
    
    # Verify user is enrolled in the course
    c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
    enrollment = c.fetchone()
    if not enrollment:
        conn.close()
        flash('You must be enrolled to post in this forum.')
        return redirect(url_for('forum', course_id=course_id))
    
    content = request.form.get('content')
    if not content or not content.strip():
        conn.close()
        flash('Post content is required.')
        return redirect(url_for('forum', course_id=course_id))
    
    ext_url = request.form.get('ext_url')
    ext_type = None
    if ext_url:
        if 'youtube.com' in ext_url or 'youtu.be' in ext_url:
            ext_type = 'youtube'
        elif 'docs.google.com' in ext_url:
            ext_type = 'gdoc'
        elif ext_url.lower().endswith('.pdf'):
            ext_type = 'pdf'
        else:
            ext_type = 'link'
    
    # Add post to thread
    c.execute('INSERT INTO posts (thread_id, user_id, enrollment_number, content, ext_url, ext_type) VALUES (?, ?, ?, ?, ?, ?)', 
             (thread_id, current_user.id, enrollment[0], content.strip(), ext_url, ext_type))
    conn.commit()
    conn.close()
    
    flash('Reply posted successfully!')
    return redirect(url_for('forum', course_id=course_id))

@csrf.exempt
@app.route('/ai_feedback_thread', methods=['POST'])
def ai_feedback_thread():
    """Get AI feedback for an entire thread including all posts"""
    print("DEBUG: /ai_feedback_thread endpoint hit")
    logging.debug(f"Headers: {dict(request.headers)}")
    logging.debug(f"Raw data: {request.data}")
    
    if not request.is_json:
        logging.error('Request to /ai_feedback_thread is not JSON. Headers: %s', dict(request.headers))
        print('ERROR: Request is not JSON')
        return jsonify({'feedback': 'Request must be JSON.'}), 400
    
    data = request.get_json(silent=True)
    logging.debug(f"Parsed JSON: {data}")
    
    if not data:
        logging.error('No JSON data received in /ai_feedback_thread. Raw data: %s', request.data)
        print('ERROR: No JSON data received')
        return jsonify({'feedback': 'No JSON data received.'}), 400
    
    thread_id = data.get('thread_id')
    if not thread_id:
        logging.error('No thread_id provided in /ai_feedback_thread. Data: %s', data)
        print('ERROR: No thread_id provided')
        return jsonify({'feedback': 'No thread_id provided.'}), 400
    
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        # Get thread info
        c.execute('SELECT title, content FROM threads WHERE id = ?', (thread_id,))
        thread = c.fetchone()
        if not thread:
            conn.close()
            return jsonify({'feedback': 'Thread not found.'}), 404
        
        thread_title, thread_content = thread
        
        # Get all posts in the thread
        c.execute('''SELECT p.content, u.username, u.display_name 
                     FROM posts p JOIN users u ON p.user_id = u.id 
                     WHERE p.thread_id = ? ORDER BY p.created_at ASC''', (thread_id,))
        posts = c.fetchall()
        conn.close()
        
        # Combine all content for analysis
        all_content = f"Thread: {thread_title}\n\nOriginal post: {thread_content}\n\n"
        all_content += "Replies:\n"
        for i, (post_content, username, display_name) in enumerate(posts, 1):
            author = display_name or username
            all_content += f"Reply {i} by {author}: {post_content}\n\n"
        
        prompt = (
            "You are a friendly tutor looking at a class discussion. Here's what people are talking about: "
            f"{all_content}"
            "Give the class some helpful feedback that: "
            "1. Summarizes what they're discussing in simple terms "
            "2. Points out what's good about their discussion "
            "3. Suggests one or two ways they could explore the topic further "
            "4. Encourages them to keep the conversation going "
            "Write like you're talking to friends - be encouraging and helpful, not formal or robotic."
        )
        
        feedback = gemini_feedback(prompt)
        if feedback:
            feedback = feedback.replace('*', '').strip()
        
        print(f"DEBUG: Thread feedback: {feedback}")
        return jsonify({'feedback': feedback})
        
    except Exception as e:
        logging.error('Error in /ai_feedback_thread: %s', str(e))
        return jsonify({'feedback': f'Error analyzing thread: {str(e)}'}), 500

@app.route('/admin/pending_approvals')
@login_required
def pending_approvals():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('home_dashboard'))
    role_filter = request.args.get('role')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if role_filter == 'creator':
        c.execute('SELECT id, username, role, full_name, email, phone, institution, payment_screenshot FROM users WHERE is_approved=0 AND role="creator"')
    elif role_filter == 'student':
        c.execute('SELECT id, username, role, full_name, email, phone, institution, payment_screenshot FROM users WHERE is_approved=0 AND role="student"')
    else:
        c.execute('SELECT id, username, role, full_name, email, phone, institution, payment_screenshot FROM users WHERE is_approved=0')
    pending_users = c.fetchall()
    conn.close()
    return render_template('pending_approvals.html', pending_users=pending_users, role_filter=role_filter)

@app.route('/admin/approve_user/<int:user_id>', methods=['POST'])
@login_required
def approve_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('home_dashboard'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE users SET is_approved=1 WHERE id=?', (user_id,))
    conn.commit()
    conn.close()
    flash('User approved!')
    return redirect(url_for('pending_approvals'))

@app.route('/admin/reject_user/<int:user_id>', methods=['POST'])
@login_required
def reject_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('home_dashboard'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id=?', (user_id,))
    conn.commit()
    conn.close()
    flash('User rejected and deleted!')
    return redirect(url_for('pending_approvals'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get platform statistics
    c.execute('SELECT COUNT(*) FROM users WHERE role = "student"')
    total_students = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE role = "creator"')
    total_instructors = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM courses')
    total_courses = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM enrollments')
    total_enrollments = c.fetchone()[0]
    
    # Get recent activity
    c.execute('SELECT COUNT(*) FROM users WHERE role = "student" AND is_approved = 0')
    pending_students = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE role = "creator" AND is_approved = 0')
    pending_instructors = c.fetchone()[0]
    
    # Get top courses by enrollment
    c.execute('''
        SELECT c.title, COUNT(e.id) as enrollment_count 
        FROM courses c 
        LEFT JOIN enrollments e ON c.id = e.course_id 
        GROUP BY c.id 
        ORDER BY enrollment_count DESC 
        LIMIT 5
    ''')
    top_courses = c.fetchall()
    
    # Get recent user registrations
    c.execute('''
        SELECT username, role, created_at 
        FROM users 
        ORDER BY created_at DESC 
        LIMIT 10
    ''')
    recent_users = c.fetchall()
    
    # Get course creation trends (last 30 days)
    c.execute('''
        SELECT DATE(created_at) as date, COUNT(*) as count 
        FROM courses 
        WHERE created_at >= date("now", "-30 days") 
        GROUP BY DATE(created_at) 
        ORDER BY date
    ''')
    course_trends = c.fetchall()
    
    # Get enrollment trends
    c.execute('''
        SELECT DATE(enrollment_date) as date, COUNT(*) as count 
        FROM enrollments 
        WHERE enrollment_date >= date("now", "-30 days") 
        GROUP BY DATE(enrollment_date) 
        ORDER BY date
    ''')
    enrollment_trends = c.fetchall()
    
    # Get approved instructors for blocking
    c.execute('SELECT id, username, full_name, email, is_blocked FROM users WHERE role = "creator" AND is_approved = 1')
    approved_instructors = c.fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         total_students=total_students,
                         total_instructors=total_instructors,
                         total_courses=total_courses,
                         total_enrollments=total_enrollments,
                         pending_students=pending_students,
                         pending_instructors=pending_instructors,
                         top_courses=top_courses,
                         recent_users=recent_users,
                         course_trends=course_trends,
                         enrollment_trends=enrollment_trends,
                         approved_instructors=approved_instructors)

@app.route('/register_instructor', methods=['GET', 'POST'])
def register_instructor():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        institution = request.form['institution']
        role = 'creator'
        payment_file = request.files.get('payment_screenshot')
        payment_path = None
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        # Ensure new columns exist
        c.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in c.fetchall()]
        if 'full_name' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN full_name TEXT')
        if 'email' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN email TEXT')
        if 'phone' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN phone TEXT')
        if 'institution' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN institution TEXT')
        if 'payment_screenshot' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN payment_screenshot TEXT')
        if payment_file and payment_file.filename:
            filename = f"payment_{username}_{int(time.time())}.{payment_file.filename.rsplit('.', 1)[-1]}"
            payment_path = os.path.join('static', 'uploads', filename)
            os.makedirs(os.path.dirname(payment_path), exist_ok=True)
            payment_file.save(payment_path)
        try:
            c.execute('INSERT INTO users (username, password, role, is_approved, full_name, email, phone, institution, payment_screenshot) VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)', (username, password, role, full_name, email, phone, institution, payment_path))
            conn.commit()
            flash('Instructor registration submitted! Awaiting admin approval.')
            return render_template('pending_approval.html')
        except sqlite3.IntegrityError:
            flash('Username already exists.')
        finally:
            conn.close()
    return render_template('register.html', instructor_form=True)

# Route to mark a chapter as complete
@app.route('/course/<int:course_id>/chapter/<int:chapter_idx>/complete', methods=['POST'])
@login_required
def mark_chapter_complete(course_id, chapter_idx):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS chapter_progress (user_id INTEGER, course_id INTEGER, chapter_idx INTEGER, completed INTEGER, PRIMARY KEY (user_id, course_id, chapter_idx))")
    c.execute('INSERT OR REPLACE INTO chapter_progress (user_id, course_id, chapter_idx, completed) VALUES (?, ?, ?, ?)', (current_user.id, course_id, chapter_idx, 1))
    conn.commit()
    conn.close()
    flash(f'Chapter {chapter_idx + 1} marked as complete! You can now access the next chapter.')
    return redirect(url_for('resources', course_id=course_id))



# --- Instructor dashboard to approve/reject enrollments ---
@app.route('/instructor/enrollments')
@login_required
def instructor_enrollments():
    if current_user.role != 'creator':
        flash('Access denied.')
        return redirect(url_for('home'))
    
    # Get filter parameter
    status_filter = request.args.get('status', '')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, title FROM courses WHERE creator_id=?', (current_user.id,))
    courses = c.fetchall()
    enrollments = []
    users_data = {}
    
    for course in courses:
        c.execute('''SELECT enrollments.id, users.full_name, users.username, enrollments.is_approved_by_instructor, courses.title, enrollments.user_id, enrollments.course_id, users.avatar, users.is_blocked
                     FROM enrollments
                     JOIN users ON enrollments.user_id = users.id
                     JOIN courses ON enrollments.course_id = courses.id
                     WHERE enrollments.course_id=?''', (course[0],))
        course_enrollments = c.fetchall()
        
        # Apply status filter if specified
        if status_filter:
            if status_filter == 'pending':
                course_enrollments = [e for e in course_enrollments if e[3] == 0]
            elif status_filter == 'approved':
                course_enrollments = [e for e in course_enrollments if e[3] == 1]
            elif status_filter == 'rejected':
                course_enrollments = [e for e in course_enrollments if e[3] == -1]
            elif status_filter == 'blocked':
                course_enrollments = [e for e in course_enrollments if e[8] == 1]
        
        enrollments += course_enrollments
        
        # Store user data for easy access
        for enrollment in course_enrollments:
            user_id = enrollment[5]
            if user_id not in users_data:
                users_data[user_id] = {
                    'full_name': enrollment[1],
                    'username': enrollment[2],
                    'avatar': enrollment[7],
                    'is_blocked': enrollment[8]
                }
    
    conn.close()
    return render_template('instructor_enrollments.html', 
                         enrollments=enrollments, 
                         users_data=users_data,
                         status_filter=status_filter)

@app.route('/instructor/enrollments/<int:enrollment_id>/approve', methods=['POST'])
@login_required
def approve_enrollment(enrollment_id):
    if current_user.role != 'creator':
        flash('Access denied.')
        return redirect(url_for('home'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE enrollments SET is_approved_by_instructor=1 WHERE id=?', (enrollment_id,))
    conn.commit()
    conn.close()
    flash('Enrollment approved.')
    return redirect(url_for('instructor_enrollments'))

@app.route('/instructor/enrollments/<int:enrollment_id>/reject', methods=['POST'])
@login_required
def reject_enrollment(enrollment_id):
    if current_user.role != 'creator':
        flash('Access denied.')
        return redirect(url_for('home'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE enrollments SET is_approved_by_instructor=-1 WHERE id=?', (enrollment_id,))
    conn.commit()
    conn.close()
    flash('Enrollment rejected.')
    return redirect(url_for('instructor_enrollments'))

@app.route('/instructor/block_student/<int:user_id>', methods=['POST'])
@login_required
def block_student(user_id):
    if current_user.role != 'creator':
        flash('Access denied.')
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE users SET is_blocked = 1 WHERE id = ? AND role = "student"', (user_id,))
    conn.commit()
    conn.close()
    flash('Student has been blocked.')
    return redirect(url_for('instructor_enrollments'))

@app.route('/instructor/unblock_student/<int:user_id>', methods=['POST'])
@login_required
def unblock_student(user_id):
    if current_user.role != 'creator':
        flash('Access denied.')
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE users SET is_blocked = 0 WHERE id = ? AND role = "student"', (user_id,))
    conn.commit()
    conn.close()
    flash('Student has been unblocked.')
    return redirect(url_for('instructor_enrollments'))

@app.route('/course/<int:course_id>/overview')
@login_required
def course_overview(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get course data including outline and objectives
    c.execute('SELECT title, description, creator_id, meeting_link, outline, objectives FROM courses WHERE id = ?', (course_id,))
    course_data = c.fetchone()
    if not course_data:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    
    course_title, description, creator_id, meeting_link, outline, objectives = course_data
    
    # Get creator info
    c.execute('SELECT username, avatar, display_name FROM users WHERE id = ?', (creator_id,))
    creator_info = c.fetchone()
    creator_username = creator_info[0] if creator_info else 'Unknown'
    creator_avatar = creator_info[1] if creator_info else None
    creator_display_name = creator_info[2] if creator_info else creator_info[0]
    
    # Check if user is enrolled
    c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?', (current_user.id, course_id))
    enrollment = c.fetchone()
    is_enrolled = bool(enrollment)
    
    # Get chapter progress for enrolled users
    chapter_progress = []
    if is_enrolled:
        c.execute("CREATE TABLE IF NOT EXISTS chapter_progress (user_id INTEGER, course_id INTEGER, chapter_idx INTEGER, completed INTEGER, PRIMARY KEY (user_id, course_id, chapter_idx))")
        chapters = outline.split('\n') if outline else []
        for idx in range(len(chapters)):
            c.execute("SELECT completed FROM chapter_progress WHERE user_id=? AND course_id=? AND chapter_idx=?", (current_user.id, course_id, idx))
            row = c.fetchone()
            chapter_progress.append(bool(row and row[0]))
    
    conn.close()
    
    return render_template('course_overview.html', 
                         course_id=course_id, 
                         course_title=course_title, 
                         description=description,
                         outline=outline,
                         objectives=objectives,
                         meeting_link=meeting_link,
                         creator_username=creator_username,
                         creator_avatar=creator_avatar,
                         creator_display_name=creator_display_name,
                         is_enrolled=is_enrolled,
                         chapter_progress=chapter_progress)

@app.route('/courses')
@login_required
def list_courses():
    return redirect(url_for('home_dashboard'))

@app.route('/admin/block_user/<int:user_id>', methods=['POST'])
@login_required
def block_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE users SET is_blocked = 1 WHERE id = ? AND role = "creator"', (user_id,))
    conn.commit()
    conn.close()
    flash('Instructor has been blocked.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/unblock_user/<int:user_id>', methods=['POST'])
@login_required
def unblock_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE users SET is_blocked = 0 WHERE id = ? AND role = "creator"', (user_id,))
    conn.commit()
    conn.close()
    flash('Instructor has been unblocked.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export_analytics')
@login_required
def export_analytics():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get comprehensive analytics data
    c.execute('SELECT COUNT(*) FROM users WHERE role = "student"')
    total_students = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE role = "creator"')
    total_instructors = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM courses')
    total_courses = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM enrollments')
    total_enrollments = c.fetchone()[0]
    
    # Get top courses
    c.execute('''
        SELECT c.title, COUNT(e.id) as enrollment_count 
        FROM courses c 
        LEFT JOIN enrollments e ON c.id = e.course_id 
        GROUP BY c.id 
        ORDER BY enrollment_count DESC 
        LIMIT 10
    ''')
    top_courses = c.fetchall()
    
    # Get user statistics
    c.execute('SELECT role, COUNT(*) FROM users GROUP BY role')
    user_stats = c.fetchall()
    
    conn.close()
    
    # Create CSV content
    csv_content = "Platform Analytics Report\n\n"
    csv_content += "Overall Statistics\n"
    csv_content += f"Total Students,{total_students}\n"
    csv_content += f"Total Instructors,{total_instructors}\n"
    csv_content += f"Total Courses,{total_courses}\n"
    csv_content += f"Total Enrollments,{total_enrollments}\n\n"
    
    csv_content += "Top Courses by Enrollment\n"
    csv_content += "Course Title,Enrollment Count\n"
    for course in top_courses:
        csv_content += f"{course[0]},{course[1]}\n"
    
    csv_content += "\nUser Statistics by Role\n"
    csv_content += "Role,Count\n"
    for stat in user_stats:
        csv_content += f"{stat[0]},{stat[1]}\n"
    
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=platform_analytics.csv'
    return response

@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template('error.html', 
                         error_code=413,
                         error_title="File Too Large",
                         error_message="The file you're trying to upload is too large. Please ensure your file is under 50MB and try again.",
                         back_url=request.referrer or url_for('home')), 413

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html',
                         error_code=404,
                         error_title="Page Not Found",
                         error_message="The page you're looking for doesn't exist.",
                         back_url=request.referrer or url_for('home')), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html',
                         error_code=500,
                         error_title="Server Error",
                         error_message="Something went wrong on our end. Please try again later.",
                         back_url=request.referrer or url_for('home')), 500

if __name__ == '__main__':
    socketio.run(app, debug=True)
