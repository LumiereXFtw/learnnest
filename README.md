# LearnNest - Advanced Learning Management System

A comprehensive Learning Management System (LMS) built with Flask, featuring AI-powered feedback, role-based access control, and advanced course management capabilities.

## 🚀 Key Features

### 👥 User Management & Access Control
- **Multi-Role System**: Supports Admin, Instructor, and Student roles.
- **Admin Controls**: Full platform oversight, including instructor approval and user blocking.
- **Instructor Management**: Payment verification, approval workflow, and access control.
- **Student Enrollment**: Admin and instructor-approved registration process.
- **User Directory**: Admin-only access to view and manage all users.

### 🎨 Custom Branding
- **Custom Logo Upload**: Instructors can upload personalized logos to replace default branding.
- **Dynamic Branding**: Logos appear consistently across all pages.
- **Role-Based Branding**: Unique logos for different instructors.

### 📚 Course Management
- **Course Creation**: Build courses with multiple file uploads per chapter.
- **Chapter Progression**: Sequential access ensures students complete chapters in order.
- **Course Outline**: Detailed structure with clear learning objectives.
- **Resource Management**: Supports multiple file types (PDF, video, documents).
- **Live Session Timing**: Scheduled live sessions with visual reminders.

### 📝 Assignment System
- **Assignment Creation**: Instructors can create detailed assignments.
- **File Upload Support**: Multiple file formats for submissions.
- **AI-Powered Feedback**: Integrated with Google Gemini API for intelligent feedback.
- **Progress Tracking**: Real-time tracking of assignment completion.

### 💬 Communication & Collaboration
- **Forum Discussions**: Threaded discussions with AI-powered feedback.
- **Real-Time Chat**: Instant communication via live chat.
- **Notifications**: Real-time updates for events and announcements.
- **Live Sessions**: Scheduled sessions with clear timing display.

### 📊 Analytics & Progress
- **Student Progress Tracking**: Detailed monitoring per course.
- **Admin Analytics**: Insights into platform usage and user behavior.
- **Instructor Analytics**: Metrics on course performance and student engagement.
- **Leaderboard**: Gamified rankings to motivate students.

### 🎯 Learning Features
- **YouTube Integration**: Video content with automatic transcript extraction.
- **AI Feedback**: Intelligent feedback on assignments and forum posts.
- **Progress Locking**: Ensures sequential chapter access for structured learning.
- **Resource Library**: Comprehensive file management system.

### 🔒 Security & Administration
- **Role-Based Access**: Granular permissions for each user role.
- **Admin Oversight**: Full control over users, courses, and content.
- **Instructor Approval**: Payment verification and approval workflow.
- **Student Approval**: Instructor-managed enrollment approvals.
- **Blocking System**: Admins can block instructors; instructors can block students.

## 🛠️ Technical Stack
- **Backend**: Flask (Python)
- **Database**: SQLite with optimized concurrency handling
- **AI Integration**: Google Gemini API
- **Real-Time**: Flask-SocketIO
- **Frontend**: Bootstrap 5.3.2, HTML5, CSS3, JavaScript
- **File Handling**: Secure uploads with size validation
- **Authentication**: Flask-Login with password hashing

## 📋 Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
