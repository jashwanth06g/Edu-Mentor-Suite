# mentor_connect_ngo_enhanced/app/models.py
from datetime import datetime, date, timedelta
from app import db, bcrypt
from flask_login import UserMixin
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy import func, case

# User model representing all users (Admin, Mentor, Student)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='student') # 'admin', 'mentor', 'student'

    # Extended User Profile fields
    bio = db.Column(db.Text, nullable=True)
    expertise_areas = db.Column(db.String(200), nullable=True)
    contact_preference = db.Column(db.String(50), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True) # For streak and heatmap
    last_activity = db.Column(db.DateTime, nullable=True) # For general activity tracking

    # Self-referencing foreign key for mentor-student relationship
    mentor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    students = db.relationship('User', foreign_keys=[mentor_id], backref=db.backref('assigned_mentor', remote_side=[id]), lazy='dynamic')

    # Relationships for In-App Messaging
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')

    # Relationship for Session Logging: sessions where THIS user is the mentor (i.e., this user is the CREATOR of the log)
    sessions_logged_as_mentor = db.relationship(
        'SessionLog',
        foreign_keys='SessionLog.mentor_id',
        backref='mentor_of_session',
        lazy='dynamic'
    )

    # Relationship for resources created by this user (Admins/Mentors)
    created_resources = db.relationship('Resource', backref='creator', lazy='dynamic')

    # New: Relationships for Quiz Management
    quizzes_created = db.relationship('Quiz', backref='creator', lazy='dynamic')

    # New: Relationship for Student Resource Completion
    resource_completions = db.relationship('StudentResourceCompletion', backref='student_user', lazy='dynamic')

    # New: Relationship for Quiz Attempts by a student
    quiz_attempts = db.relationship('QuizAttempt', backref='student_user', lazy='dynamic')


    def __repr__(self):
        return f"User('{self.username}', '{self.email}', Role: '{self.role}')"

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

    def is_admin(self):
        return self.role == 'admin'

    def is_mentor(self):
        return self.role == 'mentor'

    def is_student(self):
        return self.role == 'student'

    # Hybrid property for daily activity for heatmap
    @hybrid_property
    def daily_activity_dates(self):
        # Combines login dates, resource completion dates, and quiz attempt dates
        login_dates = [self.last_login.date()] if self.last_login else []
        resource_dates = [rc.completed_at.date() for rc in self.resource_completions.all()]
        quiz_dates = [qa.attempt_date.date() for qa in self.quiz_attempts.all()]
        
        all_dates = sorted(list(set(login_dates + resource_dates + quiz_dates)))
        
        # Aggregate counts per day
        activity_counts = {}
        for d in all_dates:
            activity_counts[d.isoformat()] = activity_counts.get(d.isoformat(), 0) + 1 # Simple count, can be weighted

        return activity_counts

    @daily_activity_dates.expression
    def daily_activity_dates(cls):
        # This is complex to do purely in SQLAlchemy for aggregation like this,
        # often easier to fetch raw data and process in Python for heatmap.
        # For a heatmap, we'll retrieve all relevant timestamps and process in Python.
        return case(
            [(cls.id != None, None)], # Placeholder, calculation happens in Python
            else_=None
        )


    def calculate_streak(self):
        """Calculates the current consecutive daily activity streak."""
        activity_dates_str = self.daily_activity_dates # This will call the hybrid property to get processed dates
        if not activity_dates_str:
            return 0

        # Convert date strings back to date objects for comparison
        all_dates = sorted([datetime.fromisoformat(d).date() for d in activity_dates_str.keys()])

        if not all_dates:
            return 0

        today = date.today()
        # Check if today or yesterday had activity
        has_today_activity = today in all_dates
        has_yesterday_activity = (today - timedelta(days=1)) in all_dates

        if not has_today_activity and not has_yesterday_activity:
            return 0 # No activity today or yesterday, streak broken

        streak = 0
        current_date = today if has_today_activity else (today - timedelta(days=1))

        # Check if the most recent activity is today or yesterday
        if current_date not in all_dates: # This might happen if last activity was older
            return 0

        # Iterate backward from the most recent active day
        for i in range(len(all_dates) - 1, -1, -1):
            if all_dates[i] == current_date:
                streak += 1
                current_date -= timedelta(days=1)
            elif all_dates[i] < current_date:
                # If there's a gap or we've gone past the expected previous day, break
                if all_dates[i] != (current_date + timedelta(days=1)): # Check for exact previous day
                     break
                else: # Consecutive day, continue
                    streak += 1
                    current_date -= timedelta(days=1)
            else: # Future date or already counted, skip
                continue

        return streak


