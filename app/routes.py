# mentor_connect_ngo_enhanced/app/routes.py
from flask import Blueprint, render_template, url_for, flash, redirect, request, abort, jsonify, current_app # Import current_app
from flask_login import login_user, current_user, logout_user, login_required
from app import db, mail # Import db and mail
from app.models import User, Message, SessionLog, Resource, Announcement, \
                       Quiz, Question, Option, QuizAttempt, QuizAnswer, StudentResourceCompletion
from app.forms import (
    RegistrationForm, LoginForm, UserManagementForm, SetPasswordForm,
    MessageForm, AnnouncementForm, SessionLogForm, ResourceForm,
    UserSearchFilterForm, QuizForm, QuizAttemptForm # New forms
)
import functools
from sqlalchemy import or_, and_, func
from flask_mail import Message as MailMessage # Rename to avoid conflict with models.Message
from threading import Thread
import requests # For Gemini API calls
import json # For handling JSON responses from Gemini API
from datetime import datetime, date, timedelta # For heatmap and streaks
import os # Import os to access environment variables
from flask_wtf.csrf import CSRFProtect # Import CSRFProtect

# Initialize CSRF protection (if not already done globally in __init__.py)
# If you have CSRFProtect(app) in __init__.py, you don't need this line.
# If you're setting it up per blueprint, you would do it here.
# For simplicity, assuming it's either global or you intend to add it to forms.

main = Blueprint('main', __name__)

# Function to send email in a background thread
def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            print(f"Email sent successfully to {msg.recipients}")
        except Exception as e:
            print(f"Error sending email: {e}")

def send_email(subject, recipients, text_body, html_body=None):
    # Get current Flask app instance for context
    app = current_app._get_current_object() # Use current_app to get the current app object safely
    msg = MailMessage(subject, recipients=recipients)
    msg.body = text_body
    if html_body:
        msg.html = html_body
    
    # Send email in a separate thread to avoid blocking the web request
    Thread(target=send_async_email, args=(app, msg)).start()


# --- Helper for Role-Based Access Control ---
def role_required(role):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'info')
                return redirect(url_for('main.login', next=request.url))
            if role == 'admin' and not current_user.is_admin():
                flash('You do not have permission to access this page.', 'danger')
                abort(403)
            elif role == 'mentor' and not (current_user.is_mentor() or current_user.is_admin()):
                flash('You do not have permission to access this page.', 'danger')
                abort(403)
            elif role == 'student' and not (current_user.is_student() or current_user.is_admin()):
                flash('You do not have permission to access this page.', 'danger')
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# --- Public Routes ---

@main.route("/")
@main.route("/home")
def home():
    if current_user.is_authenticated:
        # Update last_login and last_activity
        current_user.last_login = datetime.utcnow()
        current_user.last_activity = datetime.utcnow()
        db.session.commit() # Commit this change

        if current_user.is_admin():
            return redirect(url_for('main.admin_dashboard'))
        elif current_user.is_mentor():
            return redirect(url_for('main.mentor_dashboard'))
        elif current_user.is_student():
            return redirect(url_for('main.student_dashboard'))
    return render_template('index.html', title='Welcome')

@main.route("/about")
def about():
    return render_template('about.html', title='About Us')

