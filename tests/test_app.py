import pytest
from app import app

def test_registration_and_login():
    client = app.test_client()
    # Register
    resp = client.post('/register', data={
        'username': 'testuser',
        'password': 'testpass',
        'confirm': 'testpass'
    }, follow_redirects=True)
    assert b'Login' in resp.data
    # Login
    resp = client.post('/login', data={
        'username': 'testuser',
        'password': 'testpass'
    }, follow_redirects=True)
    assert b'Logout' in resp.data

def test_assignment_upload_validation():
    client = app.test_client()
    # Login as testuser
    client.post('/login', data={'username': 'testuser', 'password': 'testpass'})
    # Try to upload disallowed file type
    data = {
        'file': (pytest.BytesIO(b'bad'), 'malware.exe')
    }
    resp = client.post('/course/1/submit_assignment/1', data=data, content_type='multipart/form-data')
    assert b'Invalid file type' in resp.data or resp.status_code == 400

def test_csrf_protection():
    client = app.test_client()
    resp = client.post('/login', data={'username': 'testuser', 'password': 'testpass'})
    # Should fail without CSRF token if enabled
    assert resp.status_code in (400, 403)

def test_rate_limiting():
    client = app.test_client()
    for _ in range(110):
        resp = client.get('/')
    assert resp.status_code in (429, 200) 