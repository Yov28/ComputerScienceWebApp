from flask import Blueprint, render_template, redirect, url_for, request, jsonify, abort
from flask_login import login_required, current_user
from models import Week, Question, Option, Attempt, Answer
from extensions import db
from datetime import datetime
from functools import wraps

student_bp = Blueprint('student', __name__)

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
    # Get latest attempt per week for this student
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
    return render_template('student/week_detail.html', week=week, questions=questions,
                           slides=slides, past_attempts=past_attempts)

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
            'topic': q.topic,
            'section': q.section,
            'explanation': q.explanation,
        }
        for q in questions
    ]
    options_json = {
        q.id: [{'id': o.id, 'text': o.text} for o in q.options]
        for q in questions
    }

    return render_template('student/quiz.html', week=week, attempt=attempt,
                           questions=questions, questions_json=questions_json,
                           options_json=options_json, answered=answered)

@student_bp.route('/quiz/answer', methods=['POST'])
@login_required
@student_required
def submit_answer():
    data = request.get_json()
    attempt_id = data.get('attempt_id')
    question_id = data.get('question_id')
    option_id = data.get('option_id')

    attempt = Attempt.query.filter_by(id=attempt_id, user_id=current_user.id).first_or_404()
    if attempt.completed:
        return jsonify({'error': 'Attempt already completed'}), 400

    existing = Answer.query.filter_by(attempt_id=attempt_id, question_id=question_id).first()
    if existing:
        return jsonify({'already_answered': True, 'is_correct': existing.is_correct,
                        'correct_option_id': _correct_option_id(question_id),
                        'explanation': existing.question.explanation})

    option = Option.query.get(option_id)
    is_correct = option.is_correct if option else False

    answer = Answer(attempt_id=attempt_id, question_id=question_id,
                    option_id=option_id, is_correct=is_correct)
    db.session.add(answer)

    if is_correct:
        attempt.score += 1
    db.session.commit()

    return jsonify({
        'is_correct': is_correct,
        'correct_option_id': _correct_option_id(question_id),
        'explanation': Question.query.get(question_id).explanation
    })

def _correct_option_id(question_id):
    correct = Option.query.filter_by(question_id=question_id, is_correct=True).first()
    return correct.id if correct else None

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
    pct = round(attempt.score / attempt.total * 100) if attempt.total else 0
    return render_template('student/results.html', attempt=attempt, answers=answers,
                           questions=questions, pct=pct)

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