@main.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('You are already logged in!', 'info')
        return redirect(url_for('main.home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, role='student')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Register', form=form)

@main.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('You are already logged in!', 'info')
        return redirect(url_for('main.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            # Update last_login on successful login
            user.last_login = datetime.utcnow()
            user.last_activity = datetime.utcnow()
            db.session.commit()

            next_page = request.args.get('next')
            flash(f'Login successful! Welcome, {user.username}.', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash('Login Unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html', title='Login', form=form)

@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.home'))

# --- User Profile Route (Common for all roles to view) ---
@main.route("/profile/<string:username>")
@login_required
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # Update last_activity if current user is viewing their own profile
    if current_user.is_authenticated and current_user.id == user.id:
        user.last_activity = datetime.utcnow()
        db.session.commit()

    # LeetCode-like profile enhancements for student users
    quiz_scores = []
    total_possible_score = 0
    modules_completed_count = user.resource_completions.count() # Count completed resources
    
    # Get total number of resources for calculation
    total_resources = Resource.query.count()

    if user.is_student():
        # Calculate total possible score from all quizzes
        all_quizzes = Quiz.query.all()
        for quiz in all_quizzes:
            total_possible_score += quiz.questions.count() # Each question assumed to be 1 point

        # Get scores for quizzes attempted by this student
        quiz_attempts = user.quiz_attempts.order_by(QuizAttempt.attempt_date.desc()).all()
        for attempt in quiz_attempts:
            quiz_scores.append({
                'quiz_title': attempt.quiz.title,
                'score': attempt.score,
                'total': attempt.total_questions,
                'percentage': (attempt.score / attempt.total_questions * 100) if attempt.total_questions else 0
            })
    
    # Prepare data for heatmap
    heatmap_data = {}
    today = date.today()
    for i in range(365):
        d = today - timedelta(days=i)
        heatmap_data[d.isoformat()] = 0

    login_dates_query = db.session.query(User.last_login).filter(User.id == user.id, User.last_login != None).all()
    resource_completion_dates_query = db.session.query(StudentResourceCompletion.completed_at).filter(StudentResourceCompletion.student_id == user.id).all()
    quiz_attempt_dates_query = db.session.query(QuizAttempt.attempt_date).filter(QuizAttempt.student_id == user.id).all()

    for row in login_dates_query:
        if row.last_login:
            day_str = row.last_login.date().isoformat()
            heatmap_data[day_str] = heatmap_data.get(day_str, 0) + 1

    for row in resource_completion_dates_query:
        if row.completed_at:
            day_str = row.completed_at.date().isoformat()
            heatmap_data[day_str] = heatmap_data.get(day_str, 0) + 1

    for row in quiz_attempt_dates_query:
        if row.attempt_date:
            day_str = row.attempt_date.date().isoformat()
            heatmap_data[day_str] = heatmap_data.get(day_str, 0) + 1

    processed_heatmap_data = []
    for d_str, count in heatmap_data.items():
        d_obj = date.fromisoformat(d_str)
        if d_obj >= (today - timedelta(days=364)) and d_obj <= today:
             processed_heatmap_data.append({'date': d_str, 'value': count})
    
    login_streak = user.calculate_streak()

    return render_template('user_profile.html', user=user, title=f"{user.username}'s Profile",
                           quiz_scores=quiz_scores,
                           total_possible_score=total_possible_score,
                           modules_completed_count=modules_completed_count,
                           total_resources=total_resources,
                           heatmap_data=json.dumps(processed_heatmap_data),
                           login_streak=login_streak)


# --- Admin Routes ---

@main.route("/admin/dashboard")
@role_required('admin')
def admin_dashboard():
    total_users = User.query.count()
    total_mentors = User.query.filter_by(role='mentor').count()
    total_students = User.query.filter_by(role='student').count()
    assigned_students = User.query.filter(User.role == 'student').filter(User.mentor_id != None).count()
    total_sessions = SessionLog.query.count()
    total_resources = Resource.query.count()
    total_quizzes = Quiz.query.count()
    
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).limit(5).all()

    return render_template('admin_dashboard.html', title='Admin Dashboard',
                           total_users=total_users,
                           total_mentors=total_mentors,
                           total_students=total_students,
                           assigned_students=assigned_students,
                           total_sessions=total_sessions,
                           total_resources=total_resources,
                           total_quizzes=total_quizzes,
                           announcements=announcements)

@main.route("/admin/users", methods=['GET', 'POST'])
@role_required('admin')
def manage_users():
    form = UserSearchFilterForm()
    users_query = User.query.order_by(User.username)

    if form.validate_on_submit():
        search_query = form.search_query.data
        filter_role = form.filter_role.data
        filter_mentor_assigned = form.filter_mentor_assigned.data

        if search_query:
            users_query = users_query.filter(or_(
                User.username.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%')
            ))
        if filter_role:
            users_query = users_query.filter_by(role=filter_role)
        if filter_mentor_assigned == 'assigned':
            users_query = users_query.filter(User.role == 'student').filter(User.mentor_id != None)
        elif filter_mentor_assigned == 'unassigned':
            users_query = users_query.filter(User.role == 'student').filter(User.mentor_id == None)
        
        users = users_query.all()
        flash('Filters applied.', 'info')
    else:
        users = users_query.all()

    return render_template('manage_users.html', title='Manage Users', users=users, form=form)

@main.route("/admin/user/new", methods=['GET', 'POST'])
@role_required('admin')
def create_user():
    form = UserManagementForm()
    mentors = User.query.filter_by(role='mentor').order_by(User.username).all()
    form.mentor_id.choices = [(m.id, m.username) for m in mentors]
    form.mentor_id.choices.insert(0, ('', 'No Mentor Assigned'))

    if form.validate_on_submit():
        temp_password = 'password123'
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data,
            bio=form.bio.data,
            expertise_areas=form.expertise_areas.data,
            contact_preference=form.contact_preference.data
        )
        user.set_password(temp_password)

        if form.role.data == 'student' and form.mentor_id.data is not None:
            user.mentor_id = form.mentor_id.data
        else:
            user.mentor_id = None

        db.session.add(user)
        db.session.commit()
        flash(f'User "{user.username}" created with role "{user.role}". Please advise them to log in with temporary password and change it.', 'success')
        return redirect(url_for('main.manage_users'))

    return render_template('create_edit_user.html', title='Create New User', form=form, legend='Create New User')

@main.route("/admin/user/<int:user_id>/edit", methods=['GET', 'POST'])
@role_required('admin')
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserManagementForm(original_username=user.username, original_email=user.email)

    mentors = User.query.filter(User.role == 'mentor', User.id != user_id).order_by(User.username).all()
    form.mentor_id.choices = [(m.id, m.username) for m in mentors]
    form.mentor_id.choices.insert(0, ('', 'No Mentor Assigned'))

    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data
        user.bio = form.bio.data
        user.expertise_areas = form.expertise_areas.data
        user.contact_preference = form.contact_preference.data

        if form.role.data == 'student' and form.mentor_id.data is not None:
            user.mentor_id = form.mentor_id.data
        else:
            user.mentor_id = None

        db.session.commit()
        flash(f'User "{user.username}" updated!', 'success')
        return redirect(url_for('main.manage_users'))
    elif request.method == 'GET':
        form.username.data = user.username
        form.email.data = user.email
        form.role.data = user.role
        form.bio.data = user.bio
        form.expertise_areas.data = user.expertise_areas
        form.contact_preference.data = user.contact_preference
        form.mentor_id.data = user.mentor_id

    suggested_mentors = []
    if user.is_student() and user.expertise_areas:
        student_interests = set(item.strip().lower() for item in user.expertise_areas.split(',') if item.strip())
        all_mentors = User.query.filter_by(role='mentor').all()
        mentor_scores = []
        for mentor in all_mentors:
            if mentor.expertise_areas:
                mentor_expertise = set(item.strip().lower() for item in mentor.expertise_areas.split(',') if item.strip())
                score = len(student_interests.intersection(mentor_expertise))
                if score > 0:
                    mentor_scores.append((score, mentor))
        mentor_scores.sort(key=lambda x: x[0], reverse=True)
        suggested_mentors = [m for score, m in mentor_scores[:5]]

    return render_template('create_edit_user.html', title='Edit User', form=form,
                           legend='Edit User Details', user=user, suggested_mentors=suggested_mentors)

@main.route("/admin/user/<int:user_id>/set_password", methods=['GET', 'POST'])
@role_required('admin')
def set_user_password(user_id):
    user = User.query.get_or_404(user_id)
    form = SetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash(f'Password for "{user.username}" has been updated.', 'success')
        return redirect(url_for('main.manage_users'))
    return render_template('set_password.html', title='Set Password', form=form, user=user)

@main.route("/admin/user/<int:user_id>/delete", methods=['POST'])
@role_required('admin')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own admin account!', 'danger')
        return redirect(url_for('main.manage_users'))
    
    if user.is_mentor():
        students_to_unassign = User.query.filter_by(mentor_id=user.id).all()
        for student in students_to_unassign:
            student.mentor_id = None
            db.session.add(student)
        db.session.commit()

    db.session.delete(user)
    db.session.commit()
    flash(f'User "{user.username}" has been deleted.', 'success')
    return redirect(url_for('main.manage_users'))

# Announcement Management (Admin)
@main.route("/admin/announcements/new", methods=['GET', 'POST'])
@role_required('admin')
def create_announcement():
    form = AnnouncementForm()
    if form.validate_on_submit():
        announcement = Announcement(title=form.title.data, content=form.content.data, admin=current_user)
        db.session.add(announcement)
        db.session.commit()
        flash('Announcement posted!', 'success')

        # Send email notification to all users
        all_users = User.query.all()
        recipients = [user.email for user in all_users]
        subject = f"New Announcement: {announcement.title}"
        text_body = f"Hello,\n\nA new announcement has been posted on MentorConnect:\n\nTitle: {announcement.title}\nContent: {announcement.content}\n\nView it here: {url_for('main.home', _external=True)}\n\nBest regards,\nThe MentorConnect Team"
        html_body = render_template('emails/announcement_email.html', announcement=announcement)
        send_email(subject, recipients, text_body, html_body)

        return redirect(url_for('main.admin_dashboard'))
    return render_template('create_announcement.html', title='New Announcement', form=form, legend='New Announcement')

@main.route("/admin/announcements")
@role_required('admin')
def manage_announcements():
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()
    return render_template('manage_announcements.html', title='Manage Announcements', announcements=announcements)

@main.route("/admin/announcement/<int:announcement_id>/delete", methods=['POST'])
@role_required('admin')
def delete_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    db.session.delete(announcement)
    db.session.commit()
    flash('Announcement deleted.', 'success')
    return redirect(url_for('main.manage_announcements'))

# Resource Management (Admin/Mentor)
@main.route("/resources/new", methods=['GET', 'POST'])
@role_required('mentor')
def create_resource():
    form = ResourceForm()
    if form.validate_on_submit():
        resource = Resource(
            title=form.title.data,
            description=form.description.data,
            link_url=form.link_url.data,
            category=form.category.data,
            creator=current_user
        )
        db.session.add(resource)
        db.session.commit()
        flash('Resource added successfully!', 'success')
        return redirect(url_for('main.view_resources'))
    return render_template('create_edit_resource.html', title='Add New Resource', form=form, legend='Add New Resource')

@main.route("/resources")
@login_required
def view_resources():
    category_filter = request.args.get('category')
    resources_query = Resource.query.order_by(Resource.date_added.desc())

    if category_filter and category_filter != 'All':
        resources_query = resources_query.filter_by(category=category_filter)

    resources = resources_query.all()
    categories = sorted(list(set([r.category for r in Resource.query.all() if r.category])))
    
    completed_resource_ids = []
    if current_user.is_authenticated:
        completed_resource_ids = [comp.resource_id for comp in current_user.resource_completions.all()]

    return render_template('resources.html', title='Learning Resources', resources=resources, categories=categories, selected_category=category_filter,
                           completed_resource_ids=completed_resource_ids)

@main.route("/resource/<int:resource_id>/mark_complete", methods=['POST'])
@login_required
@role_required('student')
def mark_resource_complete(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    
    existing_completion = StudentResourceCompletion.query.filter_by(
        student_id=current_user.id,
        resource_id=resource.id
    ).first()

    if existing_completion:
        flash(f'You have already marked "{resource.title}" as complete!', 'info')
    else:
        completion = StudentResourceCompletion(student_id=current_user.id, resource_id=resource.id)
        db.session.add(completion)
        current_user.last_activity = datetime.utcnow()
        db.session.commit()
        flash(f'Resource "{resource.title}" marked as complete!', 'success')

    return redirect(url_for('main.view_resources'))


@main.route("/resource/<int:resource_id>/edit", methods=['GET', 'POST'])
@role_required('mentor')
def edit_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    if resource.creator != current_user and not current_user.is_admin():
        abort(403)
    form = ResourceForm()
    if form.validate_on_submit():
        resource.title = form.title.data
        resource.description = form.description.data
        resource.link_url = form.link_url.data
        resource.category = form.category.data
        db.session.commit()
        flash('Resource updated successfully!', 'success')
        return redirect(url_for('main.view_resources'))
    elif request.method == 'GET':
        form.title.data = resource.title
        form.description.data = resource.description
        form.link_url.data = resource.link_url
        form.category.data = resource.category
    return render_template('create_edit_resource.html', title='Edit Resource', form=form, legend='Edit Resource')

@main.route("/resource/<int:resource_id>/delete", methods=['POST'])
@role_required('mentor')
def delete_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    if resource.creator != current_user and not current_user.is_admin():
        abort(403)
    db.session.delete(resource)
    db.session.commit()
    flash('Resource deleted successfully!', 'success')
    return redirect(url_for('main.view_resources'))


# --- Mentor Routes ---

@main.route("/mentor/dashboard")
@role_required('mentor')
def mentor_dashboard():
    students = current_user.students.order_by(User.username).all()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).limit(5).all()
    recent_sessions = current_user.sessions_logged_as_mentor.order_by(SessionLog.session_date.desc()).limit(5).all()

    my_quizzes = current_user.quizzes_created.order_by(Quiz.date_created.desc()).all()

    return render_template('mentor_dashboard.html', title='Mentor Dashboard',
                           students=students, announcements=announcements,
                           recent_sessions=recent_sessions, my_quizzes=my_quizzes)

@main.route("/mentor/log_session/<int:student_id>", methods=['GET', 'POST'])
@login_required
def log_session(student_id):
    student = User.query.get_or_404(student_id)
    if student.assigned_mentor != current_user and not current_user.is_admin():
        flash('You are not authorized to log sessions for this student.', 'danger')
        return redirect(url_for('main.mentor_dashboard'))

    form = SessionLogForm()
    form.student_id.choices = [(student.id, student.username)]
    form.student_id.data = student.id

    if form.validate_on_submit():
        session_log = SessionLog(
            mentor_id=current_user.id,
            student_id=form.student_id.data,
            duration_minutes=form.duration_minutes.data,
            topics_discussed=form.topics_discussed.data,
            progress_notes=form.progress_notes.data
        )
        db.session.add(session_log)
        current_user.last_activity = datetime.utcnow()
        student.last_activity = datetime.utcnow()
        db.session.commit()
        flash(f'Session with {student.username} logged successfully!', 'success')
        return redirect(url_for('main.mentor_dashboard'))
    
    return render_template('log_session.html', title=f'Log Session for {student.username}', form=form, student=student)

@main.route("/mentor/sessions/<int:student_id>")
@role_required('mentor')
def student_sessions(student_id):
    student = User.query.get_or_404(student_id)
    if student.assigned_mentor != current_user and not current_user.is_admin():
        flash('You are not authorized to view sessions for this student.', 'danger')
        abort(403)
    
    sessions = SessionLog.query.filter_by(student_id=student.id).order_by(SessionLog.session_date.desc()).all()
    return render_template('student_sessions.html', title=f'Sessions for {student.username}', student=student, sessions=sessions)


# --- Quiz Management (Mentor) ---
@main.route("/mentor/quizzes/new", methods=['GET', 'POST'])
@role_required('mentor')
def create_quiz():
    form = QuizForm()
    if form.validate_on_submit():
        quiz = Quiz(title=form.title.data, description=form.description.data, creator=current_user)
        db.session.add(quiz)
        db.session.commit()

        for q_form in form.questions.entries:
            question = Question(quiz_id=quiz.id, question_text=q_form.question_text.data, question_type=q_form.question_type.data)
            db.session.add(question)
            db.session.commit()

            for opt_form in q_form.options.entries:
                option = Option(question_id=question.id, option_text=opt_form.option_text.data, is_correct=opt_form.is_correct.data)
                db.session.add(option)
            db.session.commit()
        
        current_user.last_activity = datetime.utcnow()
        db.session.commit()
        flash(f'Quiz "{quiz.title}" created successfully!', 'success')
        return redirect(url_for('main.mentor_dashboard'))
    return render_template('create_quiz.html', title='Create New Quiz', form=form, legend='Create New Quiz')

@main.route("/mentor/quizzes/<int:quiz_id>/edit", methods=['GET', 'POST'])
@role_required('mentor')
def edit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.creator != current_user and not current_user.is_admin():
        abort(403)

    form = QuizForm(obj=quiz)

    if request.method == 'POST':
        for q in quiz.questions.all():
            db.session.delete(q)
        db.session.commit()

        form.populate_obj(quiz)
        quiz.questions = []

        for q_form in form.questions.entries:
            question = Question(quiz_id=quiz.id, question_text=q_form.question_text.data, question_type=q_form.question_type.data)
            db.session.add(question)
            db.session.flush()

            for opt_form in q_form.options.entries:
                option = Option(question_id=question.id, option_text=opt_form.option_text.data, is_correct=opt_form.is_correct.data)
                db.session.add(option)
        db.session.commit()
        
        current_user.last_activity = datetime.utcnow()
        db.session.commit()
        flash(f'Quiz "{quiz.title}" updated successfully!', 'success')
        return redirect(url_for('main.mentor_dashboard'))

    return render_template('create_quiz.html', title='Edit Quiz', form=form, legend='Edit Quiz', quiz=quiz)


@main.route("/mentor/quizzes/<int:quiz_id>/delete", methods=['POST'])
@role_required('mentor')
def delete_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.creator != current_user and not current_user.is_admin():
        abort(403)
    db.session.delete(quiz)
    db.session.commit()
    flash(f'Quiz "{quiz.title}" deleted.', 'success')
    return redirect(url_for('main.mentor_dashboard'))

@main.route("/mentor/quizzes/<int:quiz_id>/results")
@role_required('mentor')
def quiz_results(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.creator != current_user and not current_user.is_admin():
        abort(403)
    
    attempts = quiz.attempts.order_by(QuizAttempt.attempt_date.desc()).all()
    return render_template('quiz_results.html', title=f'Results for "{quiz.title}"', quiz=quiz, attempts=attempts)


# --- Student Routes ---

@main.route("/student/dashboard")
@role_required('student')
def student_dashboard():
    mentor = None
    if current_user.mentor_id:
        mentor = User.query.get(current_user.mentor_id)

    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).limit(5).all()
    recent_sessions = current_user.sessions_as_student.order_by(SessionLog.session_date.desc()).limit(5).all()

    available_quizzes = Quiz.query.order_by(Quiz.date_created.desc()).all()
    
    attempted_quiz_ids = {attempt.quiz_id for attempt in current_user.quiz_attempts.all()}
    
    return render_template('student_dashboard.html', title='Student Dashboard',
                           mentor=mentor, announcements=announcements, recent_sessions=recent_sessions,
                           available_quizzes=available_quizzes, attempted_quiz_ids=attempted_quiz_ids)

@main.route("/student/take_quiz/<int:quiz_id>", methods=['GET', 'POST'])
@role_required('student')
def take_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    existing_attempt = QuizAttempt.query.filter_by(quiz_id=quiz.id, student_id=current_user.id).first()
    if existing_attempt:
        flash(f'You have already attempted "{quiz.title}". You can view your results.', 'info')
        return redirect(url_for('main.view_quiz_attempt', attempt_id=existing_attempt.id))

    form = QuizAttemptForm(quiz_id=quiz.id)

    for question in quiz.questions.all():
        if question.question_type == 'multiple_choice':
            choices = [(str(option.id), option.option_text) for option in question.options.all()]
            setattr(form, f'question_{question.id}', SelectField(question.question_text, choices=choices, validators=[DataRequired()]))

    if form.validate_on_submit():
        new_attempt = QuizAttempt(quiz_id=quiz.id, student_id=current_user.id, total_questions=quiz.questions.count())
        db.session.add(new_attempt)
        db.session.flush()

        score = 0
        for question in quiz.questions.all():
            if question.question_type == 'multiple_choice':
                selected_option_id = request.form.get(f'question_{question.id}')
                if selected_option_id:
                    selected_option = Option.query.get(int(selected_option_id))
                    if selected_option and selected_option.is_correct:
                        score += 1
                    
                    quiz_answer = QuizAnswer(
                        attempt_id=new_attempt.id,
                        question_id=question.id,
                        selected_option_id=selected_option.id
                    )
                    db.session.add(quiz_answer)
        
        new_attempt.score = score
        current_user.last_activity = datetime.utcnow()
        db.session.commit()
        
        flash(f'You completed "{quiz.title}" with a score of {score} out of {new_attempt.total_questions}!', 'success')
        return redirect(url_for('main.view_quiz_attempt', attempt_id=new_attempt.id))

    return render_template('take_quiz.html', title=f'Take Quiz: "{quiz.title}"', quiz=quiz, form=form)

@main.route("/student/quiz_attempts/<int:attempt_id>")
@role_required('student')
def view_quiz_attempt(attempt_id):
    attempt = QuizAttempt.query.get_or_404(attempt_id)
    if attempt.student_id != current_user.id and not current_user.is_admin():
        abort(403)
    
    questions_with_answers = []
    for answer in attempt.answers.all():
        question = answer.question_answered
        selected_option = answer.selected_option
        correct_option = question.options.filter_by(is_correct=True).first()
        
        questions_with_answers.append({
            'question_text': question.question_text,
            'selected_option_text': selected_option.option_text if selected_option else "No answer",
            'is_correct': (selected_option and selected_option.is_correct),
            'correct_option_text': correct_option.option_text if correct_option else "N/A"
        })

    return render_template('view_quiz_attempt.html', title=f'Quiz Results: "{attempt.quiz.title}"',
                           attempt=attempt, questions_with_answers=questions_with_answers)


# --- Messaging Routes ---

@main.route("/messages/<int:other_user_id>", methods=['GET', 'POST'])
@login_required
def messages(other_user_id):
    other_user = User.query.get_or_404(other_user_id)

    if not (current_user.is_admin() or
            (current_user.is_mentor() and other_user.assigned_mentor == current_user) or
            (current_user.is_student() and other_user == current_user.assigned_mentor) or
            (current_user.id == other_user_id)):
        flash('You are not authorized to message this user.', 'danger')
        abort(403)

    form = MessageForm()
    if form.validate_on_submit():
        message = Message(sender=current_user, receiver=other_user, content=form.content.data)
        db.session.add(message)
        current_user.last_activity = datetime.utcnow()
        other_user.last_activity = datetime.utcnow()
        db.session.commit()
        return redirect(url_for('main.messages', other_user_id=other_user.id))

    messages_query = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp).all()

    message_data = [
        {
            'sender_username': msg.sender.username,
            'receiver_username': msg.receiver.username,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_current_user_sender': msg.sender_id == current_user.id
        }
        for msg in messages_query
    ]
    return jsonify(message_data)

@main.route("/api/messages/<int:other_user_id>")
@login_required
def get_messages_api(other_user_id):
    other_user = User.query.get_or_404(other_user_id)

    if not (current_user.is_admin() or
            (current_user.is_mentor() and other_user.assigned_mentor == current_user) or
            (current_user.is_student() and other_user == current_user.assigned_mentor) or
            (current_user.id == other_user_id)):
        return jsonify({"error": "Unauthorized"}), 403

    messages_query = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp).all()

    message_data = [
        {
            'sender_username': msg.sender.username,
            'receiver_username': msg.receiver.username,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_current_user_sender': msg.sender_id == current_user.id
        }
        for msg in messages_query
    ]
    return jsonify(message_data)

