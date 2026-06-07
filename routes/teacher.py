from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort, current_app
from flask_login import login_required, current_user
from models import Week, Question, Option, Attempt, Answer, User, Slide
from extensions import db
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from functools import wraps
from datetime import datetime
import os

teacher_bp = Blueprint('teacher', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'pptx', 'ppt', 'png', 'jpg', 'jpeg', 'gif'}

def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'teacher':
            abort(403)
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ── Dashboard ──────────────────────────────────────────────────────────────────
@teacher_bp.route('/')
@login_required
@teacher_required
def dashboard():
    weeks = Week.query.order_by(Week.week_number).all()
    students = User.query.filter_by(role='student').order_by(User.full_name).all()
    total_attempts = Attempt.query.filter_by(completed=True).count()
    return render_template('teacher/dashboard.html', weeks=weeks,
                           students=students, total_attempts=total_attempts)

# ── Students ───────────────────────────────────────────────────────────────────
@teacher_bp.route('/students')
@login_required
@teacher_required
def students():
    all_students = User.query.filter_by(role='student').order_by(User.full_name).all()
    student_data = []
    for s in all_students:
        completed = Attempt.query.filter_by(user_id=s.id, completed=True).count()
        last = Attempt.query.filter_by(user_id=s.id, completed=True)\
            .order_by(Attempt.completed_at.desc()).first()
        student_data.append({'user': s, 'completed_attempts': completed, 'last_attempt': last})
    return render_template('teacher/students.html', student_data=student_data)

@teacher_bp.route('/students/<int:student_id>')
@login_required
@teacher_required
def student_detail(student_id):
    student = User.query.filter_by(id=student_id, role='student').first_or_404()
    weeks = Week.query.order_by(Week.week_number).all()
    week_data = []
    for week in weeks:
        attempts = Attempt.query.filter_by(user_id=student_id, week_id=week.id, completed=True)\
            .order_by(Attempt.completed_at.desc()).all()
        best = max(attempts, key=lambda a: a.score) if attempts else None
        week_data.append({'week': week, 'attempts': attempts, 'best': best})
    return render_template('teacher/student_detail.html', student=student, week_data=week_data)

@teacher_bp.route('/results/<int:attempt_id>')
@login_required
@teacher_required
def view_attempt(attempt_id):
    attempt = Attempt.query.get_or_404(attempt_id)
    answers = {a.question_id: a for a in attempt.answers}
    questions = attempt.week.questions
    pct = round(attempt.score / attempt.total * 100) if attempt.total else 0
    return render_template('teacher/view_attempt.html', attempt=attempt,
                           answers=answers, questions=questions, pct=pct)

