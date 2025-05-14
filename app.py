import os
import cv2
import csv
import base64
from io import BytesIO
from PIL import Image , ImageDraw,ImageFont
import face_recognition
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash ,session
from datetime import datetime




app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 60 * 1024 * 1024 
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def recognize_face(upload_path):
    try:
        uploaded_image = face_recognition.load_image_file(upload_path)
        uploaded_encoding = face_recognition.face_encodings(uploaded_image)

        if not uploaded_encoding:
            return None  

        uploaded_encoding = uploaded_encoding[0]

        with open('encodings.csv', 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                name = row[0]
                known_encoding = list(map(float, row[1:]))  
                
                match = face_recognition.compare_faces([known_encoding], uploaded_encoding)[0]
                if match:
                    return name
    except Exception as e:
        print("Error recognizing face:", e)

    return None  


@app.before_request
def require_login():
    allowed_routes = ['login', 'static', 'student_dashboard']
    if 'faculty_logged_in' not in session and request.endpoint not in allowed_routes:
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['faculty_logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('faculty_logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        files = request.files.getlist('images')

        if not files:
            flash("No images uploaded.")
            return redirect(request.url)

        encodings_to_save = []

        for file in files:
            image = face_recognition.load_image_file(file)
            encodings = face_recognition.face_encodings(image)

            if encodings:
                for encoding in encodings:
                    encodings_to_save.append((name, encoding))
            else:
                flash(f"Warning: No face detected in one image.")

        if not encodings_to_save:
            flash("Registration failed: No faces found in any image.")
            return redirect(request.url)

        with open('encodings.csv', 'a', newline='') as f:
            writer = csv.writer(f)
            for name, encoding in encodings_to_save:
                row = [name] + list(encoding)
                writer.writerow(row)

        flash(f"{name} registered successfully with {len(encodings_to_save)} angle(s).")
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/student-dashboard')
def student_dashboard():
    attendance_records = []
    if os.path.exists('attendance.csv'):
        with open('attendance.csv', 'r') as f:
            reader = csv.reader(f)
            next(reader)  
            attendance_records = list(reader)
    return render_template('student_dashboard.html', attendance=attendance_records)



@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    if request.method == 'POST':
        image_data = request.form.get('image_data')
        if not image_data:
            flash('No image data provided')
            return redirect(request.url)

        header, encoded = image_data.split(',', 1)
        image_bytes = base64.b64decode(encoded)
        image = Image.open(BytesIO(image_bytes)).convert("RGB")

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'captured.png')
        image.save(filepath)

        captured_image = face_recognition.load_image_file(filepath)
        captured_encodings = face_recognition.face_encodings(captured_image)
        face_locations = face_recognition.face_locations(captured_image)

        if not captured_encodings:
            flash('No face detected.')
            return redirect(url_for('index'))

        with open('encodings.csv', 'r') as f:
            reader = csv.reader(f)
            known_encodings = [(row[0], list(map(float, row[1:]))) for row in reader]

        recognized_names = []

        pil_image = Image.fromarray(captured_image)
        draw = ImageDraw.Draw(pil_image)
        font = ImageFont.load_default()

        for i, (face_encoding, face_location) in enumerate(zip(captured_encodings, face_locations)):
            for name, known_encoding in known_encodings:
                match = face_recognition.compare_faces([known_encoding], face_encoding)[0]
                if match:
                    recognized_names.append(name)

                    now = datetime.now()
                    date = now.strftime("%Y-%m-%d")
                    time = now.strftime("%H:%M:%S")

                    already_marked = False
                    if os.path.exists('attendance.csv'):
                        with open('attendance.csv', 'r') as f:
                            reader = csv.reader(f)
                            next(reader, None)
                            for row in reader:
                                if row[0] == name and row[1] == date:
                                    already_marked = True
                                    break

                    if not already_marked:
                        with open('attendance.csv', 'a', newline='') as f:
                            writer = csv.writer(f)
                            if os.stat('attendance.csv').st_size == 0:
                                writer.writerow(['Name', 'Date', 'Time'])
                            writer.writerow([name, date, time])
                        flash(f"Attendance marked for: {name}")
                    else:
                        flash(f"{name} has already marked attendance today.")

                    top, right, bottom, left = face_location
                    draw.rectangle(((left, top), (right, bottom)), outline="green", width=3)
                    draw.text((left, bottom + 5), name, fill="green", font=font)
                    break

        annotated_path = os.path.join(app.config['UPLOAD_FOLDER'], 'annotated.png')
        pil_image.save(annotated_path)

        if not recognized_names:
            flash("No known faces recognized.")

        return redirect(url_for('index'))

    return render_template('attendance.html')





@app.route('/dashboard')
def dashboard():
    try:
        if os.path.exists('attendance.csv') and os.path.getsize('attendance.csv') > 0:
            attendance_df = pd.read_csv('attendance.csv')
            attendance_data = attendance_df.to_dict(orient='records')
        else:
            attendance_data = []
    except pd.errors.EmptyDataError:
        attendance_data = []

    return render_template(
        "dashboard.html",
        attendance=attendance_data,
        current_year=datetime.now().year
    )


if __name__ == '__main__':
    app.run(debug=True)