# --- Chatbot Integration ---
@main.route("/chatbot", methods=['GET'])
@login_required
def chatbot_page():
    return render_template('chatbot.html', title='AI Chatbot')

@main.route("/api/chatbot", methods=['POST'])
@login_required
def chatbot_api():
    # Your JavaScript is sending 'message' in the body
    user_message = request.json.get('message')
    
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    current_user.last_activity = datetime.utcnow()
    db.session.commit()

    try:
        apiKey = os.getenv("GEMINI_API_KEY") 
        if not apiKey:
            print("Error: GEMINI_API_KEY environment variable not set.")
            return jsonify({"error": "AI service not configured. Please contact support."}), 500

        chatHistory = []
        # Add a system instruction to encourage a natural, concise, and helpful tone.
        system_instruction = "If you get user query as Hi then respond friendly like Hi back. You are a friendly, concise, and natural learning assistant. Respond directly and helpfully. Always use Markdown for formatting (lists, bolding, paragraphs) as appropriate. Avoid explicitly stating that you are using Markdown or that you are 'ready to assist'. Focus on delivering information clearly and directly related to the user's query about learning, courses, or general doubts in the context of MentorConnect."
        
        chatHistory.append({ "role": "user", "parts": [{ "text": system_instruction + "\n\n" + user_message }] })
        
        payload = { "contents": chatHistory }
        
        apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={apiKey}"
        
        print(f"Sending message to Gemini: {user_message}") # Debugging print
        response = requests.post(apiUrl, headers={'Content-Type': 'application/json'}, json=payload)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        
        result = response.json()
        print(f"Received response from Gemini: {result}") # Debugging print
        
        if result.get('candidates') and result['candidates'][0].get('content') and result['candidates'][0]['content'].get('parts'):
            bot_response = result['candidates'][0]['content']['parts'][0]['text']
        else:
            bot_response = "I'm sorry, I couldn't generate a response. The AI might have returned an empty or malformed response."
            print(f"Gemini API returned unexpected structure: {result}")
            
        return jsonify({"response": bot_response})

    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        return jsonify({"error": f"Failed to connect to the AI service: {str(e)}"}), 500
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from Gemini API: {e}")
        return jsonify({"error": f"Invalid response from AI service: {str(e)}"}), 500
    except ValueError as e:
        print(f"Configuration error: {e}")
        return jsonify({"error": f"Configuration error: {str(e)}. Please ensure GEMINI_API_KEY is set in your .env file."}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
