from flask_wtf import FlaskForm
from wtforms import HiddenField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, Regexp


class DocumentForm(FlaskForm):
    title = StringField("제목", validators=[DataRequired(), Length(min=1, max=200)])
    body_markdown = TextAreaField("본문", validators=[Optional()])
    tags = StringField("태그", validators=[Optional(), Length(max=500)])
    edit_summary = StringField("편집 요약", validators=[Optional(), Length(max=300)])
    base_revision = HiddenField()
    submit = SubmitField("저장")


class ShareForm(FlaskForm):
    username = StringField(
        "공유할 사용자명",
        validators=[
            DataRequired(),
            Length(min=3, max=32),
            Regexp(r"^[a-z0-9][a-z0-9_-]{2,31}$"),
        ],
    )
    access_level = SelectField(
        "권한",
        choices=[("viewer", "열람자"), ("editor", "편집자")],
        validators=[DataRequired()],
    )
    submit = SubmitField("공유")


class EmptyForm(FlaskForm):
    submit = SubmitField("확인")
