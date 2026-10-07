# auth.py
import re
from datetime import timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, decode_token
from werkzeug.security import generate_password_hash, check_password_hash

from models import (
    db, User, UserRole, Farmer, Buyer, Admin, Cooperative, Notification
)

auth_bp = Blueprint('auth', __name__)


def body():
    return request.get_json(silent=True) or {}


def is_valid_cnic(cnic):
    return bool(re.match(r'^\d{13}$', cnic))


def is_valid_email(email):
    return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', email))


@auth_bp.route('/register', methods=['POST'])
def register():
    data = body()
    required = ['name', 'email', 'password', 'cnic', 'role', 'location', 'phone']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400

    name = str(data['name']).strip()
    email = str(data['email']).lower().strip()
    password = str(data['password'])
    cnic = str(data['cnic']).strip()
    role_str = str(data['role']).lower().strip()
    location = str(data['location']).strip()
    phone = str(data['phone']).strip()

    if not location:
        return jsonify({"error": "Location is required"}), 400
    if len(location) > 200:
        return jsonify({"error": "Location must be 200 characters or less"}), 400
    if not phone:
        return jsonify({"error": "Phone number is required"}), 400
    if not re.match(r'^03\d{9}$', phone):
        return jsonify({"error": "Phone must be 11 digits starting with 03"}), 400
    if not is_valid_email(email):
        return jsonify({"error": "Invalid email"}), 400
    if not is_valid_cnic(cnic):
        return jsonify({"error": "CNIC must be 13 digits"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password min 8 chars"}), 400
    if not re.search(r'[A-Z]', password):
        return jsonify({"error": "Need uppercase letter"}), 400
    if not re.search(r'[a-z]', password):
        return jsonify({"error": "Need lowercase letter"}), 400
    if not re.search(r'\d', password):
        return jsonify({"error": "Need a digit"}), 400
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return jsonify({"error": "Need special character"}), 400

    try:
        role = UserRole(role_str)
    except ValueError:
        valid = [r.value for r in UserRole]
        return jsonify({"error": f"Role must be: {', '.join(valid)}"}), 400

    if role == UserRole.ADMIN:
        return jsonify({"error": "Admin cannot register here"}), 403
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409
    if User.query.filter_by(cnic=cnic).first():
        return jsonify({"error": "CNIC already registered"}), 409

    new_user = User(
        name=name,
        email=email,
        passwordHash=generate_password_hash(password),
        cnic=cnic,
        role=role,
        phone=phone,
        isVerified=False,
        emailVerified=False
    )
    db.session.add(new_user)
    db.session.commit()

    if role == UserRole.FARMER:
        db.session.add(Farmer(
            userId=new_user.userId,
            location=location,
            farmSize="",
            rating=0.0
        ))
    elif role == UserRole.BUYER:
        db.session.add(Buyer(
            userId=new_user.userId,
            businessType="",
            location=location
        ))
    elif role == UserRole.COOPERATIVE:
        db.session.add(Cooperative(
            userId=new_user.userId,
            farmerId=None,
            location=location
        ))
    db.session.commit()

    verify_link = f"/api/verify-email?user_id={new_user.userId}"
    print("verify link:", verify_link)
    return jsonify({
        "message": "Registered, please verify email",
        "userId": new_user.userId,
        "role": role.value,
        "verification_link": verify_link
    }), 201


@auth_bp.route('/verify-email', methods=['GET'])
def verify_email():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id missing"}), 400
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid user_id"}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.emailVerified:
        return jsonify({"message": "Already verified"}), 200

    user.emailVerified = True
    db.session.commit()
    return jsonify({"message": "Email verified, wait for admin approval"}), 200


@auth_bp.route('/login', methods=['POST'])
def login():
    data = body()
    if not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email and password required"}), 400

    email = str(data['email']).lower().strip()
    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.passwordHash, str(data['password'])):
        return jsonify({"error": "Wrong email or password"}), 401
    if not user.emailVerified:
        return jsonify({"error": "Verify email first"}), 403
    if not user.isVerified:
        return jsonify({"error": "Admin approval pending"}), 403

    token = create_access_token(identity=str(user.userId))
    return jsonify({
        "access_token": token,
        "userId": user.userId,
        "role": user.role.value,
        "name": user.name
    }), 200


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = str(body().get('email', '')).lower().strip()
    if not email or not is_valid_email(email):
        return jsonify({"error": "Valid email required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({
            "found": False,
            "reset_link": None,
            "message": "No account with this email"
        }), 200

    reset_token = create_access_token(
        identity=str(user.userId),
        expires_delta=timedelta(minutes=15),
        additional_claims={"purpose": "password_reset"}
    )
    reset_link = f"/reset-password?token={reset_token}"
    print("reset link:", reset_link)
    return jsonify({
        "found": True,
        "reset_link": reset_link,
        "message": "Reset link valid for 15 min"
    }), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = body()
    token = data.get('token')
    new_pass = data.get('new_password')
    if not token or not new_pass:
        return jsonify({"error": "token and new_password required"}), 400

    new_pass_str = str(new_pass)
    if len(new_pass_str) < 8:
        return jsonify({"error": "Password min 8 chars"}), 400
    if not re.search(r'[A-Z]', new_pass_str):
        return jsonify({"error": "Need uppercase letter"}), 400
    if not re.search(r'[a-z]', new_pass_str):
        return jsonify({"error": "Need lowercase letter"}), 400
    if not re.search(r'\d', new_pass_str):
        return jsonify({"error": "Need a digit"}), 400
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_pass_str):
        return jsonify({"error": "Need special character"}), 400

    try:
        decoded = decode_token(token)
    except Exception:
        return jsonify({"error": "Link invalid or expired"}), 401

    if decoded.get('purpose') != 'password_reset':
        return jsonify({"error": "Token not for password reset"}), 401

    try:
        user_id = int(decoded.get('sub'))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid token"}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.passwordHash = generate_password_hash(new_pass_str)
    db.session.commit()
    return jsonify({"message": "Password reset done"}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        cur_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid identity"}), 401

    user = db.session.get(User, cur_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    resp = {
        "userId": user.userId,
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
        "isVerified": user.isVerified,
        "emailVerified": user.emailVerified,
        "walletBalance": user.walletBalance,
        "phone": user.phone
    }

    if user.role == UserRole.FARMER:
        f = Farmer.query.filter_by(userId=user.userId).first()
        if f:
            resp.update(
                farmerId=f.farmerId,
                location=f.location,
                farmSize=f.farmSize,
                rating=f.rating
            )
    elif user.role == UserRole.BUYER:
        b = Buyer.query.filter_by(userId=user.userId).first()
        if b:
            resp.update(
                buyerId=b.buyerId,
                businessType=b.businessType,
                location=b.location
            )
    elif user.role == UserRole.COOPERATIVE:
        c = Cooperative.query.filter_by(userId=user.userId).first()
        if c:
            resp.update(coopId=c.coopId, location=c.location)

    return jsonify(resp), 200


@auth_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    try:
        cur_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid identity"}), 401

    notifs = (Notification.query
              .filter_by(recipientId=cur_id)
              .order_by(Notification.timestamp.desc())
              .limit(30)
              .all())

    unread = Notification.query.filter_by(recipientId=cur_id, isRead=False).count()

    out = []
    for n in notifs:
        out.append({
            "notifId": n.notifId,
            "message": n.message,
            "type": n.type.value if n.type else None,
            "timestamp": n.timestamp.isoformat(),
            "isRead": n.isRead
        })

    return jsonify({
        "unreadCount": unread,
        "notifications": out
    }), 200


@auth_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@jwt_required()
def mark_notification_read(notif_id):
    try:
        cur_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid identity"}), 401

    n = db.session.get(Notification, notif_id)
    if not n or n.recipientId != cur_id:
        return jsonify({"error": "Notification not found"}), 404

    n.isRead = True
    db.session.commit()
    return jsonify({"message": "Marked as read"}), 200


@auth_bp.route('/notifications/read-all', methods=['POST'])
@jwt_required()
def mark_all_notifications_read():
    try:
        cur_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid identity"}), 401

    Notification.query.filter_by(recipientId=cur_id, isRead=False).update({"isRead": True})
    db.session.commit()
    return jsonify({"message": "All marked as read"}), 200