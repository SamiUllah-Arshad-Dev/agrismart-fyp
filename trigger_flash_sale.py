import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'agrismart.db')
print(f"DB Path: {DB_PATH}")
print(f"DB Exists: {os.path.exists(DB_PATH)}\n")

from flask import Flask
from models import db, CropListing, ListingStatus, FlashSale, FlashSaleStatus, Notification, NotificationType, User, UserRole
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {'timeout': 30, 'check_same_thread': False}
}
db.init_app(app)

with app.app_context():
    threshold = datetime.now(timezone.utc) + timedelta(days=2)
    listings = CropListing.query.filter(
        CropListing.status == ListingStatus.ACTIVE,
        CropListing.shelfLife <= threshold
    ).all()
    print(f"Found {len(listings)} near-expiry listings\n")
    triggered = 0
    for listing in listings:
        if FlashSale.query.filter_by(listingId=listing.listingId).first():
            print(f"  [SKIP] {listing.cropType} (already on flash sale)")
            continue
        original = listing.price
        discounted = round(original * 0.8, 2)
        db.session.add(FlashSale(
            listingId=listing.listingId,
            discountedPrice=discounted,
            originalPrice=original,
            expiryTime=listing.shelfLife,
            status=FlashSaleStatus.ACTIVE
        ))
        listing.status = ListingStatus.ON_FLASH_SALE
        listing.price = discounted
        listing.original_price = original
        for buyer in User.query.filter_by(role=UserRole.BUYER).all():
            db.session.add(Notification(
                recipientId=buyer.userId,
                message=f"Flash Sale! {listing.cropType} at Rs.{discounted}/kg",
                timestamp=datetime.now(timezone.utc),
                type=NotificationType.FLASH_SALE
            ))
        triggered += 1
        print(f"  [TRIGGERED] {listing.cropType} (ID: {listing.listingId}) Rs.{original} -> Rs.{discounted}")
    db.session.commit()
    print(f"\nDone! Triggered: {triggered}")