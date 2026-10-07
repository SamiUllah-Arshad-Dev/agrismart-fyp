from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_

from models import (
    db, User, UserRole, Farmer, Cooperative, CooperativeListing, CooperativeFarmer,
    CooperativeSourceAllocation, ListingStatus, CropListing, ListingPhoto, FlashSale, Order
)

cooperative_bp = Blueprint('cooperative', __name__)


def get_coop():
    uid = get_jwt_identity()
    try:
        uid = int(uid)
    except (ValueError, TypeError):
        return None, (jsonify({"error": "Invalid identity"}), 401)

    user = db.session.get(User, uid)
    if not user or user.role != UserRole.COOPERATIVE:
        return None, (jsonify({"error": "Cooperative only"}), 403)

    coop = Cooperative.query.filter_by(userId=uid).first()
    if not coop:
        return None, (jsonify({"error": "Cooperative profile missing"}), 404)

    return coop, None


@cooperative_bp.route('/cooperative/flash-sale/my-alerts', methods=['GET'])
@jwt_required()
def my_cooperative_flash_alerts():
    coop, err = get_coop()
    if err:
        return err

    listings = (CooperativeListing.query.filter_by(coopId=coop.coopId)
                .order_by(CooperativeListing.createdAt.desc()).all())

    out = []
    for cl in listings:
        shadow = cl.shadow_listing
        if not shadow or shadow.status != ListingStatus.ON_FLASH_SALE:
            continue
        fs = shadow.flash_sale
        if not fs:
            continue
        out.append({
            "combinedListingId": cl.combinedListingId,
            "listingId": shadow.listingId,
            "cropType": cl.cropType,
            "quantity": cl.totalQuantity,
            "discountedPrice": shadow.price,
            "originalPrice": fs.originalPrice,
            "expiryDate": cl.shelfLife.isoformat() if cl.shelfLife else None,
            "cooperativeResponse": fs.farmerResponse,
            "status": shadow.status.value
        })
    return jsonify(out), 200


@cooperative_bp.route('/cooperative/flash-sale/respond', methods=['POST'])
@jwt_required()
def respond_cooperative_flash():
    coop, err = get_coop()
    if err:
        return err

    data = request.get_json() or {}
    lid = data.get('listing_id')
    accept = data.get('accept', True)

    if not lid:
        return jsonify({"error": "listing_id required"}), 400
    try:
        lid = int(lid)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid listing_id"}), 400

    shadow = db.session.get(CropListing, lid)
    if not shadow:
        return jsonify({"error": "Cooperative listing not found"}), 404
    if not shadow.cooperativeListingId:
        return jsonify({"error": "This is not a cooperative listing"}), 404

    combined = db.session.get(CooperativeListing, shadow.cooperativeListingId)
    if not combined:
        return jsonify({"error": "Cooperative listing not found"}), 404
    if combined.coopId != coop.coopId:
        return jsonify({"error": "You cannot manage this cooperative listing"}), 403
    if shadow.status != ListingStatus.ON_FLASH_SALE:
        return jsonify({"error": "Not on flash sale"}), 400

    fs = FlashSale.query.filter_by(listingId=shadow.listingId).first()
    if not fs:
        return jsonify({"error": "Flash sale record not found"}), 404

    if accept:
        fs.farmerResponse = 'accepted'
        db.session.commit()
        return jsonify({
            "message": "Cooperative flash sale accepted",
            "combinedListingId": combined.combinedListingId,
            "listingId": shadow.listingId,
            "status": shadow.status.value,
            "price": shadow.price
        }), 200

    if fs.originalPrice is not None:
        shadow.price = fs.originalPrice
        shadow.original_price = fs.originalPrice
    shadow.status = ListingStatus.ACTIVE
    combined.status = ListingStatus.ACTIVE
    fs.farmerResponse = 'declined'
    db.session.delete(fs)
    db.session.commit()

    return jsonify({
        "message": "Cooperative flash sale declined, price restored",
        "combinedListingId": combined.combinedListingId,
        "listingId": shadow.listingId,
        "status": shadow.status.value,
        "price": shadow.price
    }), 200


def _own_stock_filter():
    return or_(CropListing.demandForecast.is_(None), CropListing.demandForecast != "Cooperative")


