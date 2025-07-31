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

nltk.download('vader_lexicon', quiet=True)

# Set Gemini API key to the provided value and ensure only this key is used
GEMINI_API_KEY = "AIzaSyDqWsXGh22b25uiSUviSw8EFTsGMt7wTwo"
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-2.0-flash')

def gemini_feedback(prompt):
    try:
        response = gemini_model.generate_content(prompt)
        return response.text if hasattr(response, 'text') else str(response)
    except Exception as e:
        return f"[Gemini error: {e}]"

app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ASSIGNMENT_UPLOAD_FOLDER'] = 'assignment_uploads'
app.config['SECRET_KEY'] = 'your-very-secret-key'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
app.config['WTF_CSRF_CHECK_DEFAULT'] = False
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
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, avatar TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS courses
                 (id INTEGER PRIMARY KEY, title TEXT, creator_id INTEGER, description TEXT, reference_file_path TEXT, meeting_link TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS course_files
                 (id INTEGER PRIMARY KEY, course_id INTEGER, filename TEXT, file_type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS enrollments
                 (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER, enrollment_number TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS threads
                 (id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT, creator_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, ext_url TEXT, ext_type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (id INTEGER PRIMARY KEY, thread_id INTEGER, user_id INTEGER, enrollment_number TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, ext_url TEXT, ext_type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS progress
                 (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER, assignment_name TEXT, status TEXT, grade INTEGER, file_path TEXT, ai_grade INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notes
                 (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS assignments
                 (id INTEGER PRIMARY KEY, course_id INTEGER, name TEXT, type TEXT, questions TEXT, correct_answers TEXT, due_date TIMESTAMP, meeting_link TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS assignment_keywords
                 (id INTEGER PRIMARY KEY, assignment_id INTEGER, keyword TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notifications
                 (id INTEGER PRIMARY KEY, user_id INTEGER, message TEXT, link TEXT, is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS resources_external
                 (id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT, url TEXT, type TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
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
        role = 'student'
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, role))
            conn.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
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
        c.execute('SELECT id, username, password, role FROM users WHERE username = ?', (username,))
        user_data = c.fetchone()
        conn.close()
        if user_data and check_password_hash(user_data[2], password):
            user = User(user_data[0], user_data[1], user_data[3])
            login_user(user)
            return redirect(url_for('home'))
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
        file = request.files.get('file')
        reference_file = request.files.get('reference_file')
        meeting_link = request.form.get('meeting_link')
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO courses (title, creator_id, description, reference_file_path, meeting_link) VALUES (?, ?, ?, ?, ?)',
                  (title, current_user.id, description, None, meeting_link))
        course_id = c.lastrowid
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
        file = request.files.get('file')
        reference_file = request.files.get('reference_file')
        meeting_link = request.form.get('meeting_link')
        c.execute('UPDATE courses SET title = ?, description = ?, meeting_link = ? WHERE id = ?',
                  (title, description, meeting_link, course_id))
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
    if current_user.role != 'creator':
        flash('Only creators can delete posts.')
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
    c.execute('SELECT id FROM posts WHERE id = ? AND thread_id IN (SELECT id FROM threads WHERE course_id = ?)', (post_id, course_id))
    post = c.fetchone()
    if not post:
        conn.close()
        flash('Post not found.')
        return redirect(url_for('forum', course_id=course_id))
    c.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    flash('Post deleted successfully!')
    return redirect(url_for('forum', course_id=course_id))

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
        c.execute('INSERT INTO threads (course_id, user_id, title, content, ext_url, ext_type) VALUES (?, ?, ?, ?, ?, ?)', (course_id, current_user.id, title, content, ext_url, ext_type))
        conn.commit()
        conn.close()
        flash('Thread created!')
        return redirect(url_for('forum', course_id=course_id))
    # GET: show threads
    c.execute('SELECT id, title, created_at, ext_url, ext_type FROM threads WHERE course_id = ?', (course_id,))
    threads = c.fetchall()
    threads_with_posts = []
    for thread in threads:
        c.execute('''SELECT p.id, p.enrollment_number, p.content, p.created_at, u.avatar, p.ext_url, p.ext_type
                     FROM posts p JOIN users u ON p.user_id = u.id
                     WHERE p.thread_id = ?''', (thread[0],))
        posts = c.fetchall()
        threads_with_posts.append((thread, posts))
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
    c.execute('SELECT id, title, created_at FROM threads WHERE course_id = ?', (course_id,))
    threads = c.fetchall()
    threads_with_posts = []
    for thread in threads:
        c.execute('SELECT id, enrollment_number, content, created_at FROM posts WHERE thread_id = ?', (thread[0],))
        posts = c.fetchall()
        threads_with_posts.append({
            'thread': {
                'id': thread[0],
                'title': thread[1],
                'created_at': thread[2]
            },
            'posts': [
                {
                    'id': post[0],
                    'enrollment_number': post[1],
                    'content': post[2],
                    'created_at': post[3]
                } for post in posts
            ]
        })
    conn.close()
    return jsonify({'threads': threads_with_posts})

@app.route('/course/<int:course_id>/resources')
@login_required
def resources(course_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT enrollment_number FROM enrollments WHERE user_id = ? AND course_id = ?',
              (current_user.id, course_id))
    enrollment = c.fetchone()
    if not enrollment:
        conn.close()
        flash('You must be enrolled to access resources.')
        return redirect(url_for('home'))
    c.execute('SELECT title FROM courses WHERE id = ?', (course_id,))
    course_data = c.fetchone()
    if not course_data:
        conn.close()
        flash('Course not found.')
        return redirect(url_for('home'))
    course_title = course_data[0]
    c.execute('SELECT id, filename, file_type FROM course_files WHERE course_id = ?', (course_id,))
    files = c.fetchall()
    # Fetch assignments for this course, with due_date
    c.execute('SELECT id, name, type, due_date FROM assignments WHERE course_id = ? ORDER BY due_date ASC', (course_id,))
    assignments = [{'id': row[0], 'name': row[1], 'type': row[2], 'due_date': row[3]} for row in c.fetchall()]
    c.execute('SELECT id, title, url, type FROM resources_external WHERE course_id=? ORDER BY created_at DESC', (course_id,))
    external_resources = c.fetchall()
    c.execute('SELECT id, title, launch_url FROM lti_tools WHERE course_id=? ORDER BY created_at DESC', (course_id,))
    lti_tools = c.fetchall()
    c.execute('SELECT id, url, event_type, last_status FROM webhooks WHERE course_id=? ORDER BY created_at DESC', (course_id,))
    webhooks = c.fetchall()
    # For each external resource, get latest AI feedback for this user (stub: none for now)
    for ext in external_resources:
        ext = list(ext)
        ext.append(None)  # Placeholder for future AI feedback
    conn.close()
    return render_template('resources.html', course_id=course_id, course_title=course_title, files=files, assignments=assignments, external_resources=external_resources, lti_tools=lti_tools, webhooks=webhooks)

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
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT title, creator_id, reference_file_path FROM courses WHERE id = ?', (course_id,))
    course_data = c.fetchone()
    if not course_data:
        conn.close()
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
        conn.close()
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
    conn.close()
    return render_template('progress.html', course_id=course_id, course_title=course_title, progress_data=progress_data, is_creator=is_creator, is_enrolled=bool(enrollment), reference_file=reference_file, assignments=assignments, assignment_status=assignment_status, creator_avatar=creator_avatar, creator_display_name=creator_display_name)

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
    c.execute('SELECT id FROM progress WHERE id = ? AND course_id = ?', (progress_id, course_id))
    progress = c.fetchone()
    if not progress:
        conn.close()
        flash('Progress record not found.')
        return redirect(url_for('progress', course_id=course_id))
    status = request.form.get('status')
    grade = request.form.get('grade')
    if status not in ['submitted', 'completed', 'incomplete']:
        conn.close()
        flash('Invalid status.')
        return redirect(url_for('progress', course_id=course_id))
    if grade:
        try:
            grade = int(grade)
            if not 0 <= grade <= 100:
                conn.close()
                flash('Grade must be between 0 and 100.')
                return redirect(url_for('progress', course_id=course_id))
        except ValueError:
            conn.close()
            flash('Grade must be a number.')
            return redirect(url_for('progress', course_id=course_id))
    else:
        grade = None
    c.execute('UPDATE progress SET status = ?, grade = ? WHERE id = ?', (status, grade, progress_id))
    # Notify student of grade update
    c.execute('SELECT user_id FROM progress WHERE id = ?', (progress_id,))
    student_row = c.fetchone()
    if not student_row:
        conn.close()
        flash('Student not found for this progress record.')
        return redirect(url_for('progress', course_id=course_id))
    student_id = student_row[0]
    c.execute('SELECT title FROM courses WHERE id = ?', (course_id,))
    course_title_row = c.fetchone()
    course_title = course_title_row[0] if course_title_row else 'Unknown Course'
    create_notification(student_id, f'Your assignment grade was updated in {course_title}', url_for('progress', course_id=course_id), 'grades')
    conn.commit()
    conn.close()
    flash('Progress updated successfully!')
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
    return redirect(url_for('home'))

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
        questions = request.form['questions']
        correct_answers = request.form.get('correct_answers', '')
        due_date = request.form.get('due_date')
        meeting_link = request.form.get('meeting_link')
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("PRAGMA table_info(assignments)")
        columns = [col[1] for col in c.fetchall()]
        if 'meeting_link' not in columns:
            c.execute('ALTER TABLE assignments ADD COLUMN meeting_link TEXT')
            conn.commit()
        c.execute('INSERT INTO assignments (course_id, name, type, questions, correct_answers, due_date, meeting_link) VALUES (?, ?, ?, ?, ?, ?, ?)',
                  (course_id, name, type_, questions, correct_answers, due_date, meeting_link))
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
    if request.method == 'POST':
        if type_ == 'mcq':
            student_answers = [request.form.get(f'answer_{i}') for i in range(len(questions.split('\n')))]
            correct_list = correct_answers.split('\n')
            ai_grade = grade_mcq(student_answers, correct_list)
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
    # Award points and badges
    add_points(current_user.id, 10)
    award_badge(current_user.id, 'First Submission')
    return render_template('submit_assignment.html', course_id=course_id, assignment_id=assignment_id, name=name, type=type_, questions=questions, correct_answers=correct_answers)

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
        c.execute('SELECT username, role, avatar, display_name, bio, notif_forum, notif_grades, notif_announcements, dark_mode FROM users WHERE username = ?', (username_param,))
        user = c.fetchone()
        is_self = (username_param == current_user.username)
    else:
        c.execute('SELECT username, role, avatar, display_name, bio, notif_forum, notif_grades, notif_announcements, dark_mode FROM users WHERE id = ?', (current_user.id,))
        user = c.fetchone()
        is_self = True
    avatar_url = user[2] if user and user[2] else DEFAULT_AVATAR
    notif_forum = bool(user[5]) if user else True
    notif_grades = bool(user[6]) if user else True
    notif_announcements = bool(user[7]) if user else True
    dark_mode = bool(user[8]) if user else False
    if request.method == 'POST' and is_self:
        file = request.files.get('avatar')
        new_display_name = request.form.get('display_name', '').strip()
        new_bio = request.form.get('bio', '').strip()
        notif_forum_val = 1 if request.form.get('notif_forum') else 0
        notif_grades_val = 1 if request.form.get('notif_grades') else 0
        notif_announcements_val = 1 if request.form.get('notif_announcements') else 0
        dark_mode_val = 1 if request.form.get('dark_mode') else 0
        if file and allowed_avatar(file.filename):
            filename = secure_filename(f"avatar_{current_user.id}.{file.filename.rsplit('.', 1)[1].lower()}")
            filepath = os.path.join('static', 'uploads', filename)
            file.save(filepath)
            c.execute('UPDATE users SET avatar = ? WHERE id = ?', (filepath, current_user.id))
            conn.commit()
            flash('Avatar updated!')
        if new_display_name:
            c.execute('UPDATE users SET display_name = ? WHERE id = ?', (new_display_name, current_user.id))
            conn.commit()
        if new_bio:
            c.execute('UPDATE users SET bio = ? WHERE id = ?', (new_bio, current_user.id))
            conn.commit()
        c.execute('UPDATE users SET notif_forum = ?, notif_grades = ?, notif_announcements = ?, dark_mode = ? WHERE id = ?',
                  (notif_forum_val, notif_grades_val, notif_announcements_val, dark_mode_val, current_user.id))
        conn.commit()
        c.execute('SELECT username, role, avatar, display_name, bio, notif_forum, notif_grades, notif_announcements, dark_mode FROM users WHERE id = ?', (current_user.id,))
        user = c.fetchone()
        avatar_url = user[2] if user and user[2] else DEFAULT_AVATAR
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
    return render_template('profile.html', username=user[0], role=user[1], avatar_url=avatar_url, display_name=user[3] or '', bio=user[4] or '', is_self=is_self, notif_forum=notif_forum, notif_grades=notif_grades, notif_announcements=notif_announcements, dark_mode=dark_mode, api_token=api_token)

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
    # Determine type
    if 'youtube.com' in url or 'youtu.be' in url:
        type_ = 'youtube'
    elif 'docs.google.com' in url:
        type_ = 'gdoc'
    elif url.lower().endswith('.pdf'):
        type_ = 'pdf'
    else:
        type_ = 'link'
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('INSERT INTO resources_external (course_id, title, url, type) VALUES (?, ?, ?, ?)', (course_id, title, url, type_))
    conn.commit()
    conn.close()
    flash('External resource added!')
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
limiter = Limiter(app, key_func=get_remote_address, default_limits=["100 per hour"])

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
        "You are an expert tutor. For the following forum post: "
        "1. Briefly summarize the question or statement in 1-2 lines. "
        "2. Teach or explain the main concept in 2-3 lines, as if to a beginner. "
        "3. Give concise, actionable improvement suggestions in 1-2 lines. "
        "Do not use asterisks or bullet points.\n\nPost:\n"
        f"{content}\n\nOutput (summary, teaching, suggestions; a few lines each, no asterisks):"
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
    if not request.is_json:
        return jsonify({'feedback': 'Request must be JSON.'}), 400
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'feedback': 'No JSON data received.'}), 400
    content = data.get('content', '')
    note_id = data.get('note_id')
    if not content and note_id:
        # Fetch note content from DB
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT content FROM notes WHERE id = ?', (note_id,))
        row = c.fetchone()
        conn.close()
        if row:
            content = row[0]
    if not content or not isinstance(content, str):
        return jsonify({'feedback': 'No valid content provided.'}), 400
    prompt = (
        "You are an expert study assistant. For the following note: "
        "1. Briefly summarize the note in 1-2 lines. "
        "2. Teach or explain the main concept in 2-3 lines, as if to a beginner. "
        "3. Give concise, actionable improvement suggestions in 1-2 lines. "
        "Do not use asterisks or bullet points.\n\nNote:\n"
        f"{content}\n\nOutput (summary, teaching, suggestions; a few lines each, no asterisks):"
    )
    feedback = gemini_feedback(prompt)
    # Remove asterisks and excessive whitespace from the response
    if feedback:
        feedback = feedback.replace('*', '').strip()
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

if __name__ == '__main__':
    socketio.run(app, debug=True)