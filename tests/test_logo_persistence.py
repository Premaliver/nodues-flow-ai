import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from app import create_app
from models import db
from models.user import User
from models.system_setting import SystemSetting

def test_logo_persistence():
    app = create_app()
    with app.test_client() as client:
        # 1. Test unauthenticated login page
        login_page = client.get('/auth/login')
        login_html = login_page.data.decode('utf-8')
        assert 'logo_test-university_1788706574.png' in login_html, 'Login page missing custom logo!'
        print('[PASS]: /auth/login page renders official custom logo.')

        # 2. Test login as premk with Premkumar@8360292
        resp = client.post('/auth/login', json={'role': 'super_admin', 'username': 'premk', 'password': 'Premkumar@8360292'})
        assert resp.status_code == 200, f'Login failed: {resp.status_code}'
        with client.session_transaction() as sess:
            sess_logo = sess.get('university_logo')
            assert sess_logo == '/static/uploads/logos/logo_test-university_1788706574.png', f'Session logo wrong: {sess_logo}'
            assert sess.get('university_name') == 'test university'
        print('[PASS]: Login as premk set correct university session state and logo.')

        # 3. Test superadmin dashboard rendering
        dash_resp = client.get('/superadmin/dashboard')
        assert dash_resp.status_code == 200
        dash_html = dash_resp.data.decode('utf-8')
        assert 'logo_test-university_1788706574.png' in dash_html, 'Dashboard missing custom logo!'
        print('[PASS]: /superadmin/dashboard renders official custom logo.')

        # 4. Test branding update via API
        # 4. Test branding update via API
        test_new_logo = '/static/uploads/logos/logo_test-university_1788706574.png'
        brand_resp = client.post('/university/api/branding', json={
            'logo_url': test_new_logo,
            'primary_color': '#4338ca',
            'accent_color': '#6366f1',
            'banner_text': 'Clearance window open'
        })
        assert brand_resp.status_code == 200
        print('[PASS]: Branding API updated successfully.')

        # 4b. Test direct file upload via /university/api/branding/upload-logo
        import io
        fake_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        upload_data = {
            'file': (io.BytesIO(fake_png), 'test_univ_logo.png')
        }
        upload_resp = client.post('/university/api/branding/upload-logo', data=upload_data, content_type='multipart/form-data')
        assert upload_resp.status_code == 200, f'Upload failed: {upload_resp.data}'
        uploaded_logo_url = upload_resp.json.get('logo_url')
        assert uploaded_logo_url and uploaded_logo_url.startswith('/static/uploads/logos/'), f'Invalid uploaded logo url: {uploaded_logo_url}'
        print(f'[PASS]: Direct logo file uploaded successfully -> {uploaded_logo_url}')

        # 5. Test logout
        logout_resp = client.get('/auth/logout')
        assert logout_resp.status_code in (302, 200)
        with client.session_transaction() as sess:
            assert sess.get('user_role') is None
        print('[PASS]: Logged out cleanly.')

        # 6. Test RELOGIN after file upload
        relogin_resp = client.post('/auth/login', json={'role': 'super_admin', 'username': 'premk', 'password': 'Premkumar@8360292'})
        assert relogin_resp.status_code == 200
        with client.session_transaction() as sess:
            re_logo = sess.get('university_logo')
            assert re_logo == uploaded_logo_url, f'Relogin session logo lost: expected {uploaded_logo_url}, got {re_logo}'
        
        re_dash_resp = client.get('/superadmin/dashboard')
        assert re_dash_resp.status_code == 200
        re_dash_html = re_dash_resp.data.decode('utf-8')
        assert uploaded_logo_url in re_dash_html, 'Relogin dashboard missing uploaded logo!'
        print('[PASS]: RELOGIN RETAINED NEWLY UPLOADED LOGO PERMANENTLY IN DASHBOARD & SESSION!')


        # 7. Also test login as department staff (e.g. admin@test-university.edu)
        dept_resp = client.get('/auth/logout')
        staff_login = client.post('/auth/login', json={'role': 'super_admin', 'email': 'admin@test-university.edu', 'password': 'Prem@20044'})
        if staff_login.status_code == 200:
            with client.session_transaction() as sess:
                assert sess.get('university_logo') == test_new_logo
            print('[PASS]: Department/Tenant admin login also retains official university logo.')

if __name__ == '__main__':
    test_logo_persistence()
