from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from models import Student

class LoginForm(FlaskForm):
    """Form for user login"""
    username = StringField('Username', 
                       validators=[
                           DataRequired(message='Username is required'),
                           Length(min=2, max=64, message='Username must be between 2 and 64 characters')
                       ])
    password = PasswordField('Password', 
                         validators=[
                             DataRequired(message='Password is required'),
                             Length(min=6, message='Password must be at least 6 characters')
                         ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    """Form for user registration"""
    username = StringField('Username', 
                       validators=[
                           DataRequired(),
                           Length(min=2, max=20, message='Username must be between 2 and 20 characters')
                       ])
    email = StringField('Email (Optional)', 
                     validators=[Optional(), Email()])
    password = PasswordField('Password', 
                         validators=[
                             DataRequired(),
                             Length(min=6, message='Password must be at least 6 characters')
                         ])
    confirm_password = PasswordField('Confirm Password', 
                                 validators=[
                                     DataRequired(), 
                                     EqualTo('password', message='Passwords must match')
                                 ])
    submit = SubmitField('Register')

    def validate_username(self, username):
        """Validate that username is unique"""
        user = Student.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('This username is already taken.')

class ResetPasswordRequestForm(FlaskForm):
    """Form for requesting password reset"""
    username = StringField('Username', validators=[DataRequired()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    """Form for resetting password"""
    password = PasswordField('New Password', 
                         validators=[
                             DataRequired(),
                             Length(min=6, message='Password must be at least 6 characters')
                         ])
    confirm_password = PasswordField('Confirm New Password',
                                 validators=[
                                     DataRequired(), 
                                     EqualTo('password', message='Passwords must match')
                                 ])
    submit = SubmitField('Reset Password')

class AdminConsoleForm(FlaskForm):
    """Form for admin actions"""
    username = StringField('Username', validators=[DataRequired()])
    reset_password = SubmitField('Reset User Password')
    unlock_account = SubmitField('Unlock Account')