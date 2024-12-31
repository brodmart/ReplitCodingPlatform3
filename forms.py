
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from models import Student

class LoginForm(FlaskForm):
    """Form for user login"""
    username = StringField('Nom d\'utilisateur', 
                         validators=[
                             DataRequired(message='Ce champ est requis'),
                             Length(min=2, max=64, message='Le nom d\'utilisateur doit contenir entre 2 et 64 caractères')
                         ])
    password = PasswordField('Mot de passe', 
                           validators=[
                               DataRequired(message='Ce champ est requis'),
                               Length(min=6, message='Le mot de passe doit contenir au moins 6 caractères')
                           ])
    remember_me = BooleanField('Se souvenir de moi')
    submit = SubmitField('Connexion')

class RegisterForm(FlaskForm):
    """Form for user registration"""
    username = StringField('Nom d\'utilisateur', 
                         validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', 
                       validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe', 
                           validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmer le mot de passe', 
                                   validators=[DataRequired(), 
                                             EqualTo('password', 
                                                    message='Les mots de passe doivent correspondre')])
    submit = SubmitField('S\'inscrire')

    def validate_username(self, username):
        """Validate that username is unique"""
        user = Student.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Ce nom d\'utilisateur est déjà pris.')

    def validate_email(self, email):
        """Validate that email is unique"""
        user = Student.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Cet email est déjà utilisé.')
