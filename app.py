from flask import Flask, render_template, request, redirect, send_file, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import MedicalRecord, db, Patient, Doctor, Appointment, User, Prescription
from flask_migrate import Migrate
from datetime import datetime, date, timedelta
from math import ceil
import os
from werkzeug.utils import secure_filename
import uuid

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
    return db.session.get(User, int(user_id))

# Index (Dashboard)
from datetime import datetime, timedelta, date

@app.route('/')
@login_required
def index():
    patients = Patient.query.all()
    doctors = Doctor.query.all()
    appointments = Appointment.query.all()
    prescriptions = Prescription.query.all()
    
    # Get current datetime
    current_time = datetime.now()
    today = current_time.date()
    
    # Today's appointments
    today_appointments = Appointment.query.filter(
        Appointment.date == today
    ).order_by(Appointment.start_time).all()
    
    # Upcoming appointments (next 7 days)
    upcoming_appointments = Appointment.query.filter(
        Appointment.date >= today,
        Appointment.date <= today + timedelta(days=7)
    ).order_by(Appointment.date, Appointment.start_time).all()
    
    # Medical records count
    medical_records_count = MedicalRecord.query.count()
    
    # Recent medical records (last 7 days)
    recent_records_count = MedicalRecord.query.filter(
        MedicalRecord.upload_date >= today - timedelta(days=7)
    ).count()
    
    # Available doctors today (doctors with appointments today)
    available_doctors_today = Doctor.query.join(Appointment).filter(
        Appointment.date == today
    ).distinct().count()
    
    # Completed appointments today
    completed_appointments_today = Appointment.query.filter(
        Appointment.date == today,
        Appointment.start_time < current_time.time()
    ).count()
    
    # New patients this week
    new_patients_this_week = Patient.query.filter(
        Patient.date_created >= today - timedelta(days=7)
    ).count()
    
    # Active prescriptions
    pending_prescriptions = Prescription.query.filter(
        Prescription.date_prescribed >= today - timedelta(days=30)
    ).count()
    
    # Total medical records
    total_medical_records = MedicalRecord.query.count()
    
    # Recent patients (last 5)
    recent_patients = Patient.query.order_by(Patient.date_created.desc()).limit(5).all()
    
    # Recent medical records (last 5)
    recent_medical_records = MedicalRecord.query.order_by(MedicalRecord.upload_date.desc()).limit(5).all()
    
    return render_template('index.html',
                           patients=patients,
                           doctors=doctors,
                           appointments=appointments,
                           prescriptions=prescriptions,
                           today_appointments=today_appointments,
                           upcoming_appointments=upcoming_appointments,
                           medical_records_count=medical_records_count,
                           recent_records_count=recent_records_count,
                           available_doctors_today=available_doctors_today,
                           completed_appointments_today=completed_appointments_today,
                           new_patients_this_week=new_patients_this_week,
                           pending_prescriptions=pending_prescriptions,
                           total_medical_records=total_medical_records,
                           recent_patients=recent_patients,
                           recent_medical_records=recent_medical_records,
                           current_time=current_time)  # Make sure this is passed

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

@app.template_filter('datetime_time_delta')
def datetime_time_delta(time, **kwargs):
    """Add or subtract time from a datetime.time object"""
    dummy_date = datetime(2000, 1, 1)
    dummy_datetime = datetime.combine(dummy_date, time)
    result_datetime = dummy_datetime + timedelta(**kwargs)
    return result_datetime.time()

