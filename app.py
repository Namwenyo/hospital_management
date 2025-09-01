from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, Patient, Doctor, Appointment, User
from flask_migrate import Migrate
from datetime import datetime, date, timedelta
from math import ceil

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "Villo"

# Initialize database with app
db.init_app(app)
migrate = Migrate(app, db)


login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Index (Dashboard)
@app.route('/')
@login_required
def index():
    patients = Patient.query.all()
    doctors = Doctor.query.all()
    appointments = Appointment.query.all()
    return render_template('index.html',
                           patients=patients,
                           doctors=doctors,
                           appointments=appointments)

@app.route('/patients')
@login_required
def patients():
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Show 10 patients per page
    
    # Build query based on search
    if search_query:
        query = Patient.query.filter(
            (Patient.first_name.ilike(f'%{search_query}%')) | 
            (Patient.surname.ilike(f'%{search_query}%'))
        )
    else:
        query = Patient.query
    
    # Get paginated results
    patients = query.order_by(Patient.date_created.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Calculate total pages
    total_pages = ceil(query.count() / per_page)
    
    # Pass today's date to the template for setting max date in the form
    date_today = date.today().strftime('%Y-%m-%d')
    
    return render_template('patients.html', 
                         patients=patients.items, 
                         search_query=search_query, 
                         date_today=date_today,
                         page=page,
                         total_pages=total_pages)

@app.route('/add_patient', methods=['POST'])
def add_patient():
    if request.method == 'POST':
        first_name = request.form['first_name']
        surname = request.form['surname']
        date_of_birth = datetime.strptime(request.form['date_of_birth'], '%Y-%m-%d').date()
        gender = request.form['gender']
        phone = request.form.get('phone', '')
        
        new_patient = Patient(
            first_name=first_name, 
            surname=surname, 
            date_of_birth=date_of_birth,
            gender=gender,
            phone=phone
        )
        
        db.session.add(new_patient)
        db.session.commit()
        flash('Patient added successfully!', 'success')
        
        return redirect(url_for('patients'))

@app.route('/edit_patient/<int:patient_id>', methods=['POST'])
def edit_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    if request.method == 'POST':
        patient.first_name = request.form['first_name']
        patient.surname = request.form['surname']
        patient.date_of_birth = datetime.strptime(request.form['date_of_birth'], '%Y-%m-%d').date()
        patient.gender = request.form['gender']
        patient.phone = request.form.get('phone', '')
        
        db.session.commit()
        flash('Patient updated successfully!', 'success')
        
        return redirect(url_for('patients'))
    
@app.route('/delete_patient/<int:patient_id>')
def delete_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Check if patient has appointments
    if patient.appointments:
        flash('Cannot delete patient with existing appointments!', 'danger')
        return redirect(url_for('patients'))
    
    db.session.delete(patient)
    db.session.commit()
    flash('Patient deleted successfully!', 'success')
    
    return redirect(url_for('patients'))    

# Add Appointment
@app.route('/appointments', methods=['GET', 'POST'])
@login_required
def appointments():
    # Handle appointment creation
    if request.method == 'POST':
        date_str = request.form['date']  
        start_time_str = request.form['start_time']  
        end_time_str = request.form['end_time']  
        diagnosis = request.form['diagnosis']
        patient_id = request.form['patient_id']
        doctor_id = request.form['doctor_id']

        # Validate date is not more than a year ahead
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        max_allowed_date = date.today() + timedelta(days=365)
        
        if date_obj > max_allowed_date:
            flash('Cannot book appointments more than one year in advance!', 'danger')
            return redirect(url_for('appointments'))
        
        # Convert time strings to time objects
        start_time_obj = datetime.strptime(start_time_str, '%H:%M').time()
        end_time_obj = datetime.strptime(end_time_str, '%H:%M').time()
        
        # Validate that end time is after start time
        if end_time_obj <= start_time_obj:
            flash('End time must be after start time!', 'danger')
            return redirect(url_for('appointments'))
        
        # Check for time conflicts
        existing_appointment = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.date == date_obj,
            (
                (Appointment.start_time <= start_time_obj) & (Appointment.end_time > start_time_obj) |
                (Appointment.start_time < end_time_obj) & (Appointment.end_time >= end_time_obj) |
                (Appointment.start_time >= start_time_obj) & (Appointment.end_time <= end_time_obj)
            )
        ).first()
        
        if existing_appointment:
            flash('This time slot conflicts with an existing appointment!', 'danger')
            return redirect(url_for('appointments'))

        new_appointment = Appointment(
            date=date_obj,
            start_time=start_time_obj,
            end_time=end_time_obj,
            diagnosis=diagnosis,
            patient_id=patient_id,
            doctor_id=doctor_id
        )
        db.session.add(new_appointment)
        db.session.commit()
        flash("Appointment scheduled successfully!", 'success')
        return redirect(url_for('appointments'))

    # Handle GET request - show appointments with pagination
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Build query based on search
    if search_query:
        query = Appointment.query.join(Patient).join(Doctor).filter(
            (Patient.first_name.ilike(f'%{search_query}%')) | 
            (Patient.surname.ilike(f'%{search_query}%')) |
            (Doctor.first_name.ilike(f'%{search_query}%')) |
            (Doctor.surname.ilike(f'%{search_query}%'))
        )
    else:
        query = Appointment.query
    
    # Get paginated results
    appointments_pagination = query.order_by(Appointment.date.desc(), Appointment.start_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Calculate total pages
    total_pages = ceil(query.count() / per_page)
    
    patients = Patient.query.all()
    doctors = Doctor.query.all()
    
    # Get booked appointments for the next 7 days to show availability
    today = date.today()
    seven_days_later = today + timedelta(days=7)
    booked_appointments = Appointment.query.filter(
        Appointment.date >= today,
        Appointment.date <= seven_days_later
    ).all()
    
    # Create a structure of booked time slots by doctor and date
    booked_slots = {}
    for appt in booked_appointments:
        key = f"{appt.doctor_id}_{appt.date}"
        if key not in booked_slots:
            booked_slots[key] = []
        # Store both start and end times
        booked_slots[key].append({
            'start': appt.start_time.strftime('%H:%M'),
            'end': appt.end_time.strftime('%H:%M')
        })
    
    return render_template('appointments.html', 
                         appointments=appointments_pagination.items,
                         patients=patients,
                         doctors=doctors,
                         search_query=search_query,
                         page=page,
                         total_pages=total_pages,
                         booked_slots=booked_slots)

@app.route('/delete_appointment/<int:appointment_id>')
@login_required
def delete_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    db.session.delete(appointment)
    db.session.commit()
    flash("Appointment deleted successfully!")
    return redirect(url_for('index'))
# Register
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if User.query.filter_by(username=username).first():
            flash("Username already exists")
            return redirect(url_for("register"))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please login.")
        return redirect(url_for("login"))
    return render_template("register.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("index"))
        flash("Invalid username or password")
    return render_template("login.html")

# Add Doctor
@app.route('/doctors')
@login_required
def doctors():
    search_query = request.args.get('search', '')
    if search_query:
        doctors = Doctor.query.filter(
            (Doctor.name.ilike(f'%{search_query}%')) | 
            (Doctor.specialization.ilike(f'%{search_query}%'))
        ).all()
    else:
        doctors = Doctor.query.all()
    
    return render_template('doctors.html', doctors=doctors, search_query=search_query)

@app.route('/add_doctor', methods=['GET', 'POST'])
def add_doctor():
    if request.method == 'POST':
        first_name = request.form['first_name']
        surname = request.form['surname']
        specialization = request.form['specialization']
        
        new_doctor = Doctor(
            first_name=first_name, 
            surname=surname, 
            specialization=specialization
        )
        
        db.session.add(new_doctor)
        db.session.commit()
        flash('Doctor added successfully!', 'success')
        return redirect(url_for('doctors'))
    
    # For GET requests, show the doctors list
    search_query = request.args.get('search', '')
    if search_query:
        doctors = Doctor.query.filter(
            (Doctor.first_name.ilike(f'%{search_query}%')) | 
            (Doctor.surname.ilike(f'%{search_query}%')) |
            (Doctor.specialization.ilike(f'%{search_query}%'))
        ).all()
    else:
        doctors = Doctor.query.all()
    
    return render_template('doctors.html', doctors=doctors, search_query=search_query)

@app.route('/edit_doctor/<int:doctor_id>', methods=['POST'])
def edit_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    
    if request.method == 'POST':
        doctor.first_name = request.form['first_name']
        doctor.surname = request.form['surname']
        doctor.specialization = request.form['specialization']
        
        db.session.commit()
        flash('Doctor updated successfully!', 'success')
        return redirect(url_for('doctors'))

@app.route('/delete_doctor/<int:doctor_id>')
def delete_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    
    # Check if doctor has appointments
    if doctor.appointments:
        flash('Cannot delete doctor with existing appointments!', 'danger')
        return redirect(url_for('doctors'))
    
    db.session.delete(doctor)
    db.session.commit()
    flash('Doctor deleted successfully!', 'success')
    return redirect(url_for('doctors'))

# Logout
@app.route("/logout")
@login_required
def logout():
    # Clear any existing flash messages
    from flask import get_flashed_messages
    get_flashed_messages()  # This clears the flash messages queue
    
    logout_user()
    flash("Logged out successfully!", "info")  # Use a different category if needed
    return redirect(url_for("login"))


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host= "0.0.0.0", port=5000, debug=True)
