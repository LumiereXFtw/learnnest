# LearnNest - Advanced Learning Management System

A comprehensive Learning Management System built with Flask, featuring AI-powered feedback, role-based access control, and advanced course management capabilities.

## 🚀 Key Features

### 👥 **User Management & Access Control**
- **Multi-Role System**: Admin, Creator/Instructor, and Student roles
- **Admin Controls**: Full platform oversight with instructor approval and blocking capabilities
- **Instructor Management**: Payment verification, approval workflow, and access control
- **Student Enrollment**: Admin-approved student registration with instructor approval workflow
- **User Directory**: Admin-only access to view and manage all users

### 🎨 **Custom Branding**
- **Custom Logo Upload**: Creators can upload personalized logos that replace the default LearnNest branding
- **Dynamic Branding**: Custom logos appear across all pages with consistent styling
- **Role-Based Branding**: Different logos for different creators/instructors

### 📚 **Course Management**
- **Course Creation**: Comprehensive course creation with multiple file uploads per chapter
- **Chapter Progression**: Sequential access control - students must complete previous chapters
- **Course Outline**: Detailed course structure with learning objectives
- **Resource Management**: Multiple file types support (PDF, video, documents)
- **Live Session Timing**: Scheduled live sessions with visual reminders

### 📝 **Assignment System**
- **Assignment Creation**: Instructors can create assignments with detailed instructions
- **File Upload Support**: Multiple file formats for assignment submissions
- **AI-Powered Feedback**: Google Gemini API integration for intelligent feedback
- **Progress Tracking**: Real-time assignment completion tracking

### 💬 **Communication & Collaboration**
- **Forum Discussions**: Threaded discussions with AI-powered feedback
- **Real-Time Chat**: Live chat functionality for instant communication
- **Notifications**: Real-time notification system for updates and announcements
- **Live Sessions**: Scheduled live sessions with timing display

### 📊 **Analytics & Progress**
- **Student Progress Tracking**: Detailed progress monitoring per course
- **Admin Analytics**: Platform usage insights and user behavior analytics
- **Instructor Analytics**: Course performance and student engagement metrics
- **Leaderboard**: Gamified learning with student rankings

### 🎯 **Learning Features**
- **YouTube Integration**: Video content with automatic transcript extraction
- **AI Feedback**: Intelligent feedback on assignments and forum posts
- **Progress Locking**: Sequential chapter access to ensure proper learning progression
- **Resource Library**: Comprehensive file management system

### 🔒 **Security & Administration**
- **Role-Based Access**: Granular permissions based on user roles
- **Admin Oversight**: Complete platform control with user management
- **Instructor Approval**: Payment verification and approval workflow
- **Student Approval**: Instructor-controlled student enrollment approval
- **Blocking System**: Admin can block instructors, instructors can block students

## 🛠️ Technical Stack

- **Backend**: Flask (Python)
- **Database**: SQLite with optimized concurrency handling
- **AI Integration**: Google Gemini API
- **Real-Time**: Flask-SocketIO
- **Frontend**: Bootstrap 5.3.2, HTML5, CSS3, JavaScript
- **File Handling**: Secure file upload with size validation
- **Authentication**: Flask-Login with password hashing

## 📋 Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables Setup

#### Option A: Automatic Setup (Recommended)
```bash
python setup_env.py
```

#### Option B: Manual Setup
1. Copy the example environment file:
   ```bash
   cp env.example .env
   ```
2. Edit the `.env` file and add your actual API keys:
   ```env
   # Gemini API Configuration
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   
   # Flask Configuration
   SECRET_KEY=your_secure_secret_key_here
   FLASK_ENV=development
   ```

### 3. Getting API Keys

#### Gemini API Key
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the API key and paste it in your `.env` file

#### Generate Secure Secret Key
```python
import secrets
print(secrets.token_hex(32))
```

### 4. Verify Setup
```bash
python test_env.py
```

### 5. Run the Application
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## 👤 Default Users

