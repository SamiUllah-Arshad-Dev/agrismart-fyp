import os
import uuid
import random
from datetime import datetime, timezone

import joblib
import pandas as pd
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from models import (
    db, User, UserRole, Farmer, CropListing, ListingStatus, ListingPhoto,
    Escrow, Order, FlashSale, FlashSaleStatus, Notification,
    NotificationType, CooperativeListing, CooperativeFarmer,
    CooperativeOrderShare
)

farmer_bp = Blueprint('farmer', __name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'model.pkl')

ml_model = None
try:
    ml_model = joblib.load(MODEL_PATH)
    print("ML Model loaded successfully!")
except Exception as e:
    print(f"ML Model not loaded (using fallback): {e}")

ALLOWED_PHOTO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def allowed_photo(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS


def save_photos(files, listing_id):
    folder = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads')
    os.makedirs(folder, exist_ok=True)

    for f in files:
        if f and f.filename and allowed_photo(f.filename):
            name = secure_filename(f"{uuid.uuid4().hex}_{f.filename}")
            path = os.path.join(folder, name)
            f.save(path)
            db.session.add(ListingPhoto(
                listingId=listing_id,
                photoURL=f"/static/uploads/{name}"
            ))


def get_farmer():
    uid = get_jwt_identity()
    try:
        uid = int(uid)
    except (ValueError, TypeError):
        return None, (jsonify({"error": "Invalid identity"}), 401)

    user = db.session.get(User, uid)
    if not user or user.role != UserRole.FARMER:
        return None, (jsonify({"error": "Farmer only"}), 403)

    farmer = Farmer.query.filter_by(userId=uid).first()
    if not farmer:
        return None, (jsonify({"error": "Farmer profile missing"}), 404)

    return farmer, None


def ml_forecast(crop_type):
    month = datetime.now().month
    if month in [12, 1, 2]:
        season = 'Winter'
    elif month in [3, 4, 5]:
        season = 'Spring'
    elif month in [6, 7, 8]:
        season = 'Summer'
    else:
        season = 'Autumn'

    region = 'Punjab'

    if ml_model is not None:
        try:
            input_df = pd.DataFrame([[crop_type, season, region]],
                                    columns=['crop_type', 'season', 'region'])
            prediction = ml_model.predict(input_df)
            price = round(prediction[0][0], 2)
            demand_val = prediction[0][1]
            demand_map = {
                2: 'High (Rising)',
                1: 'Medium (Stable)',
                0: 'Low (Oversupply)'
            }
            demand = demand_map.get(round(demand_val), 'Medium (Stable)')
            return price, demand
        except Exception as e:
            print(f"ML Prediction error: {e}. Using fallback.")

    base = random.randint(50, 300)
    rec = max(10, base + random.randint(-20, 30))
    demand = random.choice(['High (Rising)', 'Medium (Stable)', 'Low (Oversupply)'])
    return rec, demand


@farmer_bp.route('/ml/forecast', methods=['POST'])
@jwt_required()
def forecast():
    data = request.get_json()
    crop = data.get('crop_type')
    if not crop:
        return jsonify({"error": "crop_type required"}), 400

    price, demand = ml_forecast(crop)
    return jsonify({
        "recommended_price": price,
        "demand_forecast": demand
    }), 200


@farmer_bp.route('/listings', methods=['POST'])
@jwt_required()
def create_listing():
    farmer, err = get_farmer()
    if err:
        return err

    form = request.form
    files = request.files.getlist('photos')
    crop = form.get('crop_type')
    qty = form.get('quantity')
    exp = form.get('expiry_date')
    price_in = form.get('price')

    if not all([crop, qty, exp]):
        return jsonify({"error": "crop_type, quantity, expiry_date required"}), 400

    try:
        qty = float(qty)
    except ValueError:
        return jsonify({"error": "quantity must be number"}), 400
    if qty <= 0:
        return jsonify({"error": "quantity must be > 0"}), 400

    ml_price, demand = ml_forecast(crop)

    if price_in and price_in.strip():
        try:
            price = float(price_in)
        except ValueError:
            return jsonify({"error": "invalid price"}), 400
        if price <= 0:
            return jsonify({"error": "price must be > 0"}), 400
    else:
        price = ml_price

    try:
        shelf = datetime.strptime(exp, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "date format YYYY-MM-DD"}), 400

    listing = CropListing(
        farmerId=farmer.farmerId,
        cropType=crop,
        quantity=qty,
        price=price,
        shelfLife=shelf,
        status=ListingStatus.ACTIVE,
        demandForecast=demand,
        original_price=price
    )
    db.session.add(listing)
    db.session.flush()

    if files:
        save_photos(files, listing.listingId)

    db.session.commit()
    return jsonify({
        "message": "Listing created",
        "listingId": listing.listingId,
        "recommended_price": price,
        "demand_forecast": demand
    }), 201


