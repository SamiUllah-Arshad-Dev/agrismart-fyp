from datetime import datetime, timedelta, timezone

from models import (
    db, CropListing, ListingStatus, FlashSale, FlashSaleStatus,
    Notification, NotificationType, User, UserRole
)
from config import Config


def check_and_trigger_flash_sales():
    print("wastage monitor running at", datetime.now(timezone.utc).isoformat())

    threshold = datetime.now(timezone.utc) + timedelta(days=Config.FLASH_SALE_THRESHOLD_DAYS)
    listings = CropListing.query.filter(
        CropListing.status == ListingStatus.ACTIVE,
        CropListing.shelfLife <= threshold
    ).all()

    triggered = 0
    skipped = 0

    for listing in listings:
        existing_fs = FlashSale.query.filter_by(listingId=listing.listingId).first()
        if existing_fs:
            print("skip", listing.cropType, "listing", listing.listingId, "- already on flash sale")
            skipped += 1
            continue

        original_price = listing.price
        discounted = round(original_price * (1 - Config.FLASH_SALE_DISCOUNT), 2)

        fs = FlashSale(
            listingId=listing.listingId,
            discountedPrice=discounted,
            originalPrice=original_price,
            expiryTime=listing.shelfLife,
            status=FlashSaleStatus.ACTIVE
        )
        db.session.add(fs)

        listing.status = ListingStatus.ON_FLASH_SALE
        listing.price = discounted
        listing.original_price = original_price

        # Location-based filtering: nearby buyers only
        buyers = User.query.filter_by(role=UserRole.BUYER).all()
        farmer_location = (
            listing.farmer.location.strip().lower()
            if listing.farmer and listing.farmer.location
            else None
        )

        notified_count = 0
        for buyer in buyers:
            buyer_location = (
                buyer.buyer.location.strip().lower()
                if buyer.buyer and buyer.buyer.location
                else None
            )

            # Send to buyer if:
            # 1. Location matches (case-insensitive), OR
            # 2. Either location missing (fallback — don't miss buyers)
            if not farmer_location or not buyer_location or buyer_location == farmer_location:
                db.session.add(Notification(
                    recipientId=buyer.userId,
                    message=f"Flash Sale! {listing.cropType} at Rs.{discounted}/kg (was Rs.{original_price})",
                    timestamp=datetime.now(timezone.utc),
                    type=NotificationType.FLASH_SALE
                ))
                notified_count += 1

        print(f"  -> Notified {notified_count} nearby buyer(s) for listing {listing.listingId}")

        triggered += 1
        print("triggered", listing.cropType, "listing", listing.listingId, "->", discounted)

    db.session.commit()
    print("done. triggered:", triggered, "skipped:", skipped)