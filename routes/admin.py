import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import (
    db, User, UserRole, Farmer, Order, OrderStatus, Escrow, EscrowStatus, FlashSale,
    FlashSaleStatus, CropListing, ListingStatus, Notification, NotificationType,
    CooperativeOrderShare
)

admin_bp = Blueprint('admin', __name__)


def check_admin():
    uid = get_jwt_identity()
    try:
        uid = int(uid)
    except (ValueError, TypeError):
        return None, (jsonify({"error": "Invalid identity"}), 401)

    user = db.session.get(User, uid)
    if not user or user.role != UserRole.ADMIN:
        return None, (jsonify({"error": "Admin only"}), 403)

    return user, None


def notify(user_id, message):
    db.session.add(Notification(
        recipientId=user_id,
        message=message,
        timestamp=datetime.now(timezone.utc),
        type=NotificationType.DISPUTE_UPDATE
    ))


@admin_bp.route('/admin/users/pending', methods=['GET'])
@jwt_required()
def pending_users():
    admin, err = check_admin()
    if err:
        return err

    pending = User.query.filter_by(isVerified=False).all()
    out = []
    for u in pending:
        out.append({
            "userId": u.userId,
            "name": u.name,
            "email": u.email,
            "cnic": u.cnic,
            "role": u.role.value,
            "emailVerified": u.emailVerified
        })
    return jsonify(out), 200