@farmer_bp.route('/listings', methods=['GET'])
@jwt_required()
def get_listings():
    farmer, err = get_farmer()
    if err:
        return err

    listings = CropListing.query.filter(
        CropListing.farmerId == farmer.farmerId,
        CropListing.cooperativeListingId.is_(None)
    ).all()

    result = []
    for l in listings:
        result.append({
            "listingId": l.listingId,
            "cropType": l.cropType,
            "quantity": l.quantity,
            "price": l.price,
            "shelfLife": l.shelfLife.isoformat() if l.shelfLife else None,
            "status": l.status.value,
            "demandForecast": l.demandForecast,
            "photos": [p.photoURL for p in l.photos],
            "listingType": "farmer"
        })

    cooperative_links = CooperativeFarmer.query.filter_by(farmerId=farmer.farmerId).all()
    for link in cooperative_links:
        combined = db.session.get(CooperativeListing, link.combinedListingId)
        if not combined:
            continue
        result.append({
            "listingId": combined.combinedListingId,
            "cropType": combined.cropType,
            "quantity": link.quantityContributed,
            "totalQuantity": combined.totalQuantity,
            "price": combined.price,
            "status": combined.status.value,
            "listingType": "cooperative",
            "contributedQuantity": link.quantityContributed,
            "shelfLife": combined.shelfLife.isoformat() if combined.shelfLife else None,
            "demandForecast": None,
            "photos": []
        })

    return jsonify(result), 200