@teacher_bp.route('/students/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_student():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not all([full_name, username, email, password]):
            flash('All fields are required.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
        else:
            user = User(full_name=full_name, username=username, email=email,
                        password_hash=generate_password_hash(password), role='student')
            db.session.add(user)
            db.session.commit()
            flash(f'Student account created for {full_name}.', 'success')
            return redirect(url_for('teacher.students'))
    return render_template('teacher/add_student.html')

@teacher_bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_student(student_id):
    student = User.query.filter_by(id=student_id, role='student').first_or_404()
    db.session.delete(student)
    db.session.commit()
    flash(f'Student {student.full_name} deleted.', 'success')
    return redirect(url_for('teacher.students'))

# ── Weeks ──────────────────────────────────────────────────────────────────────
@teacher_bp.route('/weeks')
@login_required
@teacher_required
def weeks():
    all_weeks = Week.query.order_by(Week.week_number).all()
    return render_template('teacher/weeks.html', weeks=all_weeks)

@teacher_bp.route('/weeks/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_week():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if not title:
            flash('Title is required.', 'error')
        else:
            max_num = db.session.query(db.func.max(Week.week_number)).scalar() or 0
            week_number = max_num + 1
            base_slug = 'week' + str(week_number)
            slug = base_slug
            n = 1
            while Week.query.filter_by(slug=slug).first():
                n += 1
                slug = base_slug + '-' + str(n)
            w = Week(slug=slug, title=title, description=description,
                     week_number=week_number, is_enabled=False, is_intro=False)
            db.session.add(w)
            db.session.commit()
            flash('Week "' + title + '" created.', 'success')
            return redirect(url_for('teacher.week_detail', slug=slug))
    return render_template('teacher/add_week.html')

@teacher_bp.route('/weeks/<slug>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_week(slug):
    week = Week.query.filter_by(slug=slug).first_or_404()
    if week.is_intro:
        flash('The introductory quiz cannot be deleted.', 'error')
        return redirect(url_for('teacher.week_detail', slug=slug))
    title = week.title
    db.session.delete(week)
    db.session.commit()
    flash('Week "' + title + '" and all its data were deleted.', 'success')
    return redirect(url_for('teacher.weeks'))

@teacher_bp.route('/weeks/<slug>')
@login_required
@teacher_required
def week_detail(slug):
    week = Week.query.filter_by(slug=slug).first_or_404()
    questions = week.questions
    slides = week.slides
    attempts_count = Attempt.query.filter_by(week_id=week.id, completed=True).count()
    return render_template('teacher/week_detail.html', week=week,
                           questions=questions, slides=slides, attempts_count=attempts_count)

@teacher_bp.route('/weeks/<slug>/toggle', methods=['POST'])
@login_required
@teacher_required
def toggle_week(slug):
    week = Week.query.filter_by(slug=slug).first_or_404()
    week.is_enabled = not week.is_enabled
    db.session.commit()
    status = 'enabled' if week.is_enabled else 'disabled'
    flash(f'{week.title} {status} for students.', 'success')
    return redirect(url_for('teacher.week_detail', slug=slug))

@teacher_bp.route('/weeks/<slug>/edit', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_week(slug):
    week = Week.query.filter_by(slug=slug).first_or_404()
    if request.method == 'POST':
        week.title = request.form.get('title', week.title).strip()
        week.description = request.form.get('description', week.description).strip()
        week.teacher_notes = request.form.get('teacher_notes', '').strip()
        db.session.commit()
        flash('Week updated.', 'success')
        return redirect(url_for('teacher.week_detail', slug=slug))
    return render_template('teacher/edit_week.html', week=week)

# ── Questions ──────────────────────────────────────────────────────────────────
@teacher_bp.route('/weeks/<slug>/questions/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_question(slug):
    week = Week.query.filter_by(slug=slug).first_or_404()
    if request.method == 'POST':
        text = request.form.get('text', '').strip()
        topic = request.form.get('topic', '').strip()
        section = request.form.get('section', '').strip()
        explanation = request.form.get('explanation', '').strip()
        options = [request.form.get(f'option_{i}', '').strip() for i in range(4)]
        correct = int(request.form.get('correct_option', 0))

        if not text or not all(options):
            flash('Question text and all 4 options are required.', 'error')
        else:
            order = len(week.questions)
            q = Question(week_id=week.id, text=text, topic=topic, section=section,
                         explanation=explanation, order=order)
            db.session.add(q)
            db.session.flush()
            for i, opt_text in enumerate(options):
                opt = Option(question_id=q.id, text=opt_text, is_correct=(i == correct), order=i)
                db.session.add(opt)
            db.session.commit()
            flash('Question added.', 'success')
            return redirect(url_for('teacher.week_detail', slug=slug))
    return render_template('teacher/add_question.html', week=week)

@teacher_bp.route('/questions/<int:q_id>/edit', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_question(q_id):
    q = Question.query.get_or_404(q_id)
    week = q.week
    if request.method == 'POST':
        q.text = request.form.get('text', '').strip()
        q.topic = request.form.get('topic', '').strip()
        q.section = request.form.get('section', '').strip()
        q.explanation = request.form.get('explanation', '').strip()
        options = [request.form.get(f'option_{i}', '').strip() for i in range(4)]
        correct = int(request.form.get('correct_option', 0))
        for i, opt in enumerate(q.options):
            opt.text = options[i]
            opt.is_correct = (i == correct)
        db.session.commit()
        flash('Question updated.', 'success')
        return redirect(url_for('teacher.week_detail', slug=week.slug))
    return render_template('teacher/edit_question.html', week=week, question=q)

@teacher_bp.route('/questions/<int:q_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_question(q_id):
    q = Question.query.get_or_404(q_id)
    slug = q.week.slug
    db.session.delete(q)
    db.session.commit()
    flash('Question deleted.', 'success')
    return redirect(url_for('teacher.week_detail', slug=slug))

# ── Slides / Resources ─────────────────────────────────────────────────────────
@teacher_bp.route('/weeks/<slug>/slides/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_slide(slug):
    week = Week.query.filter_by(slug=slug).first_or_404()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        slide_type = request.form.get('slide_type', 'file')
        order = len(week.slides)

        if slide_type == 'link':
            url = request.form.get('url', '').strip()
            if not url:
                flash('URL is required.', 'error')
            else:
                slide = Slide(week_id=week.id, title=title, file_type='link', url=url, order=order)
                db.session.add(slide)
                db.session.commit()
                flash('Link added.', 'success')
                return redirect(url_for('teacher.week_detail', slug=slug))
        else:
            file = request.files.get('file')
            if not file or not allowed_file(file.filename):
                flash('Please upload a valid file (PDF, PPTX, PNG, JPG).', 'error')
            else:
                filename = secure_filename(file.filename)
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{filename}"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                ext = filename.rsplit('.', 1)[1].lower()
                file_type = 'image' if ext in {'png','jpg','jpeg','gif'} else ext
                slide = Slide(week_id=week.id, title=title, filename=filename,
                              file_type=file_type, order=order)
                db.session.add(slide)
                db.session.commit()
                flash('File uploaded.', 'success')
                return redirect(url_for('teacher.week_detail', slug=slug))
    return render_template('teacher/add_slide.html', week=week)

@teacher_bp.route('/slides/<int:slide_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_slide(slide_id):
    slide = Slide.query.get_or_404(slide_id)
    slug = slide.week.slug
    if slide.filename:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], slide.filename)
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(slide)
    db.session.commit()
    flash('Resource deleted.', 'success')
    return redirect(url_for('teacher.week_detail', slug=slug))