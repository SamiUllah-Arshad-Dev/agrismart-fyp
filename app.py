import atexit
import logging
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from apscheduler.schedulers.background import BackgroundScheduler

from models import db
from config import Config

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('agrismart.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

CORS(app)
jwt = JWTManager(app)
db.init_app(app)

from routes.auth import auth_bp
from routes.farmer import farmer_bp
from routes.buyer import buyer_bp
from routes.admin import admin_bp
from routes.cooperative import cooperative_bp

app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(farmer_bp, url_prefix='/api')
app.register_blueprint(buyer_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/api')
app.register_blueprint(cooperative_bp, url_prefix='/api')


@app.route('/api/health')
def health_check():
    return jsonify({"status": "ok", "message": "AgriSmart backend is running"}), 200


@app.route('/')
def home():
    return render_template('register.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/forgot-password')
def forgot_password_page():
    return render_template('forgot_password.html')


@app.route('/reset-password')
def reset_password_page():
    return render_template('reset_password.html')


@app.route('/farmer/dashboard')
def farmer_dashboard():
    return render_template('farmer_dashboard.html')


@app.route('/buyer/dashboard')
def buyer_dashboard():
    return render_template('buyer_dashboard.html')


@app.route('/cooperative-ui')
def cooperative_ui():
    return render_template('cooperative_ui.html')


@app.route('/admin-panel')
def admin_panel():
    return render_template('admin_panel.html')


with app.app_context():
    db.create_all()
    logger.info("Database tables created")


from services.wastage_monitor import check_and_trigger_flash_sales


def auto_complete_stale_orders():
    with app.app_context():
        from models import Order, OrderStatus
        cutoff = datetime.now() - timedelta(days=2)
        old_orders = Order.query.filter(
            Order.status == OrderStatus.DELIVERED,
            Order.deliveredAt.isnot(None),
            Order.deliveredAt < cutoff
        ).all()

        for o in old_orders:
            o.status = OrderStatus.COMPLETED
            logger.info("Completed order: %s", o.orderId)

        if old_orders:
            db.session.commit()
            logger.info("Auto-complete done, count = %s", len(old_orders))


scheduler = BackgroundScheduler()
scheduler.add_job(func=check_and_trigger_flash_sales, trigger="interval", hours=6, id='wastage_monitor')
scheduler.add_job(func=auto_complete_stale_orders, trigger="cron", hour=2, minute=0, id='auto_complete_orders')
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

logger.info("Wastage monitor scheduled every 6 hours")
logger.info("Auto-complete orders job scheduled at 2 AM")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)