@farmer_bp.route('/listings/<int:lid>', methods=['PUT'])
@jwt_required()
def update_listing(lid):
    farmer, err = get_farmer()
    if err:
        return err

    listing = db.session.get(CropListing, lid)
    if not listing or listing.farmerId != farmer.farmerId:
        return jsonify({"error": "Not found or not yours"}), 404

    if request.content_type and 'multipart/form-data' in request.content_type:
        crop_type = request.form.get('crop_type')
        quantity = request.form.get('quantity')
        price = request.form.get('price')
        expiry_date = request.form.get('expiry_date')

        crop_type_changed = False
        if crop_type:
            if crop_type.strip() != listing.cropType:
                crop_type_changed = True
            listing.cropType = crop_type.strip()

        if quantity:
            try:
                quantity = float(quantity)
            except ValueError:
                return jsonify({"error": "Invalid quantity"}), 400
            if quantity <= 0:
                return jsonify({"error": "quantity must be > 0"}), 400
            listing.quantity = quantity

        if price:
            try:
                price = float(price)
            except ValueError:
                return jsonify({"error": "Invalid price"}), 400
            if price <= 0:
                return jsonify({"error": "price must be > 0"}), 400
            listing.price = price

        if expiry_date:
            try:
                listing.shelfLife = datetime.strptime(expiry_date, '%Y-%m-%d')
            except ValueError:
                return jsonify({"error": "date format YYYY-MM-DD"}), 400

        new_photo_uploaded = False
        if 'photo' in request.files:
            photo_file = request.files['photo']
            if photo_file and photo_file.filename:
                if not allowed_photo(photo_file.filename):
                    return jsonify({"error": "Unsupported photo type"}), 400

                new_photo_uploaded = True
                for old_photo in listing.photos:
                    old_path = os.path.join(
                        os.path.dirname(__file__), '..',
                        old_photo.photoURL.lstrip('/')
                    )
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass
                    db.session.delete(old_photo)
                db.session.flush()

                folder = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads')
                os.makedirs(folder, exist_ok=True)
                name = secure_filename(f"{uuid.uuid4().hex}_{photo_file.filename}")
                path = os.path.join(folder, name)
                photo_file.save(path)
                db.session.add(ListingPhoto(
                    listingId=lid,
                    photoURL=f"/static/uploads/{name}"
                ))

        if crop_type_changed and not new_photo_uploaded:
            for old_photo in listing.photos:
                old_path = os.path.join(
                    os.path.dirname(__file__), '..',
                    old_photo.photoURL.lstrip('/')
                )
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception:
                        pass
                db.session.delete(old_photo)

        db.session.commit()
        return jsonify({"message": "Listing updated successfully"}), 200

    else:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Invalid or missing body"}), 400

        if 'crop_type' in data:
            crop_type = str(data['crop_type']).strip()
            if not crop_type:
                return jsonify({"error": "crop_type cannot be empty"}), 400
            listing.cropType = crop_type

        if 'quantity' in data:
            try:
                quantity = float(data['quantity'])
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid quantity"}), 400
            if quantity <= 0:
                return jsonify({"error": "quantity must be > 0"}), 400
            listing.quantity = quantity

        if 'price' in data:
            try:
                price = float(data['price'])
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid price"}), 400
            if price <= 0:
                return jsonify({"error": "price must be > 0"}), 400
            listing.price = price

        if 'expiry_date' in data:
            try:
                listing.shelfLife = datetime.strptime(data['expiry_date'], '%Y-%m-%d')
            except (ValueError, TypeError):
                return jsonify({"error": "date format YYYY-MM-DD"}), 400

        db.session.commit()
        return jsonify({"message": "Listing updated"}), 200


@farmer_bp.route('/listings/<int:lid>', methods=['DELETE'])
@jwt_required()
def delete_listing(lid):
    farmer, err = get_farmer()
    if err:
        return err

    listing = db.session.get(CropListing, lid)
    if not listing or listing.farmerId != farmer.farmerId:
        return jsonify({"error": "Not found or not yours"}), 404

    order_count = Order.query.filter_by(listingId=lid).count()
    if order_count > 0:
        return jsonify({
            "error": f"Cannot delete: {order_count} order(s) on this listing. Mark as EXPIRED instead."
        }), 400

    for old_photo in listing.photos:
        old_path = os.path.join(
            os.path.dirname(__file__), '..',
            old_photo.photoURL.lstrip('/')
        )
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    fs = FlashSale.query.filter_by(listingId=lid).first()
    if fs:
        db.session.delete(fs)

    db.session.delete(listing)
    db.session.commit()
    return jsonify({"message": "Listing deleted successfully"}), 200


@farmer_bp.route('/listings/<int:lid>/mark-expired', methods=['POST'])
@jwt_required()
def mark_listing_expired(lid):
    farmer, err = get_farmer()
    if err:
        return err

    listing = db.session.get(CropListing, lid)
    if not listing or listing.farmerId != farmer.farmerId:
        return jsonify({"error": "Not found or not yours"}), 404

    if listing.status == ListingStatus.EXPIRED:
        return jsonify({"error": "Already expired"}), 400

    fs = FlashSale.query.filter_by(listingId=lid).first()
    if fs:
        db.session.delete(fs)

    if listing.original_price:
        listing.price = listing.original_price
    listing.status = ListingStatus.EXPIRED

    db.session.commit()
    return jsonify({"message": "Listing marked as EXPIRED"}), 200


