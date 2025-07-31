import sqlite3
from werkzeug.security import generate_password_hash
import os

# Create database and tables
conn = sqlite3.connect('database.db')
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, avatar TEXT, display_name TEXT, bio TEXT, notif_forum INTEGER DEFAULT 1, notif_grades INTEGER DEFAULT 1, notif_announcements INTEGER DEFAULT 1, dark_mode INTEGER DEFAULT 0, badges TEXT, points INTEGER DEFAULT 0, api_token TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS courses
             (id INTEGER PRIMARY KEY, title TEXT, creator_id INTEGER, description TEXT, reference_file_path TEXT, meeting_link TEXT, outline TEXT, objectives TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, live_session_start TEXT, live_session_end TEXT, live_days TEXT)''')
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
c.execute('''CREATE TABLE IF NOT EXISTS resources_external (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        title TEXT,
        url TEXT,
        type TEXT,
        transcript TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
c.execute('''CREATE TABLE IF NOT EXISTS lti_tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER,
    title TEXT,
    launch_url TEXT,
    consumer_key TEXT,
    consumer_secret TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
c.execute('''CREATE TABLE IF NOT EXISTS webhooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER,
    url TEXT,
    event_type TEXT,
    last_status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
c.execute('''CREATE TABLE IF NOT EXISTS badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    badge TEXT,
    awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

c.execute("PRAGMA table_info(users)")
columns = [col[1] for col in c.fetchall()]
if 'points' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0')
if 'is_blocked' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0')
if 'created_at' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN created_at TEXT')
    c.execute('UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')
if 'is_approved' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 0')
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
if 'display_name' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN display_name TEXT')
if 'bio' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN bio TEXT')
if 'notif_forum' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN notif_forum INTEGER DEFAULT 1')
if 'notif_grades' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN notif_grades INTEGER DEFAULT 1')
if 'notif_announcements' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN notif_announcements INTEGER DEFAULT 1')
if 'dark_mode' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN dark_mode INTEGER DEFAULT 0')
if 'badges' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN badges TEXT')
if 'api_token' not in columns:
    c.execute('ALTER TABLE users ADD COLUMN api_token TEXT')

c.execute("PRAGMA table_info(posts)")
post_columns = [col[1] for col in c.fetchall()]
if 'ext_url' not in post_columns:
    c.execute('ALTER TABLE posts ADD COLUMN ext_url TEXT')
if 'ext_type' not in post_columns:
    c.execute('ALTER TABLE posts ADD COLUMN ext_type TEXT')

c.execute("PRAGMA table_info(threads)")
thread_columns = [col[1] for col in c.fetchall()]
if 'ext_url' not in thread_columns:
    c.execute('ALTER TABLE threads ADD COLUMN ext_url TEXT')
if 'ext_type' not in thread_columns:
    c.execute('ALTER TABLE threads ADD COLUMN ext_type TEXT')

c.execute("PRAGMA table_info(courses)")
course_columns = [col[1] for col in c.fetchall()]
if 'meeting_link' not in course_columns:
    c.execute('ALTER TABLE courses ADD COLUMN meeting_link TEXT')
if 'outline' not in course_columns:
    c.execute('ALTER TABLE courses ADD COLUMN outline TEXT')
if 'objectives' not in course_columns:
    c.execute('ALTER TABLE courses ADD COLUMN objectives TEXT')
if 'created_at' not in course_columns:
    c.execute('ALTER TABLE courses ADD COLUMN created_at TEXT')
    c.execute('UPDATE courses SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')

c.execute("PRAGMA table_info(enrollments)")
enrollment_columns = [col[1] for col in c.fetchall()]
if 'enrollment_date' not in enrollment_columns:
    c.execute('ALTER TABLE enrollments ADD COLUMN enrollment_date TEXT')
    c.execute('UPDATE enrollments SET enrollment_date = CURRENT_TIMESTAMP WHERE enrollment_date IS NULL')

c.execute("PRAGMA table_info(assignments)")
assignment_columns = [col[1] for col in c.fetchall()]
if 'meeting_link' not in assignment_columns:
    c.execute('ALTER TABLE assignments ADD COLUMN meeting_link TEXT')
if 'created_at' not in assignment_columns:
    c.execute('ALTER TABLE assignments ADD COLUMN created_at TEXT')
    c.execute('UPDATE assignments SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')

c.execute("PRAGMA table_info(progress)")
progress_columns = [col[1] for col in c.fetchall()]
if 'created_at' not in progress_columns:
    c.execute('ALTER TABLE progress ADD COLUMN created_at TEXT')
    c.execute('UPDATE progress SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')

c.execute("PRAGMA table_info(course_files)")
course_file_columns = [col[1] for col in c.fetchall()]
if 'subtitle_path' not in course_file_columns:
    c.execute('ALTER TABLE course_files ADD COLUMN subtitle_path TEXT')

# Insert sample data
c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
          ('creator1', generate_password_hash('password123'), 'creator'))
c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
          ('student1', generate_password_hash('password123'), 'student'))
c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
          ('student2', generate_password_hash('password123'), 'student'))

c.execute("INSERT OR IGNORE INTO courses (title, creator_id, description, reference_file_path) VALUES (?, ?, ?, ?)",
          ('Python Programming', 1, 'Learn Python basics and advanced concepts.', 'uploads/python_reference.py'))
c.execute("INSERT OR IGNORE INTO courses (title, creator_id, description, reference_file_path) VALUES (?, ?, ?, ?)",
          ('Web Development', 1, 'Build modern web applications.', None))

c.execute("INSERT OR IGNORE INTO enrollments (user_id, course_id, enrollment_number) VALUES (?, ?, ?)",
          (2, 1, 'ENROLL001'))
c.execute("INSERT OR IGNORE INTO enrollments (user_id, course_id, enrollment_number) VALUES (?, ?, ?)",
          (3, 1, 'ENROLL002'))
c.execute("INSERT OR IGNORE INTO enrollments (user_id, course_id, enrollment_number) VALUES (?, ?, ?)",
          (2, 2, 'ENROLL003'))

c.execute("INSERT OR IGNORE INTO course_files (course_id, filename, file_type) VALUES (?, ?, ?)",
          (1, 'python_intro.pdf', 'application/pdf'))
c.execute("INSERT OR IGNORE INTO course_files (course_id, filename, file_type) VALUES (?, ?, ?)",
          (1, 'python_video.mp4', 'video/mp4'))
c.execute("INSERT OR IGNORE INTO course_files (course_id, filename, file_type) VALUES (?, ?, ?)",
          (2, 'html_guide.pdf', 'application/pdf'))

c.execute("INSERT OR IGNORE INTO threads (course_id, title, creator_id) VALUES (?, ?, ?)",
          (1, 'Python Syntax Questions', 2))
c.execute("INSERT OR IGNORE INTO posts (thread_id, user_id, enrollment_number, content) VALUES (?, ?, ?, ?)",
          (1, 2, 'ENROLL001', 'Can someone explain list comprehensions?'))
c.execute("INSERT OR IGNORE INTO posts (thread_id, user_id, enrollment_number, content) VALUES (?, ?, ?, ?)",
          (1, 3, 'ENROLL002', 'Check the official Python docs for examples!'))

c.execute("INSERT OR IGNORE INTO progress (user_id, course_id, assignment_name, status, grade, file_path, ai_grade) VALUES (?, ?, ?, ?, ?, ?, ?)",
          (2, 1, 'Python Quiz 1', 'submitted', None, 'assignment_uploads/2_1_Python_Quiz_1.pdf', None))
c.execute("INSERT OR IGNORE INTO progress (user_id, course_id, assignment_name, status, grade, file_path, ai_grade) VALUES (?, ?, ?, ?, ?, ?, ?)",
          (3, 1, 'Python Quiz 1', 'completed', 85, 'assignment_uploads/3_1_Python_Quiz_1.py', 80))
c.execute("INSERT OR IGNORE INTO progress (user_id, course_id, assignment_name, status, grade, file_path, ai_grade) VALUES (?, ?, ?, ?, ?, ?, ?)",
          (2, 2, 'HTML Assignment', 'incomplete', None, None, None))

c.execute("INSERT OR IGNORE INTO notes (user_id, course_id, content) VALUES (?, ?, ?)",
          (2, 1, 'Python list comprehensions: [x*2 for x in range(10)] creates a list of doubled values.'))
c.execute("INSERT OR IGNORE INTO notes (user_id, course_id, content) VALUES (?, ?, ?)",
          (3, 1, 'Remember to use virtual environments for Python projects.'))

# Create uploads and assignment uploads folders
if not os.path.exists('uploads'):
    os.makedirs('uploads')
if not os.path.exists('assignment_uploads'):
    os.makedirs('assignment_uploads')

conn.commit()
conn.close()

def add_is_approved_column():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if 'is_approved' not in columns:
        c.execute('ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 0')
        conn.commit()
    conn.close()

add_is_approved_column()

def create_default_admin():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username='admin'")
    if not c.fetchone():
        from werkzeug.security import generate_password_hash
        pw = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, password, role, is_approved) VALUES (?, ?, ?, 1)", ('admin', pw, 'admin'))
        conn.commit()
    conn.close()

create_default_admin()