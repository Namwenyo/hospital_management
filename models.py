from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import os
from flask import current_app

db = SQLAlchemy()

class Patient(db.Model):
    __tablename__ = 'patient'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    surname = db.Column(db.String(50), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)  # Store date of birth
    gender = db.Column(db.String(10))
    phone = db.Column(db.String(15))
    date_created = db.Column(db.DateTime, default=datetime.utcnow)  # New field for creation date
    
    # Relationship to Appointment
    appointments = db.relationship('Appointment', back_populates='patient')
    # Relationship to Prescription
    prescriptions = db.relationship('Prescription', back_populates='patient')
    
    # Calculate age based on date of birth
    @property
    def age(self):
        today = date.today()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

class Doctor(db.Model):
    __tablename__ = 'doctor'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    surname = db.Column(db.String(50), nullable=False)
    specialization = db.Column(db.String(50))
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationship to Appointment
    appointments = db.relationship('Appointment', back_populates='doctor')
    # Relationship to Prescription
    prescriptions = db.relationship('Prescription', back_populates='doctor')
    
    @property
    def name(self):
        return f"{self.first_name} {self.surname}"
    
class Appointment(db.Model):
    __tablename__ = 'appointment'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)  # Changed from time to start_time
    end_time = db.Column(db.Time, nullable=False)    # Added end_time
    diagnosis = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)

    # Relationships
    patient = db.relationship('Patient', back_populates='appointments')
    doctor = db.relationship('Doctor', back_populates='appointments')

class Prescription(db.Model):
    __tablename__ = 'prescription'

    id = db.Column(db.Integer, primary_key=True)
    medication_name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50), nullable=False)
    frequency = db.Column(db.String(50), nullable=False)
    duration = db.Column(db.String(50), nullable=False)
    instructions = db.Column(db.Text)
    date_prescribed = db.Column(db.Date, nullable=False, default=date.today)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)

    # Relationships
    patient = db.relationship('Patient', back_populates='prescriptions')
    doctor = db.relationship('Doctor', back_populates='prescriptions')

class MedicalRecord(db.Model):
    __tablename__ = 'medical_record'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    record_type = db.Column(db.String(100), nullable=False)  # e.g., 'Lab Report', 'X-Ray', 'Prescription', 'Medical History'
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)  # Size in bytes
    description = db.Column(db.Text)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', backref=db.backref('medical_records', lazy=True))
    doctor = db.relationship('Doctor', backref=db.backref('medical_records', lazy=True))
    
    def __repr__(self):
        return f'<MedicalRecord {self.file_name} for Patient {self.patient_id}>'
    
    def get_file_url(self):
        return f"/medical_records/{self.id}/view"
    
    def get_file_extension(self):
        return os.path.splitext(self.file_name)[1].lower()
    
    def is_image(self):
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
        return self.get_file_extension() in image_extensions
    
    def is_pdf(self):
        return self.get_file_extension() == '.pdf'
    
    def can_preview(self):
        return self.is_image() or self.is_pdf()    

class User(db.Model, UserMixin):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)