The system comes with default users for testing:
- **Admin**: Username: `creator1`, Password: `password`
- **Student**: Username: `student1`, Password: `password`

## 🎯 Feature Highlights

### For Administrators
- **Complete Platform Control**: Manage all users, courses, and content
- **Instructor Approval**: Review and approve instructor applications with payment verification
- **User Management**: Block/unblock instructors and manage student enrollments
- **Analytics Dashboard**: Comprehensive platform usage insights
- **Custom Branding**: Upload platform-wide branding elements

### For Instructors/Creators
- **Course Creation**: Create comprehensive courses with multiple resources
- **Student Management**: Approve/reject student enrollments and manage access
- **Assignment System**: Create and grade assignments with AI assistance
- **Live Sessions**: Schedule and conduct live learning sessions
- **Custom Branding**: Upload personalized logos for your courses
- **Progress Tracking**: Monitor student progress and engagement

### For Students
- **Course Enrollment**: Browse and enroll in available courses
- **Sequential Learning**: Progress through chapters in order
- **Assignment Submission**: Submit assignments with file uploads
- **AI Feedback**: Receive intelligent feedback on submissions
- **Live Sessions**: Join scheduled live learning sessions
- **Progress Tracking**: Monitor your learning progress
- **Forum Participation**: Engage in course discussions

## 🔧 Advanced Features

### Database Optimization
- **Concurrency Handling**: Optimized database operations with WAL mode
- **Retry Mechanisms**: Automatic retry for database operations
- **Connection Pooling**: Efficient database connection management

### File Management
- **Multiple File Types**: Support for PDF, video, document uploads
- **Size Validation**: Configurable file size limits
- **Secure Storage**: Safe file handling with proper validation

### Real-Time Features
- **Live Chat**: Real-time communication between users
- **Notifications**: Instant updates for important events
- **Progress Updates**: Real-time progress tracking

## 🚀 Recent Enhancements

### Custom Logo System
- **Creator Branding**: Upload custom logos for personalized branding
- **Dynamic Display**: Logos appear across all pages with consistent styling
- **Role-Based Access**: Only creators can upload and manage logos

### Admin Controls
- **Instructor Management**: Complete control over instructor approval and access
- **Student Management**: Instructor-level control over student enrollments
- **User Directory**: Admin-only access to comprehensive user management

### Enhanced UI/UX
- **Responsive Design**: Mobile-optimized interface
- **Modern Styling**: Bootstrap 5.3.2 with custom CSS
- **Intuitive Navigation**: User-friendly interface design

## 📚 API Documentation

Visit `/api/docs` for comprehensive API documentation when the application is running.

## 🔒 Security Features

- **Environment Variable Protection**: Sensitive data stored in `.env` files
- **Password Hashing**: Secure password storage using Werkzeug
- **File Upload Security**: Validated file uploads with size and type restrictions
- **Role-Based Access**: Granular permissions based on user roles
- **Session Management**: Secure session handling with Flask-Login

## 🐛 Troubleshooting

### Common Issues
- **Environment Variables**: Ensure `.env` file is in root directory
- **API Keys**: Verify Gemini API key is correct and active
- **Database Issues**: Check for file permissions and disk space
- **File Uploads**: Verify file size limits and supported formats

### Performance Optimization
- **Database**: Optimized with WAL mode and connection pooling
- **File Handling**: Efficient file storage and retrieval
- **Real-Time**: Optimized SocketIO implementation

## 🤝 Contributing

This is a comprehensive Learning Management System designed for educational institutions and online learning platforms. The system prioritizes:

- **Minimal Impact**: New features are added with minimal disruption to existing functionality
- **Scalability**: Designed to handle multiple users and courses
- **User Experience**: Intuitive interface for all user roles
- **Security**: Robust security measures for data protection

## 📄 License

This project is designed for educational and commercial use in learning management systems.

---

**LearnNest** - Empowering Education Through Technology #   l e a r n n e s t _ e n h a n c e d  
 