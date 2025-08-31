# mentor_connect_ngo_enhanced/app/forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, BooleanField, \
                    TextAreaField, SelectField, IntegerField, FieldList, FormField, HiddenField # Added HiddenField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
from app.models import User # Import User model to check for uniqueness
from flask_login import current_user
from email_validator import validate_email, EmailNotValidError # Import for email validation

# Custom validator for email
def validate_email_address(form, field):
    try:
        validate_email(field.data)
    except EmailNotValidError:
        raise ValidationError('Invalid email address.')

# For Quiz Forms
class OptionForm(FlaskForm):
    option_text = StringField('Option Text', validators=[DataRequired()])
    is_correct = BooleanField('Is Correct?')

class QuestionForm(FlaskForm):
    question_text = TextAreaField('Question Text', validators=[DataRequired()])
    question_type = SelectField('Question Type', choices=[('multiple_choice', 'Multiple Choice')], validators=[DataRequired()]) # Extendable
    options = FieldList(FormField(OptionForm), min_entries=2, max_entries=5) # At least 2 options, max 5

class QuizForm(FlaskForm):
    title = StringField('Quiz Title', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    questions = FieldList(FormField(QuestionForm), min_entries=1) # At least one question
    submit = SubmitField('Create Quiz')


# User Registration Form
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email(), validate_email_address]) # Using custom validator
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is taken. Please choose a different one.')

# User Login Form
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

# Form for managing user roles and mentor assignment by Admin
class UserManagementForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email(), validate_email_address])
    role = SelectField('Role', choices=[('student', 'Student'), ('mentor', 'Mentor'), ('admin', 'Admin')], validators=[DataRequired()])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=500)])
    expertise_areas = StringField('Expertise Areas (comma-separated)', validators=[Optional(), Length(max=200)])
    contact_preference = StringField('Contact Preference', validators=[Optional(), Length(max=50)])
    
    # Custom coerce function for mentor_id
    # It converts an empty string to None, otherwise tries to convert to int.
    # This is crucial for handling the "No Mentor Assigned" option.
    mentor_id = SelectField(
        'Assigned Mentor', 
        choices=[('', 'No Mentor Assigned')], 
        coerce=lambda x: int(x) if x else None,
        validators=[Optional()]
    )
    submit = SubmitField('Save User')

    def __init__(self, original_username=None, original_email=None, *args, **kwargs):
        super(UserManagementForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user:
                raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        if email.data != self.original_email:
            user = User.query.filter_by(email=self.email.data).first()
            if user:
                raise ValidationError('That email is taken. Please choose a different one.')

# Form for setting/resetting user password
class SetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Set Password')

# Form for sending messages
class MessageForm(FlaskForm):
    content = TextAreaField('Message', validators=[DataRequired(), Length(min=1, max=500)])
    submit = SubmitField('Send Message')

# Form for announcements
class AnnouncementForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=2, max=100)])
    content = TextAreaField('Content', validators=[DataRequired()])
    submit = SubmitField('Post Announcement')

# Form for session logging
class SessionLogForm(FlaskForm):
    student_id = SelectField('Student', coerce=int, validators=[DataRequired()])
    duration_minutes = IntegerField('Duration (minutes)', validators=[DataRequired()])
    topics_discussed = TextAreaField('Topics Discussed', validators=[DataRequired()])
    progress_notes = TextAreaField('Progress Notes', validators=[Optional()])
    submit = SubmitField('Log Session')

# Form for resources
class ResourceForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=2, max=150)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    link_url = StringField('Link URL', validators=[Optional(), Length(max=255)])
    category = SelectField('Category', choices=[
        ('Academics', 'Academics'),
        ('Career Development', 'Career Development'),
        ('Life Skills', 'Life Skills'),
        ('Mental Health', 'Mental Health'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    submit = SubmitField('Add Resource')

# Form for searching/filtering users
class UserSearchFilterForm(FlaskForm):
    search_query = StringField('Search (Username or Email)', validators=[Optional()])
    filter_role = SelectField('Filter by Role', choices=[('', 'All Roles'), ('student', 'Student'), ('mentor', 'Mentor'), ('admin', 'Admin')], validators=[Optional()])
    filter_mentor_assigned = SelectField('Filter Students by Mentor Status', choices=[('', 'All Students'), ('assigned', 'Assigned'), ('unassigned', 'Unassigned')], validators=[Optional()])
    submit = SubmitField('Apply Filters')

# Form for Quiz Attempt (taken by students)
# This form will be dynamically generated in routes.py
class QuizAttemptForm(FlaskForm):
    quiz_id = HiddenField() # To store the quiz ID
    submit = SubmitField('Submit Quiz')

    def __init__(self, quiz_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.quiz_id.data = quiz_id

# Note: The actual question fields will be added dynamically in the route
# with setattr(form, f'question_{question.id}', SomeField(...))
