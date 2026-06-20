from flask import Blueprint, render_template, redirect, url_for, request, jsonify, abort, flash
from flask_login import login_required, current_user
from models import Week, Question, Option, Attempt, Answer, Submission
from extensions import db
from datetime import datetime
from functools import wraps
import os

import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True,
)

student_bp = Blueprint('student', __name__)

ALLOWED_SUBMISSION_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg', 'gif',
                                 'py', 'zip', 'pptx', 'ppt', 'xlsx', 'csv', 'md'}
MAX_SUBMISSION_MB = 10

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'student':
            abort(403)
        return f(*args, **kwargs)
    return decorated

@student_bp.route('/')
@login_required
@student_required
def home():
    weeks = Week.query.order_by(Week.week_number).all()
    attempt_map = {}
    for week in weeks:
        latest = Attempt.query.filter_by(user_id=current_user.id, week_id=week.id, completed=True)\
            .order_by(Attempt.completed_at.desc()).first()
        attempt_map[week.id] = latest
    return render_template('student/home.html', weeks=weeks, attempt_map=attempt_map)

@student_bp.route('/week/<slug>')
@login_required
@student_required
def week_detail(slug):
    week = Week.query.filter_by(slug=slug).first_or_404()
    if not week.is_enabled:
        abort(403)
    questions = week.questions
    slides = week.slides
    past_attempts = Attempt.query.filter_by(user_id=current_user.id, week_id=week.id, completed=True)\
        .order_by(Attempt.completed_at.desc()).all()
    my_submissions = Submission.query.filter_by(user_id=current_user.id, week_id=week.id)\
        .order_by(Submission.submitted_at.desc()).all()
    return render_template('student/week_detail.html', week=week, questions=questions,
                           slides=slides, past_attempts=past_attempts,
                           my_submissions=my_submissions)

# ── Work submissions ───────────────────────────────────────────────────────────
@student_bp.route('/week/<slug>/submit-work', methods=['POST'])
@login_required
@student_required
def submit_work(slug):
    week = Week.query.filter_by(slug=slug).first_or_404()
    if not week.is_enabled or not week.allow_submissions:
        abort(403)

    file = request.files.get('file')
    title = request.form.get('title', '').strip()
    comment = request.form.get('comment', '').strip()

    if not file or file.filename == '':
        flash('Please choose a file to upload.', 'error')
        return redirect(url_for('student.week_detail', slug=slug))

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_SUBMISSION_EXTENSIONS:
        flash(f'File type ".{ext}" is not allowed.', 'error')
        return redirect(url_for('student.week_detail', slug=slug))

    file.seek(0, os.SEEK_END)
    size_mb = file.tell() / (1024 * 1024)
    file.seek(0)
    if size_mb > MAX_SUBMISSION_MB:
        flash(f'File is too large ({size_mb:.1f} MB). Maximum is {MAX_SUBMISSION_MB} MB.', 'error')
        return redirect(url_for('student.week_detail', slug=slug))

    from werkzeug.utils import secure_filename
    is_doc = ext in {'doc','docx','ppt','pptx','xls','xlsx','txt','csv','py','zip','md'}
    try:
        result = cloudinary.uploader.upload(
            file,
            resource_type='raw' if is_doc else 'auto',
            folder=f'gcse-quiz/submissions/{week.slug}',
            public_id=f'u{current_user.id}_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}_{secure_filename(file.filename)}',
            use_filename=False,
        )
    except Exception as e:
        print('CLOUDINARY SUBMISSION UPLOAD ERROR:', e)
        flash(f'Upload failed: {e}', 'error')
        return redirect(url_for('student.week_detail', slug=slug))

    sub = Submission(
        user_id=current_user.id,
        week_id=week.id,
        title=title or file.filename,
        comment=comment,
        file_url=result.get('secure_url'),
        file_name=file.filename,
        file_format=ext,
    )
    db.session.add(sub)
    db.session.commit()
    flash('Work submitted! Your teacher can now see it.', 'success')
    return redirect(url_for('student.week_detail', slug=slug))

# ── Quiz flow ──────────────────────────────────────────────────────────────────
@student_bp.route('/quiz/<slug>/start', methods=['POST'])
@login_required
@student_required
def start_quiz(slug):
    week = Week.query.filter_by(slug=slug).first_or_404()
    if not week.is_enabled or not week.questions:
        abort(403)
    attempt = Attempt(user_id=current_user.id, week_id=week.id, total=len(week.questions))
    db.session.add(attempt)
    db.session.commit()
    return redirect(url_for('student.quiz', slug=slug, attempt_id=attempt.id))

