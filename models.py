from extensions import db
from flask_login import UserMixin
from datetime import datetime


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # 'student' or 'teacher'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    attempts = db.relationship('Attempt', backref='user', lazy=True, cascade='all, delete-orphan')
    submissions = db.relationship('Submission', backref='user', lazy=True, cascade='all, delete-orphan')


class Week(db.Model):
    __tablename__ = 'weeks'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    week_number = db.Column(db.Integer, nullable=False)
    is_enabled = db.Column(db.Boolean, default=False)
    is_intro = db.Column(db.Boolean, default=False)
    teacher_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship('Question', backref='week', lazy=True, cascade='all, delete-orphan', order_by='Question.order')
    slides = db.relationship('Slide', backref='week', lazy=True, cascade='all, delete-orphan', order_by='Slide.order')
    attempts = db.relationship('Attempt', backref='week', lazy=True, cascade='all, delete-orphan')
    submissions = db.relationship('Submission', backref='week', lazy=True, cascade='all, delete-orphan')


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey('weeks.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    # 'mcq' = single correct option, 'multi' = multiple correct options, 'text' = free-text answer
    qtype = db.Column(db.String(20), default='mcq', nullable=False)
    model_answer = db.Column(db.Text)  # optional, shown to teacher when marking text questions
    topic = db.Column(db.String(100))
    section = db.Column(db.String(100))
    explanation = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    options = db.relationship('Option', backref='question', lazy=True, cascade='all, delete-orphan', order_by='Option.order')
    answers = db.relationship('Answer', backref='question', lazy=True, cascade='all, delete-orphan')


class Option(db.Model):
    __tablename__ = 'options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)


class Slide(db.Model):
    __tablename__ = 'slides'
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey('weeks.id'), nullable=False)
    title = db.Column(db.String(200))
    filename = db.Column(db.String(300))
    file_type = db.Column(db.String(50))  # 'pdf', 'pptx', 'image', 'link'
    url = db.Column(db.String(500))        # for external links
    order = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Attempt(db.Model):
    __tablename__ = 'attempts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey('weeks.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    answers = db.relationship('Answer', backref='attempt', lazy=True, cascade='all, delete-orphan')


class Answer(db.Model):
    __tablename__ = 'answers'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('options.id'), nullable=True)  # single-choice answer
    selected_option_ids = db.Column(db.String(300))  # comma-separated ids for multi-answer questions
    text_answer = db.Column(db.Text)                  # free-text answer
    is_correct = db.Column(db.Boolean, default=False)
    pending = db.Column(db.Boolean, default=False)    # True = awaiting teacher marking (text questions)
    teacher_feedback = db.Column(db.Text)             # teacher's comment when marking
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey('weeks.id'), nullable=False)
    title = db.Column(db.String(200))
    comment = db.Column(db.Text)                      # student's note with their submission
    file_url = db.Column(db.String(600), nullable=False)   # Cloudinary URL
    file_name = db.Column(db.String(300))             # original filename
    file_format = db.Column(db.String(20))            # pdf, docx, etc.
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher_feedback = db.Column(db.Text)             # teacher's feedback on the work
    grade = db.Column(db.String(50))                  # free-form grade, e.g. "8/10" or "Merit"
    reviewed_at = db.Column(db.DateTime)