# Message model for in-app messaging
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"Message(From: '{self.sender.username}', To: '{self.receiver.username}', Time: '{self.timestamp}')"

# Announcement model
class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    admin = db.relationship('User', backref='posted_announcements')

    def __repr__(self):
        return f"Announcement('{self.title}', By: '{self.admin.username}')"

# SessionLog model for mentors to log sessions
class SessionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # FK to the mentor who logged it
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # FK to the student for whom it was logged
    session_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    duration_minutes = db.Column(db.Integer, nullable=True)
    topics_discussed = db.Column(db.Text, nullable=False)
    progress_notes = db.Column(db.Text, nullable=True)

    # Relationship from a SessionLog to the Student User
    # 'foreign_keys' explicitly specifies SessionLog.student_id links to User.id for this relationship.
    # 'backref' creates a 'sessions_as_student' attribute on the User model, showing sessions
    # where that user was the student.
    student = db.relationship(
        'User',
        foreign_keys=[student_id],
        backref=db.backref('sessions_as_student', lazy='dynamic') # <--- FIXED LINE HERE
    )
    # The 'mentor_of_session' relationship on SessionLog is implicitly created by the backref
    # from User.sessions_logged_as_mentor.

    def __repr__(self):
        return f"SessionLog(Mentor: '{self.mentor_of_session.username}', Student: '{self.student.username}', Date: '{self.session_date}')"

# Resource model for curated learning resources
class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    link_url = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Creator of the resource

    # New: relationship to track which students completed this resource
    completions = db.relationship('StudentResourceCompletion', backref='resource_item', lazy='dynamic')

    def __repr__(self):
        return f"Resource('{self.title}', Category: '{self.category}')"

# New Model: StudentResourceCompletion (for tracking which students completed which resources)
class StudentResourceCompletion(db.Model):
    __tablename__ = 'student_resource_completion'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('student_id', 'resource_id', name='_student_resource_uc'),)

    def __repr__(self):
        return f"StudentResourceCompletion(Student: {self.student_id}, Resource: {self.resource_id}, Completed: {self.completed_at})"


# --- New Models for Quizzes ---
class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Mentor who created it
    
    # Relationships
    questions = db.relationship('Question', backref='quiz', lazy='dynamic', cascade='all, delete-orphan')
    attempts = db.relationship('QuizAttempt', backref='quiz', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"Quiz('{self.title}', Creator: '{self.creator.username}')"

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), nullable=False, default='multiple_choice') # 'multiple_choice', 'true_false'
    
    # Relationships
    options = db.relationship('Option', backref='question', lazy='dynamic', cascade='all, delete-orphan')
    answers = db.relationship('QuizAnswer', backref='question_answered', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"Question('{self.question_text[:50]}...')"

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    option_text = db.Column(db.String(200), nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"Option('{self.option_text}', Correct: {self.is_correct})"

class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    attempt_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    score = db.Column(db.Integer, nullable=True) # Could be number of correct answers or percentage
    total_questions = db.Column(db.Integer, nullable=True)

    # Relationships
    answers = db.relationship('QuizAnswer', backref='attempt', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (UniqueConstraint('quiz_id', 'student_id', name='_quiz_student_attempt_uc'),) # Limit one attempt per student per quiz (can be removed for multiple attempts)

    def __repr__(self):
        return f"QuizAttempt(Student: {self.student_user.username}, Quiz: '{self.quiz.title}', Score: {self.score}/{self.total_questions})"

class QuizAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempt.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    # Storing the selected option ID for multiple choice, or text for open-ended
    selected_option_id = db.Column(db.Integer, db.ForeignKey('option.id'), nullable=True)
    # You might also want to store the actual text answer for open-ended questions
    # student_answer_text = db.Column(db.Text, nullable=True) # For future open-ended questions

    __table_args__ = (UniqueConstraint('attempt_id', 'question_id', name='_attempt_question_uc'),)

    def __repr__(self):
        return f"QuizAnswer(Attempt: {self.attempt_id}, Question: {self.question_id}, Selected: {self.selected_option_id})"

