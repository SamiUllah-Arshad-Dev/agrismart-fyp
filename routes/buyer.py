import os
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from models import (
    db, User, UserRole, Buyer, Farmer, CropListing, ListingStatus, Order, OrderStatus,
    Escrow, EscrowStatus, Rating, Notification, NotificationType, FlashSale,
    CooperativeOrderShare, CooperativeSourceAllocation
)

buyer_bp = Blueprint('buyer', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024


def get_buyer():
    uid = get_jwt_identity()
    try:
        uid = int(uid)
    except (ValueError, TypeError):
        return None, None, (jsonify({"error": "Invalid identity"}), 401)

    user = db.session.get(User, uid)
    if not user or user.role != UserRole.BUYER:
        return None, None, (jsonify({"error": "Buyer only"}), 403)

    buyer = Buyer.query.filter_by(userId=uid).first()
    if not buyer:
        return None, None, (jsonify({"error": "Buyer profile missing"}), 404)

    return buyer, user, None


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def notify(user_id, message, ntype=NotificationType.ORDER_UPDATE):
    db.session.add(Notification(
        recipientId=user_id,
        message=message,
        timestamp=datetime.now(timezone.utc),
        type=ntype
    ))


def save_delivery_photo(file, order_id):
    if not file or not file.filename:
        return None, "No file provided"
    if not allowed_file(file.filename):
        return None, "Only jpg, png, jpeg, gif allowed"

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_CONTENT_LENGTH:
        return None, "File too large (max 5 MB)"

    folder = os.path.join(os.path.dirname(__file__), '..', 'static', 'delivery_photos')
    os.makedirs(folder, exist_ok=True)
    name = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
    file.save(os.path.join(folder, name))
    return f"/static/delivery_photos/{name}", None


@buyer_bp.route('/wallet/add-funds', methods=['POST'])
@jwt_required()
def add_funds():
    buyer, user, err = get_buyer()
    if err:
        return err

    data = request.get_json()
    amount = data.get('amount')
    if amount is None:
        return jsonify({"error": "amount required"}), 400
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400
    if amount > 100000:
        return jsonify({"error": "Max 100000 per transaction"}), 400

    user.walletBalance += amount
    db.session.commit()
    return jsonify({"message": f"Rs. {amount} added", "newBalance": user.walletBalance}), 200


@buyer_bp.route('/listings/active', methods=['GET'])
@jwt_required()
def browse():
    buyer, user, err = get_buyer()
    if err:
        return err

    crop = request.args.get('crop_type')
    q = CropListing.query.filter(CropListing.status == ListingStatus.ACTIVE)
    if crop:
        q = q.filter(CropListing.cropType.ilike(f'%{crop}%'))

    out = []
    for l in q.all():
        f = l.farmer
        fu = f.user if f else None

        # cooperative listings show the cooperative's name and phone to the buyer
        coop_user = None
        if l.cooperative_listing and l.cooperative_listing.cooperative:
            coop_user = l.cooperative_listing.cooperative.user

        if coop_user:
            display_name = coop_user.name + " (Cooperative)"
            display_phone = coop_user.phone or ""
        else:
            display_name = fu.name if fu else "Unknown"
            display_phone = fu.phone if fu and fu.phone else ""

        out.append({
            "listingId": l.listingId,
            "cropType": l.cropType,
            "quantity": l.quantity,
            "price": l.price,
            "expiryDate": l.shelfLife.isoformat(),
            "farmerName": display_name,
            "farmerPhone": display_phone,
            "farmerRating": f.rating if f else 0,
            "farmerLocation": f.location if f else "",
            "photos": [p.photoURL for p in l.photos],
            "demandForecast": l.demandForecast
        })
    return jsonify(out), 200


@buyer_bp.route('/orders', methods=['POST'])
@jwt_required()
def place_order():
    buyer, user, err = get_buyer()
    if err:
        return err

    data = request.get_json()
    lid = data.get('listing_id')
    qty = data.get('quantity')
    if not lid or not qty:
        return jsonify({"error": "listing_id and quantity required"}), 400
    try:
        qty = float(qty)
        lid = int(lid)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numbers"}), 400
    if qty <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400

    listing = db.session.query(CropListing).filter_by(listingId=lid).with_for_update().first()
    if not listing or listing.status not in [ListingStatus.ACTIVE, ListingStatus.ON_FLASH_SALE]:
        return jsonify({"error": "Listing not available"}), 404
    if listing.quantity < qty:
        return jsonify({"error": "Not enough quantity"}), 400

    cooperative = listing.cooperative_listing
    cooperative_allocations = []
    if cooperative:
        cooperative_allocations = (
            db.session.query(CooperativeSourceAllocation)
            .filter_by(combinedListingId=cooperative.combinedListingId)
            .order_by(CooperativeSourceAllocation.allocationId.asc())
            .with_for_update()
            .all()
        )
        if not cooperative_allocations:
            return jsonify({"error": "Cooperative source allocation missing"}), 409
        available_coop_stock = sum(a.quantityAllocated for a in cooperative_allocations)
        if available_coop_stock < qty:
            return jsonify({"error": "Not enough cooperative source stock"}), 400

    total = listing.price * qty
    if user.walletBalance < total:
        return jsonify({"error": "Not enough balance"}), 400

    # pre-compute how much each source farmer gets for a cooperative order
    share_plan = []
    if cooperative:
        total_source_stock = sum(a.quantityAllocated for a in cooperative_allocations)
        remaining_qty = round(qty, 2)
        for index, allocation in enumerate(cooperative_allocations):
            if index == len(cooperative_allocations) - 1:
                share_qty = round(remaining_qty, 2)
            else:
                share_qty = round(qty * (allocation.quantityAllocated / total_source_stock), 2)
                share_qty = min(share_qty, remaining_qty)

            if share_qty <= 0:
                continue

            share_plan.append({
                "allocation": allocation,
                "quantity": share_qty,
                "amount": round(share_qty * listing.price, 2)
            })
            remaining_qty = round(remaining_qty - share_qty, 2)

        if round(remaining_qty, 2) != 0:
            return jsonify({"error": "Could not calculate cooperative farmer shares"}), 409
        share_total = round(sum(item["amount"] for item in share_plan), 2)
        if share_total != round(total, 2):
            return jsonify({"error": "Cooperative amount split mismatch"}), 409

    user.walletBalance -= total
    order = Order(
        buyerId=buyer.buyerId,
        listingId=lid,
        orderDate=datetime.now(timezone.utc),
        quantity=qty,
        totalAmount=total,
        status=OrderStatus.PENDING,
        cropTypeSnapshot=listing.cropType,
        priceAtOrder=listing.price
    )
    db.session.add(order)
    db.session.flush()

    db.session.add(Escrow(orderId=order.orderId, amount=total, status=EscrowStatus.HELD))

    listing.quantity -= qty
    if listing.quantity <= 0:
        listing.quantity = 0
        listing.status = ListingStatus.SOLD

    if cooperative:
        for item in share_plan:
            allocation = item["allocation"]
            share_qty = item["quantity"]
            amount_share = item["amount"]
            source = allocation.source_listing

            if not source:
                db.session.rollback()
                return jsonify({"error": "Source listing missing"}), 409
            if source.quantity < share_qty:
                db.session.rollback()
                return jsonify({"error": "Source listing stock mismatch"}), 409
            if source.reservedQuantity < share_qty:
                db.session.rollback()
                return jsonify({"error": "Reserved stock mismatch"}), 409

            source.quantity -= share_qty
            source.reservedQuantity -= share_qty
            if source.reservedQuantity < 0:
                source.reservedQuantity = 0
            if source.quantity <= 0:
                source.quantity = 0
                source.status = ListingStatus.SOLD

            allocation.quantityAllocated -= share_qty
            if allocation.quantityAllocated < 0:
                allocation.quantityAllocated = 0

            db.session.add(CooperativeOrderShare(
                orderId=order.orderId,
                farmerId=allocation.farmerId,
                quantityShare=share_qty,
                amountShare=amount_share
            ))

        cooperative.totalQuantity = max(round(cooperative.totalQuantity - qty, 2), 0)
        if cooperative.totalQuantity <= 0:
            cooperative.totalQuantity = 0
            cooperative.status = ListingStatus.SOLD

    order.status = OrderStatus.PAID

    buyer_loc = buyer.location or "unknown location"
    if cooperative and cooperative.cooperative and cooperative.cooperative.user:
        notify(cooperative.cooperative.user.userId,
               f"New cooperative order: {qty}kg {listing.cropType} "
               f"by {user.name} ({buyer_loc}). Escrow held Rs.{total}")
    elif listing.farmer and listing.farmer.user:
        notify(listing.farmer.user.userId,
               f"New order: {qty}kg {listing.cropType} "
               f"by {user.name} ({buyer_loc}). Escrow held Rs.{total}")

    db.session.commit()
    return jsonify({
        "message": "Order placed, escrow held",
        "orderId": order.orderId,
        "total": total
    }), 201


@buyer_bp.route('/orders', methods=['GET'])
@jwt_required()
def order_history():
    buyer, user, err = get_buyer()
    if err:
        return err

    orders = Order.query.filter_by(buyerId=buyer.buyerId).all()
    out = []
    for o in orders:
        l = o.listing
        farmer_name = "Unknown"
        farmer_phone = ""

        if l and l.cooperative_listing and l.cooperative_listing.cooperative:
            coop_user = l.cooperative_listing.cooperative.user
            farmer_name = coop_user.name + " (Cooperative)"
            farmer_phone = coop_user.phone or ""
        elif l and l.farmer and l.farmer.user:
            farmer_name = l.farmer.user.name
            farmer_phone = l.farmer.user.phone or ""

        out.append({
            "orderId": o.orderId,
            "cropType": o.cropTypeSnapshot or (l.cropType if l else "Unknown"),
            "priceAtOrder": o.priceAtOrder,
            "farmerName": farmer_name,
            "farmerPhone": farmer_phone,
            "quantity": o.quantity,
            "totalAmount": o.totalAmount,
            "status": o.status.value,
            "orderDate": o.orderDate.isoformat(),
            "deliveryPhoto": o.deliveryPhoto,
            "escrow": {
                "amount": o.escrow.amount if o.escrow else 0,
                "status": o.escrow.status.value if o.escrow else None
            }
        })
    return jsonify(out), 200


@buyer_bp.route('/orders/<int:oid>/confirm', methods=['POST'])
@jwt_required()
def confirm(oid):
    buyer, user, err = get_buyer()
    if err:
        return err

    order = db.session.get(Order, oid)
    if not order or order.buyerId != buyer.buyerId:
        return jsonify({"error": "Order not found"}), 404
    if order.status != OrderStatus.PAID:
        return jsonify({"error": "Cannot confirm"}), 400

    if 'photo' not in request.files:
        return jsonify({"error": "Photo required"}), 400
    photo = request.files['photo']
    if photo.filename == '':
        return jsonify({"error": "Empty photo"}), 400

    url, error = save_delivery_photo(photo, oid)
    if error:
        return jsonify({"error": error}), 400

    esc = order.escrow
    if not esc or esc.status != EscrowStatus.HELD:
        return jsonify({"error": "Escrow is not available for release"}), 400

    order.deliveryPhoto = url
    order.deliveredAt = datetime.now(timezone.utc)
    order.status = OrderStatus.DELIVERED

    cooperative = order.listing.cooperative_listing if order.listing else None
    if cooperative:
        shares = CooperativeOrderShare.query.filter_by(orderId=order.orderId).all()
        if not shares:
            db.session.rollback()
            return jsonify({"error": "Cooperative payout shares missing"}), 409

        share_total = round(sum(float(s.amountShare) for s in shares), 2)
        if share_total != round(float(esc.amount), 2):
            db.session.rollback()
            return jsonify({"error": "Cooperative payout amount mismatch"}), 409

        # a single farmer might have several shares, so accumulate first
        farmer_payouts = {}
        for share in shares:
            farmer_payouts[share.farmerId] = farmer_payouts.get(share.farmerId, 0.0) + float(share.amountShare)

        esc.status = EscrowStatus.RELEASED
        for farmer_id, amount in farmer_payouts.items():
            farmer = db.session.get(Farmer, farmer_id)
            if not farmer or not farmer.user:
                db.session.rollback()
                return jsonify({"error": f"Farmer data missing for farmer {farmer_id}"}), 409

            amount = round(amount, 2)
            farmer.user.walletBalance += amount
            notify(farmer.user.userId,
                   f"Delivery confirmed for cooperative order #{order.orderId}. "
                   f"Your share of escrow released: Rs.{amount}")
    else:
        esc.status = EscrowStatus.RELEASED
        if order.listing and order.listing.farmer and order.listing.farmer.user:
            farmer_user = order.listing.farmer.user
            farmer_user.walletBalance += esc.amount
            notify(farmer_user.userId,
                   f"Delivery confirmed for order #{order.orderId}. Escrow released Rs.{esc.amount}")

    db.session.commit()
    return jsonify({"message": "Delivery confirmed, escrow released", "photoUrl": url}), 200


@buyer_bp.route('/orders/<int:oid>/dispute', methods=['POST'])
@jwt_required()
def dispute(oid):
    buyer, user, err = get_buyer()
    if err:
        return err

    data = request.get_json()
    reason = data.get('reason')
    if not reason:
        return jsonify({"error": "Reason required"}), 400

    order = db.session.get(Order, oid)
    if not order or order.buyerId != buyer.buyerId:
        return jsonify({"error": "Order not found"}), 404
    if order.status not in [OrderStatus.PAID, OrderStatus.PENDING]:
        return jsonify({"error": "Cannot dispute"}), 400

    order.status = OrderStatus.DISPUTED
    if order.escrow:
        order.escrow.status = EscrowStatus.DISPUTED

    dispute_type = NotificationType.DISPUTE_UPDATE

    admin = User.query.filter_by(role=UserRole.ADMIN).first()
    if admin:
        notify(admin.userId, f"Dispute on order {oid}: {reason}", dispute_type)

    cooperative = order.listing.cooperative_listing if order.listing else None
    if cooperative and cooperative.cooperative and cooperative.cooperative.user:
        notify(cooperative.cooperative.user.userId,
               f"Dispute raised on cooperative order #{oid}. Reason: {reason}", dispute_type)
    elif order.listing and order.listing.farmer and order.listing.farmer.user:
        notify(order.listing.farmer.user.userId,
               f"Dispute raised on order #{oid}. Reason: {reason}", dispute_type)

    db.session.commit()
    return jsonify({"message": "Dispute raised"}), 200


@buyer_bp.route('/ratings', methods=['POST'])
@jwt_required()
def rate():
    buyer, user, err = get_buyer()
    if err:
        return err

    data = request.get_json()
    oid = data.get('order_id')
    score = data.get('score')
    comment = data.get('comment', '')
    if not oid or score is None:
        return jsonify({"error": "order_id and score required"}), 400

    try:
        score = float(score)
        if not 1 <= score <= 5:
            raise ValueError
        oid = int(oid)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid score or order_id"}), 400

    order = db.session.get(Order, oid)
    if not order or order.buyerId != buyer.buyerId:
        return jsonify({"error": "Order not found"}), 404
    if order.status not in [OrderStatus.DELIVERED, OrderStatus.COMPLETED]:
        return jsonify({"error": "Cannot rate yet"}), 400

    existing = Rating.query.filter_by(orderId=oid, reviewerId=user.userId).first()
    if existing:
        return jsonify({"error": "Already rated"}), 409
    if not order.listing:
        return jsonify({"error": "Listing data missing"}), 404

    cooperative = order.listing.cooperative_listing
    if cooperative:
        if not cooperative.cooperative or not cooperative.cooperative.user:
            return jsonify({"error": "Cooperative data missing"}), 404
        reviewee_user = cooperative.cooperative.user
        db.session.add(Rating(
            reviewerId=user.userId,
            revieweeId=reviewee_user.userId,
            orderId=oid,
            score=score,
            comment=comment
        ))
    else:
        if not order.listing.farmer:
            return jsonify({"error": "Farmer data missing"}), 404
        farmer_user = order.listing.farmer.user
        if not farmer_user:
            return jsonify({"error": "Farmer user missing"}), 404

        db.session.add(Rating(
            reviewerId=user.userId,
            revieweeId=farmer_user.userId,
            orderId=oid,
            score=score,
            comment=comment
        ))

        all_ratings = Rating.query.filter_by(revieweeId=farmer_user.userId).all()
        avg = sum(r.score for r in all_ratings) / len(all_ratings) if all_ratings else 0.0
        order.listing.farmer.rating = round(avg, 1)

    if order.status != OrderStatus.COMPLETED:
        order.status = OrderStatus.COMPLETED

    db.session.commit()
    return jsonify({"message": "Rating submitted, order completed"}), 200


@buyer_bp.route('/flash-sale/alerts', methods=['GET'])
@jwt_required()
def flash_alerts():
    buyer, user, err = get_buyer()
    if err:
        return err

    listings = CropListing.query.filter(CropListing.status == ListingStatus.ON_FLASH_SALE).all()
    out = []
    for l in listings:
        fs = FlashSale.query.filter_by(listingId=l.listingId).first()
        farmer = l.farmer

        coop_user = None
        if l.cooperative_listing and l.cooperative_listing.cooperative:
            coop_user = l.cooperative_listing.cooperative.user

        if coop_user:
            display_name = coop_user.name + " (Cooperative)"
            display_phone = coop_user.phone or ""
        else:
            display_name = farmer.user.name if farmer and farmer.user else "Unknown"
            display_phone = farmer.user.phone if farmer and farmer.user and farmer.user.phone else ""

        out.append({
            "listingId": l.listingId,
            "cropType": l.cropType,
            "originalPrice": l.original_price,
            "discountedPrice": fs.discountedPrice if fs else l.price,
            "quantity": l.quantity,
            "expiryDate": l.shelfLife.isoformat(),
            "farmerName": display_name,
            "farmerPhone": display_phone,
            "farmerLocation": farmer.location if farmer else "",
            "photos": [p.photoURL for p in l.photos]
        })
    return jsonify(out), 200