@app.template_filter('file_extension')
def file_extension(filename):
    """Get file extension from filename"""
    return filename.split('.')[-1].upper() if '.' in filename else 'FILE'

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
        
        # Check for doctor time conflicts
        existing_doctor_appointment = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.date == date_obj,
            (
                (Appointment.start_time <= start_time_obj) & (Appointment.end_time > start_time_obj) |
                (Appointment.start_time < end_time_obj) & (Appointment.end_time >= end_time_obj) |
                (Appointment.start_time >= start_time_obj) & (Appointment.end_time <= end_time_obj)
            )
        ).first()
        
        if existing_doctor_appointment:
            flash('This time slot conflicts with an existing appointment for the doctor!', 'danger')
            return redirect(url_for('appointments'))

        # Check for patient time conflicts
        existing_patient_appointment = Appointment.query.filter(
            Appointment.patient_id == patient_id,
            Appointment.date == date_obj,
            (
                (Appointment.start_time <= start_time_obj) & (Appointment.end_time > start_time_obj) |
                (Appointment.start_time < end_time_obj) & (Appointment.end_time >= end_time_obj) |
                (Appointment.start_time >= start_time_obj) & (Appointment.end_time <= end_time_obj)
            )
        ).first()
        
        if existing_patient_appointment:
            # Get the conflicting appointment details for better error message
            conflicting_appointment = existing_patient_appointment
            doctor_name = conflicting_appointment.doctor.name
            flash(f'This patient already has an appointment at the selected time with Dr. {doctor_name}! Please choose a different time.', 'danger')
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
    
    # Create a structure of booked time slots by patient and date
    patient_booked_slots = {}
    for appt in booked_appointments:
        key = f"{appt.patient_id}_{appt.date}"
        if key not in patient_booked_slots:
            patient_booked_slots[key] = []
        # Store both start and end times and doctor info
        patient_booked_slots[key].append({
            'start': appt.start_time.strftime('%H:%M'),
            'end': appt.end_time.strftime('%H:%M'),
            'doctor_name': appt.doctor.name
        })
    
    max_allowed_date = date.today() + timedelta(days=365)
    
    # Get today's date for status comparison
    today_date = date.today()
    
    return render_template('appointments.html', 
                         appointments=appointments_pagination.items,
                         patients=patients,
                         doctors=doctors,
                         search_query=search_query,
                         page=page,
                         total_pages=total_pages,
                         booked_slots=booked_slots,
                         patient_booked_slots=patient_booked_slots,
                         max_allowed_date=max_allowed_date.strftime('%Y-%m-%d'),
                         today_date=today_date)

@app.route('/delete_appointment/<int:appointment_id>')
@login_required
def delete_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    db.session.delete(appointment)
    db.session.commit()
    flash("Appointment deleted successfully!", "success")
    # Redirect back to appointments page instead of index
    return redirect(url_for('appointments'))

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
    from datetime import date

    search_query = request.args.get('search', '')
    if search_query:
        doctors = Doctor.query.filter(
            (Doctor.name.ilike(f'%{search_query}%')) | 
            (Doctor.specialization.ilike(f'%{search_query}%'))
        ).all()
    else:
        doctors = Doctor.query.all()
    
    # Add today_date for status comparison in the template
    today_date = date.today()
    
    return render_template('doctors.html', doctors=doctors, search_query=search_query, today_date=today_date)

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

