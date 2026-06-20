from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort, current_app
from flask_login import login_required, current_user
from models import Week, Question, Option, Attempt, Answer, User, Slide, Submission
from extensions import db
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from functools import wraps
from datetime import datetime
import os

import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True,
)

teacher_bp = Blueprint('teacher', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'pptx', 'ppt', 'png', 'jpg', 'jpeg', 'gif',
                      'doc', 'docx', 'xlsx', 'xls', 'txt', 'csv'}
IMAGE_EXTS = {'png', 'jpg', 'jpeg', 'gif'}

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
    pending_marks = Answer.query.filter_by(pending=True).count()
    new_submissions = Submission.query.filter_by(reviewed_at=None).count()
    return render_template('teacher/dashboard.html', weeks=weeks,
                           students=students, total_attempts=total_attempts,
                           pending_marks=pending_marks, new_submissions=new_submissions)

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
    submissions = Submission.query.filter_by(user_id=student_id)\
        .order_by(Submission.submitted_at.desc()).all()
    return render_template('teacher/student_detail.html', student=student,
                           week_data=week_data, submissions=submissions)

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

# ── Marking free-text answers ──────────────────────────────────────────────────
@teacher_bp.route('/marking')
@login_required
@teacher_required
def marking_queue():
    pending = Answer.query.filter_by(pending=True).order_by(Answer.answered_at).all()
    return render_template('teacher/marking.html', pending=pending)

@teacher_bp.route('/answers/<int:answer_id>/mark', methods=['POST'])
@login_required
@teacher_required
def mark_answer(answer_id):
    answer = Answer.query.get_or_404(answer_id)
    verdict = request.form.get('verdict')          # 'correct' or 'incorrect'
    feedback = request.form.get('feedback', '').strip()

    was_correct = bool(answer.is_correct)
    answer.is_correct = (verdict == 'correct')
    answer.pending = False
    answer.teacher_feedback = feedback

    attempt = answer.attempt
    if answer.is_correct and not was_correct:
        attempt.score += 1
    elif not answer.is_correct and was_correct:
        attempt.score = max(0, attempt.score - 1)

    db.session.commit()
    flash('Answer marked.', 'success')
    return redirect(request.referrer or url_for('teacher.marking_queue'))

# ── Submissions (student work) ─────────────────────────────────────────────────
@teacher_bp.route('/submissions')
@login_required
@teacher_required
def submissions():
    all_subs = Submission.query.order_by(Submission.submitted_at.desc()).all()
    return render_template('teacher/submissions.html', submissions=all_subs)

@teacher_bp.route('/submissions/<int:sub_id>/review', methods=['POST'])
@login_required
@teacher_required
def review_submission(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    sub.teacher_feedback = request.form.get('feedback', '').strip()
    sub.grade = request.form.get('grade', '').strip()
    sub.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash('Feedback saved.', 'success')
    return redirect(request.referrer or url_for('teacher.submissions'))

@teacher_bp.route('/submissions/<int:sub_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_submission(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    db.session.delete(sub)
    db.session.commit()
    flash('Submission deleted.', 'success')
    return redirect(request.referrer or url_for('teacher.submissions'))

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
    week_submissions = Submission.query.filter_by(week_id=week.id)\
        .order_by(Submission.submitted_at.desc()).all()
    return render_template('teacher/week_detail.html', week=week,
                           questions=questions, slides=slides,
                           attempts_count=attempts_count,
                           week_submissions=week_submissions)

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
def _parse_question_form(form):
    """Shared parser for add/edit question forms. Returns (dict, None) or (None, error)."""
    qtype = form.get('qtype', 'mcq')
    text = form.get('text', '').strip()
    topic = form.get('topic', '').strip()
    section = form.get('section', '').strip()
    explanation = form.get('explanation', '').strip()
    model_answer = form.get('model_answer', '').strip()

    if not text:
        return None, 'Question text is required.'

    options, correct_flags = [], []
    if qtype in ('mcq', 'multi'):
        raw = [form.get(f'option_{i}', '').strip() for i in range(4)]
        # keep original indexes so correct flags line up, but drop blank trailing options
        kept = [(i, o) for i, o in enumerate(raw) if o]
        if len(kept) < 2:
            return None, 'At least 2 options are required.'
        options = [o for _, o in kept]
        if qtype == 'mcq':
            correct = int(form.get('correct_option', 0))
            correct_flags = [i == correct for i, _ in kept]
            if not any(correct_flags):
                return None, 'Select the correct option (it cannot be a blank one).'
        else:
            correct_flags = [form.get(f'correct_{i}') == 'on' for i, _ in kept]
            if not any(correct_flags):
                return None, 'Tick at least one correct option.'

    return {
        'qtype': qtype, 'text': text, 'topic': topic, 'section': section,
        'explanation': explanation, 'model_answer': model_answer,
        'options': options, 'correct_flags': correct_flags,
    }, None

@teacher_bp.route('/weeks/<slug>/questions/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_question(slug):
    week = Week.query.filter_by(slug=slug).first_or_404()
    if request.method == 'POST':
        parsed, error = _parse_question_form(request.form)
        if error:
            flash(error, 'error')
        else:
            order = len(week.questions)
            q = Question(week_id=week.id, text=parsed['text'], qtype=parsed['qtype'],
                         topic=parsed['topic'], section=parsed['section'],
                         explanation=parsed['explanation'],
                         model_answer=parsed['model_answer'], order=order)
            db.session.add(q)
            db.session.flush()
            for i, opt_text in enumerate(parsed['options']):
                opt = Option(question_id=q.id, text=opt_text,
                             is_correct=parsed['correct_flags'][i], order=i)
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
        parsed, error = _parse_question_form(request.form)
        if error:
            flash(error, 'error')
        else:
            q.text = parsed['text']
            q.qtype = parsed['qtype']
            q.topic = parsed['topic']
            q.section = parsed['section']
            q.explanation = parsed['explanation']
            q.model_answer = parsed['model_answer']
            for opt in list(q.options):
                db.session.delete(opt)
            db.session.flush()
            for i, opt_text in enumerate(parsed['options']):
                db.session.add(Option(question_id=q.id, text=opt_text,
                                      is_correct=parsed['correct_flags'][i], order=i))
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
        slide_type = request.form.get('slide_type', 'link')
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
                flash('Please upload a valid file (PDF, Word, PowerPoint, Excel, image, or text).', 'error')
            else:
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                file_type = 'image' if ext in IMAGE_EXTS else ext
                is_doc = ext in {'doc','docx','ppt','pptx','xls','xlsx','txt','csv'}
                try:
                    result = cloudinary.uploader.upload(
                        file,
                        resource_type='raw' if is_doc else 'auto',
                        folder=f'gcse-quiz/resources/{week.slug}',
                        public_id=f'res_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}_{secure_filename(file.filename)}',
                        use_filename=False,
                    )
                except Exception as e:
                    print('CLOUDINARY RESOURCE UPLOAD ERROR:', e)
                    flash(f'Upload failed: {e}', 'error')
                    return redirect(url_for('teacher.add_slide', slug=slug))
                slide = Slide(week_id=week.id, title=title or file.filename,
                              filename=file.filename, file_type=file_type,
                              cloud_url=result.get('secure_url'), order=order)
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
    # Remove any legacy local file (older uploads saved to disk)
    if slide.filename and not slide.cloud_url:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], slide.filename)
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(slide)
    db.session.commit()
    flash('Resource deleted.', 'success')
    return redirect(url_for('teacher.week_detail', slug=slug))
