from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
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
                         validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', 
                       validators=[DataRequired(), Email()])
    password = PasswordField('Password', 
                           validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), 
                                             EqualTo('password', 
                                                    message='Passwords must match')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        """Validate that username is unique"""
        user = Student.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('This username is already taken.')

    def validate_email(self, email):
        """Validate that email is unique"""
        user = Student.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('This email is already registered.')