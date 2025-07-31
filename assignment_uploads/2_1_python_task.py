import sqlite3
from werkzeug.security import generate_password_hash
import os

# Create database and tables
conn = sqlite3.connect('database.db')
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS courses
             (id INTEGER PRIMARY KEY, title TEXT, creator_id INTEGER, description TEXT, reference_file_path TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS course_files
             (id INTEGER PRIMARY KEY, course_id INTEGER, filename TEXT, file_type TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS enrollments
             (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER, enrollment_number TEXT UNIQUE)''')
c.execute('''CREATE TABLE IF NOT EXISTS threads
             (id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT, creator_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS posts
             (id INTEGER PRIMARY KEY, thread_id INTEGER, user_id INTEGER, enrollment_number TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS progress
             (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER, assignment_name TEXT, status TEXT, grade INTEGER, file_path TEXT, ai_grade INTEGER)''')

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

# Create uploads and assignment uploads folders
if not os.path.exists('uploads'):
    os.makedirs('uploads')
if not os.path.exists('assignment_uploads'):
    os.makedirs('assignment_uploads')

conn.commit()
conn.close()