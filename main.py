import sqlalchemy
from flask import Flask, render_template, redirect, url_for, flash, session
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, CreateRegisterForm, CreateLoginForm, CommentForm
from flask_gravatar import Gravatar
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.exceptions import Forbidden
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL1", "sqlite:///blog.db")
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

Base = declarative_base()

login_manager = LoginManager()
login_manager.init_app(app)

ADMIN_EMAIL = os.environ.get("EMAIL_ID")

gravatar = Gravatar(app,
                    size=200,
                    rating='x',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# #CONFIGURE TABLES
class Users(UserMixin, db.Model, Base):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    # Child BlogPost - one to many - parent = Users(one), child = BlogPost(many)
    child_blog_post = relationship("BlogPost", back_populates="parent_users")
    # Child Comment - one to many - parent = Users(one), child = Comment(many)
    child_comment = relationship("Comment", back_populates="parent_users")


class BlogPost(db.Model, Base):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(1000), nullable=False)
    # Parent Users - one to many - parent = Users(one), child = BlogPost(many)
    parent_user_id = db.Column(db.Integer, sqlalchemy.ForeignKey("users.id"))
    parent_users = relationship("Users", back_populates="child_blog_post")
    # Child Comment - one to many - parent = BlogPost(one), child = Comment(many)
    child_comment = relationship("Comment", back_populates="parent_blog_post")


class Comment(db.Model, Base):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    # Parent Users - one to many - parent = Users(one), child = Comment(many)
    parent_user_id = db.Column(db.Integer, sqlalchemy.ForeignKey("users.id"))
    parent_users = relationship("Users", back_populates="child_comment")
    # Parent BlogPost - one to many - parent = BlogPost(one), child = Comment(many)
    parent_blog_post_id = db.Column(db.Integer, sqlalchemy.ForeignKey("blog_posts.id"))
    parent_blog_post = relationship("BlogPost", back_populates="child_comment")

# db.create_all()


def all_users_emails():
    all_users = db.session.query(Users).all()
    all_user_email = []
    for user in all_users:
        all_user_email.append(user.email)
    return all_user_email


def admin_only(the_function):
    def wrapper(*args, **kwargs):
        try:
            if current_user.id == 1:
                return the_function(*args, **kwargs)
            else:
                raise Forbidden
        except AttributeError:
            raise Forbidden

    # The following code is essential to remove :-
    # 'AssertionError: View function mapping is overwriting an existing endpoint function'
    wrapper.__name__ = the_function.__name__

    return wrapper


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(user_id)


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, admin_email=ADMIN_EMAIL)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = CreateRegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        encrypted_password = generate_password_hash(password=form.password.data,
                                                    method='pbkdf2:sha256',
                                                    salt_length=8)
        name = form.name.data
        if email not in all_users_emails():
            new_user = Users(
                email=email,
                password=encrypted_password,
                name=name
            )
            db.session.add(new_user)
            db.session.commit()

            user_details = Users.query.filter_by(email=email).first()
            login_user(user_details, remember=False, force=False, fresh=True)
            return redirect(url_for("get_all_posts"))
        else:
            flash("The email entered is already registered with us, login instead!")
            return redirect(url_for("login"))

    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = CreateLoginForm()
    if form.validate_on_submit():
        session.pop('_flashes', None)
        entered_email = form.email.data
        entered_password = form.password.data

        if entered_email in all_users_emails():
            user_details = Users.query.filter_by(email=entered_email).first()
            if check_password_hash(user_details.password, entered_password):
                login_user(user_details, remember=False, force=False, fresh=True)
                session["name"] = user_details.name
                return redirect(url_for("get_all_posts"))
            else:
                flash("The password you entered is incorrect!")
                return redirect(url_for("login"))

        else:
            flash("The email entered is not registered with us!")
            return redirect(url_for("login"))

    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                text=form.comment.data,
                parent_user_id=current_user.id,
                parent_blog_post_id=post_id
            )
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash("Login to post a comment!")
            return redirect(url_for("login"))

    my_comments = []
    all_comments_based_on_blog_id = Comment.query.filter_by(parent_blog_post_id=post_id)
    for comment in all_comments_based_on_blog_id:
        comment_text = comment.text
        comment_parent_users_id = comment.parent_user_id
        user_by_parent_users_id = Users.query.get(comment_parent_users_id)
        user_name = user_by_parent_users_id.name
        email = user_by_parent_users_id.email
        the_dict = {"username": user_name, "text": comment_text, "email": email}
        my_comments.append(the_dict)

    requested_post = BlogPost.query.get(post_id)
    return render_template(
        "post.html",
        post=requested_post,
        admin_email=ADMIN_EMAIL,
        comment_form=form,
        all_comments=my_comments
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user.name,
            date=date.today().strftime("%B %d, %Y"),
            parent_user_id=current_user.id
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    # app.run(host='0.0.0.0', port=5000)
    app.run(port=5000, debug=True)
