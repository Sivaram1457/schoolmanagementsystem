import requests

url='http://127.0.0.1:8000/auth/login'
for user in [('student@school.com','password123'),('admin@school.com','password123')]:
    r=requests.post(url,json={'email':user[0],'password':user[1]})
    print('==',user)
    print(r.status_code)
    try:
        print(r.json())
    except Exception:
        print('body:', r.text)