@app.route('/doctor_availability', methods=['GET', 'POST'])
@login_required
def doctor_availability():
    # Handle appointment creation from availability page
    if request.method == 'POST':
        date_str = request.form['date']  
        start_time_str = request.form['start_time']  
        end_time_str = request.form['end_time']  
        diagnosis = request.form.get('diagnosis', '')
        patient_id = request.form['patient_id']
        doctor_id = request.form['doctor_id']

        # Validate date is not more than a year ahead
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        max_allowed_date = date.today() + timedelta(days=365)
        
        if date_obj > max_allowed_date:
            flash('Cannot book appointments more than one year in advance!', 'danger')
            return redirect(url_for('doctor_availability', date=date_str))
        
        # Validate weekday
        if date_obj.weekday() >= 5:  # 5=Saturday, 6=Sunday
            flash('Appointments are only available Monday to Friday!', 'danger')
            return redirect(url_for('doctor_availability', date=date_str))
        
        # Convert time strings to time objects
        start_time_obj = datetime.strptime(start_time_str, '%H:%M').time()
        end_time_obj = datetime.strptime(end_time_str, '%H:%M').time()
        
        # Validate that end time is after start time
        if end_time_obj <= start_time_obj:
            flash('End time must be after start time!', 'danger')
            return redirect(url_for('doctor_availability', date=date_str))
        
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
            return redirect(url_for('doctor_availability', date=date_str))

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
        flash("Appointment booked successfully!", 'success')
        return redirect(url_for('doctor_availability', date=date_str))

    # Handle GET request - show availability
    selected_date = request.args.get('date')
    if selected_date:
        try:
            selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()
    
    # Check if selected date is weekend
    is_weekend = selected_date.weekday() >= 5
    
    # Get all doctors
    doctors = Doctor.query.all()
    patients = Patient.query.all()  # Add this for the booking form
    
    # Get appointments for the selected date
    appointments = Appointment.query.filter(Appointment.date == selected_date).all()
    
    # Create availability data structure
    availability_data = []
    
    # Define working hours (8:00 AM to 6:00 PM)
    working_hours_start = datetime.strptime('08:00', '%H:%M').time()
    working_hours_end = datetime.strptime('18:00', '%H:%M').time()
    
    for doctor in doctors:
        # Get doctor's appointments for the selected date
        doctor_appointments = [appt for appt in appointments if appt.doctor_id == doctor.id]
        
        # Sort appointments by start time
        doctor_appointments.sort(key=lambda x: x.start_time)
        
        # Calculate available time slots (only if not weekend)
        available_slots = []
        total_available_minutes = 0
        total_available_hours = 0
        availability_percentage = 0
        
        if not is_weekend:
            current_time = working_hours_start
            
            for appointment in doctor_appointments:
                # If there's a gap before the appointment, it's available
                if current_time < appointment.start_time:
                    slot_duration = (datetime.combine(selected_date, appointment.start_time) - 
                                   datetime.combine(selected_date, current_time)).seconds // 60
                    available_slots.append({
                        'start': current_time,
                        'end': appointment.start_time,
                        'duration': slot_duration
                    })
                    total_available_minutes += slot_duration
                
                # Move current time to after this appointment
                current_time = appointment.end_time
            
            # Check for availability after the last appointment
            if current_time < working_hours_end:
                slot_duration = (datetime.combine(selected_date, working_hours_end) - 
                               datetime.combine(selected_date, current_time)).seconds // 60
                available_slots.append({
                    'start': current_time,
                    'end': working_hours_end,
                    'duration': slot_duration
                })
                total_available_minutes += slot_duration
            
            total_available_hours = total_available_minutes / 60
            availability_percentage = (total_available_minutes / (10 * 60)) * 100  # 10 hours total
        
        availability_data.append({
            'doctor': doctor,
            'appointments': doctor_appointments,
            'available_slots': available_slots,
            'total_available_minutes': total_available_minutes,
            'total_available_hours': total_available_hours,
            'availability_percentage': availability_percentage
        })
    
    # Format dates for template
    today = date.today()
    min_date = today
    max_date = today + timedelta(days=30)  # Show availability for next 30 days
    
    # Get booked appointments for the next 7 days to show availability
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
    
    # Prepare detailed appointments data for JSON - FIXED: Use different variable name
    detailed_appointments_json = {}
    for doctor_data in availability_data:  # Changed variable name to avoid conflict
        doctor_appointments_list = []
        for appointment in doctor_data['appointments']:  # Access as dictionary
            doctor_appointments_list.append({
                'id': appointment.id,
                'patient_name': f"{appointment.patient.first_name} {appointment.patient.surname}",
                'patient_phone': appointment.patient.phone or 'N/A',
                'start_time': appointment.start_time.strftime('%H:%M') if appointment.start_time else '',
                'end_time': appointment.end_time.strftime('%H:%M') if appointment.end_time else '',
                'diagnosis': appointment.diagnosis or 'No diagnosis notes',
                'date_created': appointment.date_created.strftime('%Y-%m-%d %H:%M') if appointment.date_created else 'N/A',
                'status': 'Today' if appointment.date == today else 'Upcoming' if appointment.date > today else 'Completed'
            })
        detailed_appointments_json[str(doctor_data['doctor'].id)] = doctor_appointments_list
    
    return render_template('doctor_availability.html',
                         availability_data=availability_data,
                         selected_date=selected_date,
                         today=today,
                         min_date=min_date,
                         max_date=max_date,
                         is_weekend=is_weekend,
                         patients=patients,
                         booked_slots=booked_slots,
                         appointments_json=detailed_appointments_json)  # Use the fixed variable name

