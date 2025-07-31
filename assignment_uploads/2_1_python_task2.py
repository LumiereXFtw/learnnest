import sqlite3
from werkzeug.security import generate_password_hash

# Connect to SQLite database
conn = sqlite3.connect('database.db')
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS courses
             (id INTEGER PRIMARY KEY, title TEXT, creator_id INTEGER, description TEXT)''')
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

# Insert sample users
users = [
    (1, 'creator1', generate_password_hash('password123'), 'creator'),
    (2, 'student1', generate_password_hash('password123'), 'student'),
    (3, 'student2', generate_password_hash('password123'), 'student')
]
c.executemany('INSERT OR REPLACE INTO users (id, username, password, role) VALUES (?, ?, ?, ?)', users)

# Insert sample courses
courses = [
    (1, 'Python Programming', 1, 'Learn Python basics'),
    (2, 'Web Development', 1, 'Learn HTML, CSS, and JavaScript')
]
c.executemany('INSERT OR REPLACE INTO courses (id, title, creator_id, description) VALUES (?, ?, ?, ?)', courses)

# Insert sample course files
course_files = [
    (1, 1, 'python_intro.pdf', 'application/pdf'),
    (2, 1, 'python_video.mp4', 'video/mp4'),
    (3, 2, 'html_guide.pdf', 'application/pdf')
]
c.executemany('INSERT OR REPLACE INTO course_files (id, course_id, filename, file_type) VALUES (?, ?, ?, ?)', course_files)

# Insert sample enrollments
enrollments = [
    (1, 2, 1, 'ENROLL001'),
    (2, 3, 1, 'ENROLL002'),
    (3, 2, 2, 'ENROLL003'),
    (4, 3, 2, 'ENROLL004')
]
c.executemany('INSERT OR REPLACE INTO enrollments (id, user_id, course_id, enrollment_number) VALUES (?, ?, ?, ?)', enrollments)

# Insert sample threads
threads = [
    (1, 1, 'Python Syntax Questions', 2),
    (2, 1, 'Debugging Tips', 3),
    (3, 2, 'CSS Layout Issues', 2)
]
c.executemany('INSERT OR REPLACE INTO threads (id, course_id, title, creator_id) VALUES (?, ?, ?, ?)', threads)

# Insert sample posts
posts = [
    (1, 1, 2, 'ENROLL001', 'How do I use list comprehensions?', '2023-10-01 10:00:00'),
    (2, 1, 3, 'ENROLL002', 'Check out this debugging trick!', '2023-10-01 11:00:00'),
    (3, 2, 2, 'ENROLL001', 'Use a debugger like pdb.', '2023-10-02 09:00:00')
]
c.executemany('INSERT OR REPLACE INTO posts (id, thread_id, user_id, enrollment_number, content, created_at) VALUES (?, ?, ?, ?, ?, ?)', posts)

# Insert sample progress
progress = [
    (1, 2, 1, 'Assignment 1', 'submitted', 80, 'assignment_uploads/2_1_Assignment_1.pdf', None),
    (2, 3, 1, 'Assignment 1', 'submitted', 90, 'assignment_uploads/3_1_Assignment_1.py', 60),
    (3, 2, 2, 'Assignment 1', 'submitted', 85, 'assignment_uploads/2_2_Assignment_1.txt', 40)
]
c.executemany('INSERT OR REPLACE INTO progress (id, user_id, course_id, assignment_name, status, grade, file_path, ai_grade) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', progress)

# Commit and close
conn.commit()
conn.close()