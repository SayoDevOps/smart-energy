from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from markupsafe import Markup

db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_name='default'):
    from config import config
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    if config_name != 'development' and not app.config.get('SECRET_KEY'):
        raise RuntimeError('SECRET_KEY must be configured outside development.')
    if config_name != 'development' and not app.config.get('SQLALCHEMY_DATABASE_URI'):
        raise RuntimeError('DATABASE_URL must be configured outside development.')
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    @app.template_filter('naira')
    def naira_filter(value):
        if value is None:
            return "—"
        return Markup(f"&#8358;{value:,.2f}")
    
    @app.template_filter('percent')
    def percent_filter(value):
        if value is None:
            return "—"
        return f"{value:.1f}%"
    
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.appliances import appliances_bp
    from app.routes.consumption import consumption_bp
    from app.routes.billing import billing_bp
    from app.routes.optimizer import optimizer_bp
    from app.routes.reports import reports_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(appliances_bp, url_prefix='/appliances')
    app.register_blueprint(consumption_bp)
    app.register_blueprint(billing_bp, url_prefix='/billing')
    app.register_blueprint(optimizer_bp, url_prefix='/optimizer')
    app.register_blueprint(reports_bp, url_prefix='/reports')

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('errors/404.html'), 404
    
    @app.cli.command('init-db')
    def init_db():
        from app.models import User, TariffBand, Appliance, ConsumptionLog, Bill, OptimizationTip, Budget
        db.create_all()
        from app.utils.seeder import seed_tariff_bands
        seed_tariff_bands()
        print("Database initialized.")
    
    @app.cli.command('drop-db')
    def drop_db():
        db.drop_all()
        print("Database dropped.")
    
    return app