@farmer_bp.route('/listings/<int:lid>/start-flash-sale', methods=['POST'])
@jwt_required()
def start_flash_sale(lid):
    from config import Config

    farmer, err = get_farmer()
    if err:
        return err

    listing = db.session.get(CropListing, lid)
    if not listing or listing.farmerId != farmer.farmerId:
        return jsonify({"error": "Not found or not yours"}), 404
    if listing.status == ListingStatus.ON_FLASH_SALE:
        return jsonify({"error": "Already on flash sale"}), 400
    if listing.status != ListingStatus.ACTIVE:
        return jsonify({"error": "Only active listings can go on flash sale"}), 400

    data = request.get_json() or {}
    discount = float(data.get('discount', Config.FLASH_SALE_DISCOUNT))

    if not (Config.FLASH_SALE_MIN_DISCOUNT <= discount <= Config.FLASH_SALE_MAX_DISCOUNT):
        return jsonify({
            "error": (
                f"Discount must be between "
                f"{int(Config.FLASH_SALE_MIN_DISCOUNT * 100)}% "
                f"and {int(Config.FLASH_SALE_MAX_DISCOUNT * 100)}%"
            )
        }), 400

    original = listing.price
    discounted = round(original * (1 - discount), 2)

    fs = FlashSale(
        listingId=lid,
        discountedPrice=discounted,
        originalPrice=original,
        expiryTime=listing.shelfLife,
        status=FlashSaleStatus.ACTIVE,
        farmerResponse='accepted'
    )
    db.session.add(fs)
    listing.status = ListingStatus.ON_FLASH_SALE
    listing.price = discounted
    listing.original_price = original

    buyers = User.query.filter_by(role=UserRole.BUYER).all()
    for buyer in buyers:
        db.session.add(Notification(
            recipientId=buyer.userId,
            message=f"Flash Sale! {listing.cropType} at Rs.{discounted}/kg (was Rs.{original})",
            timestamp=datetime.now(timezone.utc),
            type=NotificationType.FLASH_SALE
        ))

    db.session.commit()
    return jsonify({
        "message": "Flash sale started",
        "listingId": lid,
        "originalPrice": original,
        "discountedPrice": discounted,
        "discount": int(discount * 100)
    }), 201


@farmer_bp.route('/listings/<int:lid>/edit-flash-sale', methods=['POST'])
@jwt_required()
def edit_flash_sale(lid):
    from config import Config

    farmer, err = get_farmer()
    if err:
        return err

    listing = db.session.get(CropListing, lid)
    if not listing or listing.farmerId != farmer.farmerId:
        return jsonify({"error": "Not found or not yours"}), 404
    if listing.status != ListingStatus.ON_FLASH_SALE:
        return jsonify({"error": "Not on flash sale"}), 400

    data = request.get_json() or {}
    discount = float(data.get('discount', Config.FLASH_SALE_DISCOUNT))

    if not (Config.FLASH_SALE_MIN_DISCOUNT <= discount <= Config.FLASH_SALE_MAX_DISCOUNT):
        return jsonify({
            "error": (
                f"Discount must be between "
                f"{int(Config.FLASH_SALE_MIN_DISCOUNT * 100)}% "
                f"and {int(Config.FLASH_SALE_MAX_DISCOUNT * 100)}%"
            )
        }), 400

    original = listing.original_price or listing.price
    discounted = round(original * (1 - discount), 2)

    fs = FlashSale.query.filter_by(listingId=lid).first()
    if fs:
        fs.discountedPrice = discounted
        fs.originalPrice = original

    listing.price = discounted
    db.session.commit()
    return jsonify({
        "message": "Flash sale discount updated",
        "originalPrice": original,
        "discountedPrice": discounted,
        "discount": int(discount * 100)
    }), 200


@farmer_bp.route('/listings/<int:lid>/end-flash-sale', methods=['POST'])
@jwt_required()
def end_flash_sale(lid):
    farmer, err = get_farmer()
    if err:
        return err

    listing = db.session.get(CropListing, lid)
    if not listing or listing.farmerId != farmer.farmerId:
        return jsonify({"error": "Not found or not yours"}), 404
    if listing.status != ListingStatus.ON_FLASH_SALE:
        return jsonify({"error": "Not on flash sale"}), 400

    if listing.original_price:
        listing.price = listing.original_price
    listing.status = ListingStatus.ACTIVE

    fs = FlashSale.query.filter_by(listingId=lid).first()
    if fs:
        db.session.delete(fs)

    db.session.commit()
    return jsonify({"message": "Flash sale ended, listing active again"}), 200