# Prescription Management
@app.route('/prescriptions')
@login_required
def prescriptions():
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Build query based on search
    if search_query:
        query = Prescription.query.join(Patient).join(Doctor).filter(
            (Patient.first_name.ilike(f'%{search_query}%')) | 
            (Patient.surname.ilike(f'%{search_query}%')) |
            (Doctor.first_name.ilike(f'%{search_query}%')) |
            (Doctor.surname.ilike(f'%{search_query}%')) |
            (Prescription.medication_name.ilike(f'%{search_query}%'))
        )
    else:
        query = Prescription.query
    
    # Get paginated results
    prescriptions_pagination = query.order_by(Prescription.date_prescribed.desc(), Prescription.date_created.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Calculate total pages
    total_pages = ceil(query.count() / per_page)
    
    patients = Patient.query.all()
    doctors = Doctor.query.all()
    
    # ADD THIS LINE - Pass current date to template
    today = date.today()
    
    return render_template('prescriptions.html',
                         prescriptions=prescriptions_pagination.items,
                         patients=patients,
                         doctors=doctors,
                         search_query=search_query,
                         page=page,
                         total_pages=total_pages,
                         today=today)  # Add this parameter

@app.route('/add_prescription', methods=['POST'])
@login_required
def add_prescription():
    if request.method == 'POST':
        medication_name = request.form['medication_name']
        dosage = request.form['dosage']
        frequency = request.form['frequency']
        duration = request.form['duration']
        instructions = request.form.get('instructions', '')
        patient_id = request.form['patient_id']
        doctor_id = request.form['doctor_id']
        date_prescribed = datetime.strptime(request.form['date_prescribed'], '%Y-%m-%d').date()

        new_prescription = Prescription(
            medication_name=medication_name,
            dosage=dosage,
            frequency=frequency,
            duration=duration,
            instructions=instructions,
            patient_id=patient_id,
            doctor_id=doctor_id,
            date_prescribed=date_prescribed
        )
        
        db.session.add(new_prescription)
        db.session.commit()
        flash('Prescription added successfully!', 'success')
        
        return redirect(url_for('prescriptions'))

@app.route('/edit_prescription/<int:prescription_id>', methods=['POST'])
@login_required
def edit_prescription(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    
    if request.method == 'POST':
        prescription.medication_name = request.form['medication_name']
        prescription.dosage = request.form['dosage']
        prescription.frequency = request.form['frequency']
        prescription.duration = request.form['duration']
        prescription.instructions = request.form.get('instructions', '')
        prescription.patient_id = request.form['patient_id']
        prescription.doctor_id = request.form['doctor_id']
        prescription.date_prescribed = datetime.strptime(request.form['date_prescribed'], '%Y-%m-%d').date()
        
        db.session.commit()
        flash('Prescription updated successfully!', 'success')
        
        return redirect(url_for('prescriptions'))

@app.route('/delete_prescription/<int:prescription_id>')
@login_required
def delete_prescription(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    
    db.session.delete(prescription)
    db.session.commit()
    flash('Prescription deleted successfully!', 'success')
    
    return redirect(url_for('prescriptions'))

@app.route('/get_patient_info/<int:patient_id>')
@login_required
def get_patient_info(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return jsonify({
        'name': f"{patient.first_name} {patient.surname}",
        'age': patient.age,
        'gender': patient.gender
    })


UPLOAD_FOLDER = 'medical_records'
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'txt'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_folder():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

@app.route('/medical_records')
@login_required
def medical_records():
    search_query = request.args.get('search', '')
    patient_filter = request.args.get('patient_filter', '')
    record_type_filter = request.args.get('record_type', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Build query based on filters
    query = MedicalRecord.query
    
    if search_query:
        query = query.join(Patient).filter(
            (Patient.first_name.ilike(f'%{search_query}%')) | 
            (Patient.surname.ilike(f'%{search_query}%')) |
            (MedicalRecord.record_type.ilike(f'%{search_query}%')) |
            (MedicalRecord.description.ilike(f'%{search_query}%'))
        )
    
    if patient_filter:
        query = query.filter(MedicalRecord.patient_id == patient_filter)
    
    if record_type_filter:
        query = query.filter(MedicalRecord.record_type == record_type_filter)
    
    # Get paginated results
    medical_records_pagination = query.order_by(MedicalRecord.upload_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Calculate total pages
    total_pages = ceil(query.count() / per_page)
    
    all_patients = Patient.query.all()
    all_doctors = Doctor.query.all()
    
    return render_template('medical_records.html',
                         medical_records=medical_records_pagination.items,
                         all_patients=all_patients,
                         all_doctors=all_doctors,
                         search_query=search_query,
                         patient_filter=patient_filter,
                         record_type_filter=record_type_filter,
                         page=page,
                         total_pages=total_pages)

@app.route('/medical_records', methods=['POST'])
@login_required
def upload_medical_record():
    ensure_upload_folder()
    
    if 'medical_file' not in request.files:
        flash('No file selected!', 'danger')
        return redirect(url_for('medical_records'))
    
    file = request.files['medical_file']
    
    if file.filename == '':
        flash('No file selected!', 'danger')
        return redirect(url_for('medical_records'))
    
    if file and allowed_file(file.filename):
        # Check file size
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0, 0)
        
        if file_length > MAX_FILE_SIZE:
            flash('File size must be less than 10MB!', 'danger')
            return redirect(url_for('medical_records'))
        
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        try:
            file.save(file_path)
            
            # Create medical record in database
            medical_record = MedicalRecord(
                patient_id=request.form['patient_id'],
                doctor_id=request.form['doctor_id'],
                record_type=request.form['record_type'],
                file_name=filename,
                file_path=file_path,
                file_size=file_length,
                description=request.form.get('description', '')
            )
            
            db.session.add(medical_record)
            db.session.commit()
            flash('Medical record uploaded successfully!', 'success')
            
        except Exception as e:
            flash('Error uploading file!', 'danger')
            print(f"Error: {e}")
            
    else:
        flash('Invalid file type! Allowed types: PDF, JPG, JPEG, PNG, GIF, DOC, DOCX, TXT', 'danger')
    
    return redirect(url_for('medical_records'))

@app.route('/medical_records/<int:record_id>/download')
@login_required
def download_medical_record(record_id):
    medical_record = MedicalRecord.query.get_or_404(record_id)
    
    if not os.path.exists(medical_record.file_path):
        flash('File not found!', 'danger')
        return redirect(url_for('medical_records'))
    
    return send_file(medical_record.file_path, 
                     as_attachment=True, 
                     download_name=medical_record.file_name)

@app.route('/medical_records/<int:record_id>/delete')
@login_required
def delete_medical_record(record_id):
    medical_record = MedicalRecord.query.get_or_404(record_id)
    
    try:
        # Delete physical file
        if os.path.exists(medical_record.file_path):
            os.remove(medical_record.file_path)
        
        # Delete database record
        db.session.delete(medical_record)
        db.session.commit()
        flash('Medical record deleted successfully!', 'success')
        
    except Exception as e:
        flash('Error deleting medical record!', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('medical_records'))

@app.route('/medical_records/<int:record_id>/view')
@login_required
def view_medical_record(record_id):
    medical_record = MedicalRecord.query.get_or_404(record_id)
    
    if not os.path.exists(medical_record.file_path):
        flash('File not found!', 'danger')
        return redirect(url_for('medical_records'))
    
    # For PDF and images, send file for viewing
    if medical_record.is_pdf() or medical_record.is_image():
        return send_file(medical_record.file_path)
    else:
        # For other file types, force download
        return send_file(medical_record.file_path, 
                         as_attachment=True, 
                         download_name=medical_record.file_name)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host= "0.0.0.0", port=8000, debug=True)