def _stock_map(farmer_ids=None):
    crop_key = db.func.lower(db.func.trim(CropListing.cropType))
    available = CropListing.quantity - db.func.coalesce(CropListing.reservedQuantity, 0)

    q = db.session.query(CropListing.farmerId, crop_key, db.func.sum(available)).filter(
        CropListing.status == ListingStatus.ACTIVE, _own_stock_filter()
    )
    if farmer_ids is not None:
        q = q.filter(CropListing.farmerId.in_(farmer_ids))
    q = q.group_by(CropListing.farmerId, crop_key)

    result = {}
    for fid, crop, qty in q.all():
        qty = float(qty or 0)
        if crop and qty > 0:
            result.setdefault(fid, {})[crop] = qty
    return result


@cooperative_bp.route('/cooperative/farmers', methods=['GET'])
@jwt_required()
def get_farmers():
    coop, err = get_coop()
    if err:
        return err

    stock = _stock_map()
    out = []
    for f in Farmer.query.all():
        if not f.user:
            continue
        out.append({
            "farmerId": f.farmerId,
            "name": f.user.name,
            "location": f.location,
            "rating": f.rating,
            "stock": stock.get(f.farmerId, {})
        })
    return jsonify(out), 200


@cooperative_bp.route('/cooperative/combined-listing', methods=['POST'])
@jwt_required()
def create_combined():
    coop, err = get_coop()
    if err:
        return err

    data = request.get_json() or {}
    fids = data.get('farmer_ids')
    crop = data.get('crop_type')
    total_qty = data.get('total_quantity')
    price = data.get('price_per_kg')
    expiry_date = data.get('expiry_date')

    if not all([fids, crop, total_qty, price, expiry_date]):
        return jsonify({"error": "farmer_ids, crop_type, total_quantity, price_per_kg and expiry_date required"}), 400
    if not isinstance(fids, list) or len(fids) == 0:
        return jsonify({"error": "farmer_ids must be non-empty list"}), 400

    try:
        fids = list(dict.fromkeys(int(x) for x in fids))
        total_qty = float(total_qty)
        price = float(price)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numbers"}), 400
    if total_qty <= 0 or price <= 0:
        return jsonify({"error": "Quantity and price must be greater than 0"}), 400

    try:
        expiry = datetime.strptime(str(expiry_date), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return jsonify({"error": "expiry_date must be in YYYY-MM-DD format"}), 400
    if expiry.date() < datetime.now(timezone.utc).date():
        return jsonify({"error": "Expiry date cannot be in the past"}), 400

    crop = str(crop).strip()
    crop_key = crop.lower()
    if not crop:
        return jsonify({"error": "crop_type cannot be empty"}), 400

    farmers = Farmer.query.filter(Farmer.farmerId.in_(fids)).all()
    if len(farmers) != len(fids):
        return jsonify({"error": "Some farmer IDs invalid"}), 400

    stock = _stock_map(fids)
    total_available = 0.0
    contributions = []
    for fid in fids:
        available = stock.get(fid, {}).get(crop_key, 0.0)
        if available <= 0:
            farmer_obj = db.session.get(Farmer, fid)
            farmer_name = farmer_obj.user.name if farmer_obj and farmer_obj.user else f"Farmer {fid}"
            return jsonify({"error": f"{farmer_name} has no active {crop} stock"}), 400
        total_available += available
        contributions.append({"farmerId": fid, "available": available})

    if total_available < total_qty:
        return jsonify({"error": f"Not enough total stock. Available: {total_available}, Requested: {total_qty}"}), 400

    display_crop = crop.title()
    cl = CooperativeListing(
        coopId=coop.coopId,
        cropType=display_crop,
        totalQuantity=total_qty,
        price=price,
        shelfLife=expiry,
        status=ListingStatus.ACTIVE,
        createdAt=datetime.now(timezone.utc)
    )
    db.session.add(cl)
    db.session.flush()

    remaining_total = round(total_qty, 2)
    for index, item in enumerate(contributions):
        farmer_id = item["farmerId"]
        available = item["available"]

        if index == len(contributions) - 1:
            farmer_contribution = round(remaining_total, 2)
        else:
            farmer_contribution = round((available / total_available) * total_qty, 2)
            farmer_contribution = min(farmer_contribution, remaining_total)

        if farmer_contribution <= 0:
            continue

        remaining_total = round(remaining_total - farmer_contribution, 2)
        db.session.add(CooperativeFarmer(
            combinedListingId=cl.combinedListingId,
            farmerId=farmer_id,
            quantityContributed=farmer_contribution
        ))

        source_listings = (CropListing.query
            .filter(
                CropListing.farmerId == farmer_id,
                CropListing.status == ListingStatus.ACTIVE,
                _own_stock_filter(),
                db.func.lower(db.func.trim(CropListing.cropType)) == crop_key
            )
            .order_by(CropListing.listingId.asc())
            .with_for_update()
            .all())

        remaining_farmer_qty = round(farmer_contribution, 2)
        for source in source_listings:
            available_source = round(source.quantity - (source.reservedQuantity or 0), 2)
            if available_source <= 0:
                continue

            allocation_qty = round(min(available_source, remaining_farmer_qty), 2)
            if allocation_qty <= 0:
                continue

            source.reservedQuantity = round((source.reservedQuantity or 0) + allocation_qty, 2)
            db.session.add(CooperativeSourceAllocation(
                combinedListingId=cl.combinedListingId,
                listingId=source.listingId,
                farmerId=farmer_id,
                quantityAllocated=allocation_qty
            ))

            remaining_farmer_qty = round(remaining_farmer_qty - allocation_qty, 2)
            if remaining_farmer_qty <= 0:
                break

        if remaining_farmer_qty > 0:
            db.session.rollback()
            return jsonify({"error": f"Unable to allocate complete stock for farmer {farmer_id}"}), 400

    if remaining_total > 0:
        db.session.rollback()
        return jsonify({"error": "Unable to allocate requested total quantity"}), 400

    shadow_listing = CropListing(
        farmerId=fids[0],
        cropType=display_crop,
        quantity=total_qty,
        price=price,
        original_price=price,
        shelfLife=expiry,
        status=ListingStatus.ACTIVE,
        demandForecast="Cooperative",
        cooperativeListingId=cl.combinedListingId,
        reservedQuantity=0.0
    )
    db.session.add(shadow_listing)
    db.session.flush()

    db.session.add(ListingPhoto(
        listingId=shadow_listing.listingId,
        photoURL=f"/static/crops/{crop_key}.jpg"
    ))
    db.session.commit()

    return jsonify({
        "message": "Combined listing created",
        "combinedListingId": cl.combinedListingId,
        "shadowListingId": shadow_listing.listingId,
        "farmersCount": len(fids),
        "shelfLife": expiry.isoformat()
    }), 201


@cooperative_bp.route('/cooperative/combined-listings', methods=['GET'])
@jwt_required()
def get_combined():
    coop, err = get_coop()
    if err:
        return err

    listings = (CooperativeListing.query.filter_by(coopId=coop.coopId)
                .order_by(CooperativeListing.createdAt.desc()).all())

    out = []
    for cl in listings:
        farmers_list = []
        for cf in cl.farmers:
            f = db.session.get(Farmer, cf.farmerId)
            if f and f.user:
                farmers_list.append({
                    "farmerId": f.farmerId,
                    "name": f.user.name,
                    "contribution": cf.quantityContributed
                })
        out.append({
            "combinedListingId": cl.combinedListingId,
            "cropType": cl.cropType,
            "totalQuantity": cl.totalQuantity,
            "price": cl.price,
            "status": cl.status.value,
            "createdAt": cl.createdAt.isoformat(),
            "shelfLife": cl.shelfLife.isoformat() if cl.shelfLife else None,
            "farmers": farmers_list
        })
    return jsonify(out), 200


@cooperative_bp.route('/cooperative/orders', methods=['GET'])
@jwt_required()
def get_cooperative_orders():
    coop, err = get_coop()
    if err:
        return err

    listings = CooperativeListing.query.filter_by(coopId=coop.coopId).all()
    listing_ids = [cl.shadow_listing.listingId for cl in listings if cl.shadow_listing]
    if not listing_ids:
        return jsonify([]), 200

    orders = (Order.query.filter(Order.listingId.in_(listing_ids))
              .order_by(Order.orderDate.desc()).all())

    out = []
    for o in orders:
        buyer_user = o.buyer.user if o.buyer else None
        out.append({
            "orderId": o.orderId,
            "cropType": o.cropTypeSnapshot or "N/A",
            "quantity": o.quantity,
            "totalAmount": o.totalAmount,
            "status": o.status.value,
            "orderDate": o.orderDate.isoformat(),
            "buyerName": buyer_user.name if buyer_user else "Unknown",
            "buyerPhone": buyer_user.phone if buyer_user else "",
            "buyerLocation": o.buyer.location if o.buyer else "",
            "deliveryPhoto": o.deliveryPhoto
        })
    return jsonify(out), 200