@farmer_bp.route('/escrow/history', methods=['GET'])
@jwt_required()
def escrow_history():
    farmer, err = get_farmer()
    if err:
        return err

    normal_orders = (
        Order.query
        .join(CropListing)
        .filter(CropListing.farmerId == farmer.farmerId)
        .all()
    )

    coop_shares = CooperativeOrderShare.query.filter_by(farmerId=farmer.farmerId).all()

    existing_ids = [o.orderId for o in normal_orders]
    coop_order_ids = [s.orderId for s in coop_shares if s.orderId not in existing_ids]

    coop_orders = []
    if coop_order_ids:
        coop_orders = Order.query.filter(Order.orderId.in_(coop_order_ids)).all()

    all_orders = normal_orders + coop_orders

    result = []
    for o in all_orders:
        esc = o.escrow

        buyer_name = 'N/A'
        buyer_location = 'N/A'
        buyer_phone = 'N/A'
        try:
            if o.buyer and o.buyer.user:
                buyer_name = o.buyer.user.name
                buyer_location = o.buyer.location or 'N/A'
                buyer_phone = o.buyer.user.phone or 'N/A'
        except Exception:
            pass

        crop_name = o.cropTypeSnapshot
        if not crop_name and o.listing:
            crop_name = o.listing.cropType
        crop_name = crop_name or 'N/A'

        coop_share = CooperativeOrderShare.query.filter_by(
            orderId=o.orderId,
            farmerId=farmer.farmerId
        ).first()

        if coop_share:
            amount = coop_share.amountShare
        else:
            amount = esc.amount if esc else 0

        result.append({
            "orderId": o.orderId,
            "buyerName": buyer_name,
            "buyerPhone": buyer_phone,
            "buyerLocation": buyer_location,
            "cropType": crop_name,
            "amount": amount,
            "escrowStatus": esc.status.value if esc else None,
            "orderStatus": o.status.value,
            "orderDate": o.orderDate.isoformat()
        })

    return jsonify(result), 200


@farmer_bp.route('/flash-sale/respond', methods=['POST'])
@jwt_required()
def respond_flash():
    farmer, err = get_farmer()
    if err:
        return err

    data = request.get_json()
    lid = data.get('listing_id')
    accept = data.get('accept', True)

    listing = db.session.get(CropListing, lid)
    if not listing or listing.farmerId != farmer.farmerId:
        return jsonify({"error": "Listing not found"}), 404
    if listing.status != ListingStatus.ON_FLASH_SALE:
        return jsonify({"error": "Not on flash sale"}), 400

    if accept:
        fs = FlashSale.query.filter_by(listingId=lid).first()
        if fs:
            fs.farmerResponse = 'accepted'
            db.session.commit()
        return jsonify({"message": "Flash sale accepted"}), 200
    else:
        if listing.original_price:
            listing.price = listing.original_price
        listing.status = ListingStatus.ACTIVE

        fs = FlashSale.query.filter_by(listingId=lid).first()
        if fs:
            db.session.delete(fs)

        db.session.commit()
        return jsonify({"message": "Flash sale declined, price restored"}), 200


@farmer_bp.route('/flash-sale/my-alerts', methods=['GET'])
@jwt_required()
def my_flash_alerts():
    farmer, err = get_farmer()
    if err:
        return err

    listings = CropListing.query.filter(
        CropListing.farmerId == farmer.farmerId,
        CropListing.status == ListingStatus.ON_FLASH_SALE,
        CropListing.cooperativeListingId.is_(None)
    ).all()

    res = []
    for l in listings:
        res.append({
            "listingId": l.listingId,
            "cropType": l.cropType,
            "quantity": l.quantity,
            "discountedPrice": l.price,
            "originalPrice": l.original_price,
            "expiryDate": l.shelfLife.isoformat(),
            "farmerResponse": l.flash_sale.farmerResponse if l.flash_sale else None,
            "photos": [p.photoURL for p in l.photos]
        })
    return jsonify(res), 200