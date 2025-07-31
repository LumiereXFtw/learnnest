# Learning Management System

A comprehensive Learning Management System built with Flask, featuring AI-powered feedback using Google's Gemini API.

## Features

- User authentication and role-based access control
- Course creation and management
- Assignment submission and AI-powered grading
- Forum discussions with AI feedback
- Real-time chat functionality
- Progress tracking and analytics
- File upload and management
- YouTube video integration with transcripts

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables Setup

#### Option A: Automatic Setup (Recommended)
```bash
python setup_env.py
```
This will create a `.env` file from the template and guide you through the setup process.

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

#### Getting a Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the API key and paste it in your `.env` file

#### Generating a Secure Secret Key

You can generate a secure secret key using Python:
```python
import secrets
print(secrets.token_hex(32))
```

### 3. Verify Setup

Run the test script to verify your environment variables are set up correctly:
```bash
python test_env.py
```

### 4. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Security Notes

- The `.env` file is already included in `.gitignore` to prevent sensitive data from being committed to version control
- Never commit your actual API keys to the repository
- Use the `env.example` file as a template for setting up your environment variables
- The application will use fallback values if environment variables are not set (for development only)

## Default Users

The system comes with some default users for testing:
- Username: `creator1`, Password: `password` (Admin/Creator role)
- Username: `student1`, Password: `password` (Student role)

## API Documentation

Visit `/api/docs` for API documentation when the application is running.

## Troubleshooting

### Environment Variables Not Loading
- Make sure you have `python-dotenv` installed: `pip install python-dotenv`
- Verify your `.env` file is in the root directory
- Check that the variable names match exactly (case-sensitive)

### Gemini API Issues
- Verify your API key is correct and active
- Check your API usage limits in Google AI Studio
- Ensure you have internet connectivity for API calls 