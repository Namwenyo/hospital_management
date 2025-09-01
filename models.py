from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

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
    
    @property
    def name(self):
        return f"{self.first_name} {self.surname}"
    
class Appointment(db.Model):
    __tablename__ = 'appointment'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    diagnosis = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)  # New field for creation date

    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)

    # Relationships
    patient = db.relationship('Patient', back_populates='appointments')
    doctor = db.relationship('Doctor', back_populates='appointments')

class User(db.Model, UserMixin):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)