from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp

USERNAME_PATTERN = r"^[a-z0-9][a-z0-9_-]{2,31}$"


class RegisterForm(FlaskForm):
    username = StringField(
        "사용자명",
        validators=[
            DataRequired(),
            Length(min=3, max=32),
            Regexp(
                USERNAME_PATTERN,
                message="영문 소문자나 숫자로 시작하고 영문 소문자, 숫자, _, -만 사용하세요.",
            ),
        ],
    )
    display_name = StringField(
        "표시 이름",
        validators=[DataRequired(), Length(min=1, max=80)],
    )
    email = StringField(
        "이메일",
        validators=[DataRequired(), Email(), Length(max=254)],
    )
    password = PasswordField(
        "비밀번호",
        validators=[DataRequired(), Length(min=12, max=128)],
    )
    password_confirm = PasswordField(
        "비밀번호 확인",
        validators=[DataRequired(), EqualTo("password", message="비밀번호가 일치하지 않습니다.")],
    )
    submit = SubmitField("계정 만들기")


class LoginForm(FlaskForm):
    identity = StringField(
        "이메일 또는 사용자명",
        validators=[DataRequired(), Length(max=254)],
    )
    password = PasswordField("비밀번호", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("로그인 상태 유지")
    submit = SubmitField("로그인")


class EmailRequestForm(FlaskForm):
    email = StringField(
        "이메일",
        validators=[DataRequired(), Email(), Length(max=254)],
    )
    submit = SubmitField("메일 보내기")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "새 비밀번호",
        validators=[DataRequired(), Length(min=12, max=128)],
    )
    password_confirm = PasswordField(
        "새 비밀번호 확인",
        validators=[DataRequired(), EqualTo("password", message="비밀번호가 일치하지 않습니다.")],
    )
    submit = SubmitField("비밀번호 변경")


class EmptyForm(FlaskForm):
    submit = SubmitField("확인")