@admin_bp.route('/admin/verify/<int:uid>', methods=['POST'])
@jwt_required()
def verify_user(uid):
    admin, err = check_admin()
    if err:
        return err

    user = db.session.get(User, uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.isVerified:
        return jsonify({"message": "Already verified"}), 200

    user.isVerified = True
    db.session.commit()
    return jsonify({"message": f"{user.name} verified"}), 200


@admin_bp.route('/admin/dashboard', methods=['GET'])
@jwt_required()
def dashboard():
    admin, err = check_admin()
    if err:
        return err

    return jsonify({
        "total_users": User.query.count(),
        "total_farmers": User.query.filter_by(role=UserRole.FARMER).count(),
        "total_buyers": User.query.filter_by(role=UserRole.BUYER).count(),
        "total_orders": Order.query.count(),
        "pending_orders": Order.query.filter_by(status=OrderStatus.PENDING).count(),
        "disputed_orders": Order.query.filter_by(status=OrderStatus.DISPUTED).count(),
        "active_flash_sales": FlashSale.query.filter_by(status=FlashSaleStatus.ACTIVE).count(),
        "total_listings": CropListing.query.count()
    }), 200


@admin_bp.route('/admin/disputes', methods=['GET'])
@jwt_required()
def get_disputes():
    admin, err = check_admin()
    if err:
        return err

    orders = Order.query.filter_by(status=OrderStatus.DISPUTED).all()
    out = []
    for o in orders:
        esc = o.escrow
        listing = db.session.get(CropListing, o.listingId)
        farmer_name = "Unknown"
        cooperative_name = None

        if listing:
            cooperative = listing.cooperative_listing
            if cooperative:
                if cooperative.cooperative and cooperative.cooperative.user:
                    cooperative_name = cooperative.cooperative.user.name
                else:
                    cooperative_name = "Cooperative"
                farmer_name = f"Cooperative: {cooperative_name}"
            elif listing.farmer and listing.farmer.user:
                farmer_name = listing.farmer.user.name

        buyer_name = o.buyer.user.name if o.buyer and o.buyer.user else "Unknown"
        out.append({
            "orderId": o.orderId,
            "buyerName": buyer_name,
            "farmerName": farmer_name,
            "cooperativeName": cooperative_name,
            "amount": esc.amount if esc else 0,
            "orderStatus": o.status.value,
            "escrowStatus": esc.status.value if esc else "None",
            "deliveryPhoto": o.deliveryPhoto
        })
    return jsonify(out), 200


@admin_bp.route('/admin/disputes/<int:oid>/resolve', methods=['POST'])
@jwt_required()
def resolve_dispute(oid):
    admin, err = check_admin()
    if err:
        return err

    data = request.get_json() or {}
    action = data.get('action')
    if action not in ['release', 'hold', 'cancel_refund']:
        return jsonify({"error": "Invalid action"}), 400

    order = db.session.get(Order, oid)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    if order.status != OrderStatus.DISPUTED:
        return jsonify({"error": "Dispute already resolved or not active"}), 400

    esc = order.escrow
    if not esc:
        return jsonify({"error": "No escrow"}), 404

    buyer_user = order.buyer.user if order.buyer else None
    listing = db.session.get(CropListing, order.listingId)
    if not listing:
        return jsonify({"error": "Listing not found"}), 404

    cooperative = listing.cooperative_listing
    farmer_user = listing.farmer.user if listing.farmer else None
    cooperative_user = cooperative.cooperative.user if cooperative and cooperative.cooperative else None

    if action == 'release':
        if cooperative:
            shares = CooperativeOrderShare.query.filter_by(orderId=order.orderId).all()
            if not shares:
                return jsonify({"error": "Cooperative order has no payout shares"}), 400

            total_share_amount = round(sum(float(s.amountShare) for s in shares), 2)
            escrow_amount = round(float(esc.amount), 2)
            if total_share_amount != escrow_amount:
                return jsonify({
                    "error": "Cooperative payout shares do not match escrow amount",
                    "escrowAmount": escrow_amount,
                    "shareAmount": total_share_amount
                }), 400

            for share in shares:
                farmer = db.session.get(Farmer, share.farmerId)
                if not farmer or not farmer.user:
                    return jsonify({
                        "error": f"Farmer {share.farmerId} for cooperative payout not found"
                    }), 400
                farmer.user.walletBalance += share.amountShare
                notify(farmer.user.userId,
                       f"Dispute on cooperative order #{oid} resolved in your favor. "
                       f"Rs. {share.amountShare:.2f} released to your wallet.")

            esc.status = EscrowStatus.RELEASED
            order.status = OrderStatus.COMPLETED
            msg = "Payment released to participating farmers, cooperative order completed"

            if cooperative_user:
                notify(cooperative_user.userId,
                       f"Dispute on cooperative order #{oid} was resolved: "
                       "payment was released to participating farmers.")
        else:
            esc.status = EscrowStatus.RELEASED
            order.status = OrderStatus.COMPLETED
            if farmer_user:
                farmer_user.walletBalance += esc.amount
                notify(farmer_user.userId,
                       f"Dispute on order #{oid} resolved in your favor. "
                       f"Rs. {esc.amount:.2f} released to your wallet.")
            msg = "Payment released, order completed"

        if buyer_user:
            if cooperative:
                buyer_message = (f"Your dispute on order #{oid} was resolved: payment was released "
                                 "to the participating farmers, and the order was completed.")
            else:
                buyer_message = (f"Your dispute on order #{oid} was resolved: "
                                 "payment released to the farmer, order completed.")
            notify(buyer_user.userId, buyer_message)

    elif action == 'hold':
        esc.status = EscrowStatus.DISPUTED
        msg = "Escrow held for review"

        if buyer_user:
            notify(buyer_user.userId,
                   f"Your dispute on order #{oid} is still under review. Escrow remains held.")
        if cooperative and cooperative_user:
            notify(cooperative_user.userId,
                   f"Dispute on cooperative order #{oid} is still under review. Escrow remains held.")
        elif farmer_user:
            notify(farmer_user.userId,
                   f"Dispute on order #{oid} is still under review. Escrow remains held.")

    else:  # cancel_refund
        esc.status = EscrowStatus.REFUNDED
        order.status = OrderStatus.CANCELLED
        if order.buyer and order.buyer.user:
            order.buyer.user.walletBalance += esc.amount
        msg = "Order cancelled, buyer refunded"

        if buyer_user:
            notify(buyer_user.userId,
                   f"Your dispute on order #{oid} was resolved: order cancelled "
                   f"and Rs. {esc.amount:.2f} refunded to your wallet.")
        if cooperative and cooperative_user:
            notify(cooperative_user.userId,
                   f"Cooperative order #{oid} was cancelled by admin after a dispute. "
                   "Buyer was refunded.")
        elif farmer_user:
            notify(farmer_user.userId,
                   f"Order #{oid} was cancelled by admin after a dispute. "
                   "No payment was released.")

    db.session.commit()
    return jsonify({"message": msg}), 200


@admin_bp.route('/admin/flash-sales', methods=['GET'])
@jwt_required()
def get_flash_sales():
    admin, err = check_admin()
    if err:
        return err

    fsales = FlashSale.query.filter_by(status=FlashSaleStatus.ACTIVE).all()
    out = []
    for fs in fsales:
        l = fs.listing
        out.append({
            "flashSaleId": fs.flashSaleId,
            "listingId": fs.listingId,
            "cropType": l.cropType if l else "Unknown",
            "originalPrice": l.original_price if l else 0,
            "discountedPrice": fs.discountedPrice,
            "expiryTime": fs.expiryTime.isoformat(),
            "status": fs.status.value
        })
    return jsonify(out), 200


@admin_bp.route('/admin/flash-sales/<int:fsid>/override', methods=['POST'])
@jwt_required()
def override_flash(fsid):
    admin, err = check_admin()
    if err:
        return err

    fs = db.session.get(FlashSale, fsid)
    if not fs:
        return jsonify({"error": "Flash sale not found"}), 404

    fs.status = FlashSaleStatus.OVERRIDDEN
    listing = fs.listing
    if listing:
        listing.price = fs.originalPrice
        listing.status = ListingStatus.ACTIVE

    db.session.commit()
    return jsonify({"message": "Flash sale overridden, listing active"}), 200


@admin_bp.route('/admin/offline-mode', methods=['POST'])
@jwt_required()
def offline_mode():
    admin, err = check_admin()
    if err:
        return err

    data = request.get_json()
    enable = data.get('enable', False)
    current_app.config['OFFLINE_MODE'] = enable

    if enable:
        base = current_app.config.get('BASE_DIR', os.path.abspath(os.path.dirname(__file__)))
        uri = 'sqlite:///' + os.path.join(base, 'instance', 'agrismart.db')
        current_app.config['SQLALCHEMY_DATABASE_URI'] = uri
        msg = "Offline mode enabled (SQLite)"
    else:
        msg = "Online mode ready (set DATABASE_URL)"

    return jsonify({"message": msg, "offline_mode": enable}), 200


@admin_bp.route('/admin/offline-mode/status', methods=['GET'])
@jwt_required()
def offline_status():
    admin, err = check_admin()
    if err:
        return err

    return jsonify({
        "offline_mode": current_app.config.get('OFFLINE_MODE', False),
        "database_uri": current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    }), 200


@admin_bp.route('/admin/users/all', methods=['GET'])
@jwt_required()
def get_all_users():
    admin, err = check_admin()
    if err:
        return err

    users = User.query.all()
    out = []
    for u in users:
        out.append({
            "userId": u.userId,
            "name": u.name,
            "email": u.email,
            "role": u.role.value,
            "verified": u.isVerified
        })
    return jsonify(out), 200


@admin_bp.route('/admin/orders/all', methods=['GET'])
@jwt_required()
def get_all_orders():
    admin, err = check_admin()
    if err:
        return err

    orders = Order.query.all()
    out = []
    for o in orders:
        listing = db.session.get(CropListing, o.listingId)
        out.append({
            "orderId": o.orderId,
            "buyer": o.buyer.user.name if o.buyer and o.buyer.user else "N/A",
            "crop": listing.cropType if listing else "N/A",
            "total": o.totalAmount,
            "status": o.status.value
        })
    return jsonify(out), 200


@admin_bp.route('/admin/users/stats', methods=['GET'])
@jwt_required()
def get_user_stats():
    admin, err = check_admin()
    if err:
        return err

    return jsonify({
        "total": User.query.count(),
        "verified": User.query.filter_by(isVerified=True).count(),
        "unverified": User.query.filter_by(isVerified=False).count()
    }), 200


@admin_bp.route('/admin/users/search', methods=['GET'])
@jwt_required()
def search_users():
    admin, err = check_admin()
    if err:
        return err

    query = request.args.get('q', 'a').strip()
    if not query:
        return jsonify([]), 200

    users = User.query.filter(db.or_(
        User.name.ilike(f'%{query}%'),
        User.email.ilike(f'%{query}%'),
        User.cnic.ilike(f'%{query}%')
    )).all()

    out = []
    for u in users:
        out.append({
            "userId": u.userId,
            "name": u.name,
            "email": u.email,
            "cnic": u.cnic,
            "role": u.role.value,
            "isVerified": u.isVerified,
            "emailVerified": u.emailVerified
        })
    return jsonify(out), 200