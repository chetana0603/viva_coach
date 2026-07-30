"""Application factory."""
import logging
import os

from flask import Flask, render_template

from app.extensions import csrf, db, login_manager, migrate


def create_app(config_object: str = "app.config.DevelopmentConfig") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    os.makedirs(os.path.join(os.getcwd(), "instance"), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import user as _user  # noqa: F401  (registers mappers)
    from app.models import exam as _exam  # noqa: F401
    from app.models import question as _question  # noqa: F401
    from app.models import attempt as _attempt  # noqa: F401
    from app.models import response as _response  # noqa: F401
    from app.models import integrity_event as _ie  # noqa: F401
    from app.models import audit as _audit  # noqa: F401
    from app.models import project as _project  # noqa: F401

    from app.auth.routes import auth_bp
    from app.student.routes import student_bp
    from app.teacher.routes import teacher_bp
    from app.project.routes import project_bp
    from app.public import public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(project_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return db.session.get(User, int(user_id))

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("error.html", code=403,
                               message="You do not have access to that page."), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404,
                               message="That page does not exist."), 404

    @app.template_filter("ist")
    def ist(dt):
        from app.utils.datetime_utils import to_ist_string
        return to_ist_string(dt)

    if not app.debug:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s %(message)s")

    return app