@student_bp.route('/quiz/<slug>/<int:attempt_id>')
@login_required
@student_required
def quiz(slug, attempt_id):
    week = Week.query.filter_by(slug=slug).first_or_404()
    attempt = Attempt.query.filter_by(id=attempt_id, user_id=current_user.id).first_or_404()
    if attempt.completed:
        return redirect(url_for('student.results', attempt_id=attempt_id))
    questions = week.questions
    answered = {a.question_id: a for a in attempt.answers}

    questions_json = [
        {
            'id': q.id,
            'text': q.text,
            'qtype': q.qtype or 'mcq',
            'topic': q.topic,
            'section': q.section,
            'explanation': q.explanation,
        }
        for q in questions
    ]
    options_json = {
        str(q.id): [{'id': o.id, 'text': o.text} for o in q.options]
        for q in questions
    }
    answered_json = {}
    for qid, a in answered.items():
        q = a.question
        correct_ids = [o.id for o in q.options if o.is_correct]
        answered_json[str(qid)] = {
            'qtype': q.qtype or 'mcq',
            'chosen_id': a.option_id,
            'chosen_ids': [int(x) for x in a.selected_option_ids.split(',')] if a.selected_option_ids else [],
            'text_answer': a.text_answer,
            'is_correct': a.is_correct,
            'pending': a.pending,
            'correct_id': correct_ids[0] if (q.qtype or 'mcq') == 'mcq' and correct_ids else None,
            'correct_ids': correct_ids,
            'explanation': q.explanation,
        }

    return render_template('student/quiz.html', week=week, attempt=attempt,
                           questions=questions, questions_json=questions_json,
                           options_json=options_json, answered_json=answered_json)

@student_bp.route('/quiz/answer', methods=['POST'])
@login_required
@student_required
def submit_answer():
    data = request.get_json()
    attempt_id = data.get('attempt_id')
    question_id = data.get('question_id')

    attempt = Attempt.query.filter_by(id=attempt_id, user_id=current_user.id).first_or_404()
    if attempt.completed:
        return jsonify({'error': 'Attempt already completed'}), 400

    existing = Answer.query.filter_by(attempt_id=attempt_id, question_id=question_id).first()
    if existing:
        return jsonify({'error': 'Already answered'}), 400

    question = Question.query.get_or_404(question_id)
    qtype = question.qtype or 'mcq'
    correct_ids = [o.id for o in question.options if o.is_correct]

    if qtype == 'mcq':
        option_id = data.get('option_id')
        option = Option.query.get(option_id)
        is_correct = bool(option and option.is_correct)
        answer = Answer(attempt_id=attempt_id, question_id=question_id,
                        option_id=option_id, is_correct=is_correct, pending=False)
        if is_correct:
            attempt.score += 1
        db.session.add(answer)
        db.session.commit()
        return jsonify({'qtype': 'mcq', 'is_correct': is_correct,
                        'correct_id': correct_ids[0] if correct_ids else None,
                        'explanation': question.explanation})

    elif qtype == 'multi':
        chosen_ids = data.get('option_ids') or []
        chosen_ids = [int(x) for x in chosen_ids]
        is_correct = set(chosen_ids) == set(correct_ids) and len(chosen_ids) > 0
        answer = Answer(attempt_id=attempt_id, question_id=question_id,
                        selected_option_ids=','.join(str(x) for x in chosen_ids),
                        is_correct=is_correct, pending=False)
        if is_correct:
            attempt.score += 1
        db.session.add(answer)
        db.session.commit()
        return jsonify({'qtype': 'multi', 'is_correct': is_correct,
                        'correct_ids': correct_ids,
                        'explanation': question.explanation})

    else:  # text
        text_answer = (data.get('text_answer') or '').strip()
        if not text_answer:
            return jsonify({'error': 'Answer cannot be empty'}), 400
        answer = Answer(attempt_id=attempt_id, question_id=question_id,
                        text_answer=text_answer, is_correct=False, pending=True)
        db.session.add(answer)
        db.session.commit()
        return jsonify({'qtype': 'text', 'pending': True,
                        'explanation': None})

@student_bp.route('/quiz/complete', methods=['POST'])
@login_required
@student_required
def complete_quiz():
    data = request.get_json()
    attempt_id = data.get('attempt_id')
    attempt = Attempt.query.filter_by(id=attempt_id, user_id=current_user.id).first_or_404()
    attempt.completed = True
    attempt.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'redirect': url_for('student.results', attempt_id=attempt_id)})

@student_bp.route('/results/<int:attempt_id>')
@login_required
@student_required
def results(attempt_id):
    attempt = Attempt.query.filter_by(id=attempt_id, user_id=current_user.id).first_or_404()
    if not attempt.completed:
        return redirect(url_for('student.quiz', slug=attempt.week.slug, attempt_id=attempt_id))
    answers = {a.question_id: a for a in attempt.answers}
    questions = attempt.week.questions
    pending_count = sum(1 for a in attempt.answers if a.pending)
    pct = round(attempt.score / attempt.total * 100) if attempt.total else 0
    return render_template('student/results.html', attempt=attempt, answers=answers,
                           questions=questions, pct=pct, pending_count=pending_count)

@student_bp.route('/my-progress')
@login_required
@student_required
def my_progress():
    weeks = Week.query.filter_by(is_enabled=True).order_by(Week.week_number).all()
    progress = []
    for week in weeks:
        attempts = Attempt.query.filter_by(user_id=current_user.id, week_id=week.id, completed=True)\
            .order_by(Attempt.completed_at.desc()).all()
        best = max(attempts, key=lambda a: a.score) if attempts else None
        progress.append({'week': week, 'attempts': attempts, 'best': best})
    return render_template('student/progress.html', progress=progress)
