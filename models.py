from flask_sqlalchemy import SQLAlchemy
from enum import Enum

db = SQLAlchemy()


# all enum types used in the project
class UserRole(Enum):
    FARMER = 'farmer'
    BUYER = 'buyer'
    ADMIN = 'admin'
    COOPERATIVE = 'cooperative'


class ListingStatus(Enum):
    ACTIVE = 'active'
    SOLD = 'sold'
    EXPIRED = 'expired'
    ON_FLASH_SALE = 'on_flash_sale'


class OrderStatus(Enum):
    PENDING = 'pending'
    PAID = 'paid'
    DELIVERED = 'delivered'
    DISPUTED = 'disputed'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'


class EscrowStatus(Enum):
    HELD = 'held'
    RELEASED = 'released'
    DISPUTED = 'disputed'
    REFUNDED = 'refunded'


class FlashSaleStatus(Enum):
    ACTIVE = 'active'
    ENDED = 'ended'
    OVERRIDDEN = 'overridden'


class NotificationType(Enum):
    FLASH_SALE = 'flash_sale'
    ORDER_UPDATE = 'order_update'
    DISPUTE_UPDATE = 'dispute_update'


# base user table - all roles share this
class User(db.Model):
    __tablename__ = 'user'

    userId = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    passwordHash = db.Column(db.String(255), nullable=False)
    cnic = db.Column(db.String(15), unique=True, nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False)
    walletBalance = db.Column(db.Float, default=0.0)
    phone = db.Column(db.String(20), nullable=False)
    isVerified = db.Column(db.Boolean, default=False)
    emailVerified = db.Column(db.Boolean, default=False)

    # one-to-one links to role tables
    farmer = db.relationship('Farmer', backref='user', uselist=False, cascade='all, delete-orphan')
    buyer = db.relationship('Buyer', backref='user', uselist=False, cascade='all, delete-orphan')
    admin = db.relationship('Admin', backref='user', uselist=False, cascade='all, delete-orphan')
    cooperative = db.relationship('Cooperative', backref='user', uselist=False, cascade='all, delete-orphan')

    notifications = db.relationship('Notification', backref='user', lazy='dynamic')


# farmer profile - linked to user
class Farmer(db.Model):
    __tablename__ = 'farmer'

    farmerId = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey('user.userId'), unique=True, nullable=False)

    location = db.Column(db.String(200))
    farmSize = db.Column(db.String(50))
    rating = db.Column(db.Float, default=0.0)

    listings = db.relationship('CropListing', backref='farmer', lazy='dynamic', cascade='all, delete-orphan')

    cooperative = db.relationship('Cooperative', backref='farmer', uselist=False, cascade='all, delete-orphan')


# buyer profile - linked to user
class Buyer(db.Model):
    __tablename__ = 'buyer'

    buyerId = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey('user.userId'), unique=True, nullable=False)

    businessType = db.Column(db.String(100))
    location = db.Column(db.String(200))

    orders = db.relationship('Order', backref='buyer', lazy='dynamic')


# admin profile
class Admin(db.Model):
    __tablename__ = 'admin'

    adminId = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey('user.userId'), unique=True, nullable=False)

    role = db.Column(db.String(50))


# cooperative profile - optionally linked to a farmer
class Cooperative(db.Model):
    __tablename__ = 'cooperative'

    coopId = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey('user.userId'), unique=True, nullable=False)
    farmerId = db.Column(db.Integer, db.ForeignKey('farmer.farmerId'), unique=True, nullable=True)

    # Location added for cooperative coordination
    location = db.Column(db.String(200))

    combined_listings = db.relationship('CooperativeListing', backref='cooperative', lazy='dynamic')


# crop listing created by farmers
class CropListing(db.Model):
    __tablename__ = 'croplisting'

    listingId = db.Column(db.Integer, primary_key=True)
    farmerId = db.Column(db.Integer, db.ForeignKey('farmer.farmerId'), nullable=False)

    cropType = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float, nullable=True)
    shelfLife = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.Enum(ListingStatus), default=ListingStatus.ACTIVE)

    demandForecast = db.Column(db.String(50))

    # Links the buyer-facing shadow listing to its CooperativeListing.
    cooperativeListingId = db.Column(
        db.Integer,
        db.ForeignKey('cooperative_listing.combinedListingId'),
        nullable=True,
        unique=True
    )

    # Quantity reserved from this farmer listing for a cooperative combined listing.
    reservedQuantity = db.Column(db.Float, nullable=False, default=0.0)

    photos = db.relationship('ListingPhoto', backref='listing', lazy='dynamic', cascade='all, delete-orphan')
    flash_sale = db.relationship('FlashSale', backref='listing', uselist=False)

    # Explicit relationship to the cooperative batch.
    cooperative_listing = db.relationship(
        'CooperativeListing',
        back_populates='shadow_listing',
        foreign_keys=[cooperativeListingId]
    )


# photos for listings (composite key)
class ListingPhoto(db.Model):
    __tablename__ = 'listing_photos'

    listingId = db.Column(db.Integer, db.ForeignKey('croplisting.listingId'), primary_key=True)
    photoURL = db.Column(db.String(500), primary_key=True)


# order placed by buyer
class Order(db.Model):
    __tablename__ = 'order'

    orderId = db.Column(db.Integer, primary_key=True)
    buyerId = db.Column(db.Integer, db.ForeignKey('buyer.buyerId'), nullable=False)
    listingId = db.Column(db.Integer, db.ForeignKey('croplisting.listingId'), nullable=False)

    orderDate = db.Column(db.DateTime, nullable=False)
    deliveredAt = db.Column(db.DateTime, nullable=True)
    quantity = db.Column(db.Float, nullable=True)
    totalAmount = db.Column(db.Float, nullable=False)

    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.PENDING)

    deliveryPhoto = db.Column(db.String(500))
    cropTypeSnapshot = db.Column(db.String(100))
    priceAtOrder = db.Column(db.Float)

    listing = db.relationship('CropListing', backref='orders')
    escrow = db.relationship('Escrow', backref='order', uselist=False)
    ratings = db.relationship('Rating', backref='order', lazy='dynamic')


# escrow for each order
class Escrow(db.Model):
    __tablename__ = 'escrow'

    escrowId = db.Column(db.Integer, primary_key=True)
    orderId = db.Column(db.Integer, db.ForeignKey('order.orderId'), unique=True, nullable=False)

    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(EscrowStatus), default=EscrowStatus.HELD)


# rating from buyer or farmer
class Rating(db.Model):
    __tablename__ = 'rating'

    ratingId = db.Column(db.Integer, primary_key=True)
    reviewerId = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)
    revieweeId = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)
    orderId = db.Column(db.Integer, db.ForeignKey('order.orderId'), nullable=False)

    score = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text)


# flash sale record for near-expiry listings
class FlashSale(db.Model):
    __tablename__ = 'flashsale'

    flashSaleId = db.Column(db.Integer, primary_key=True)
    listingId = db.Column(db.Integer, db.ForeignKey('croplisting.listingId'), unique=True, nullable=False)

    discountedPrice = db.Column(db.Float, nullable=False)
    originalPrice = db.Column(db.Float, nullable=False)
    expiryTime = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.Enum(FlashSaleStatus), default=FlashSaleStatus.ACTIVE)
    farmerResponse = db.Column(db.String(20), nullable=True)


# notifications sent to users
class Notification(db.Model):
    __tablename__ = 'notification'

    notifId = db.Column(db.Integer, primary_key=True)
    recipientId = db.Column(db.Integer, db.ForeignKey('user.userId'), nullable=False)

    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    type = db.Column(db.Enum(NotificationType))
    isRead = db.Column(db.Boolean, default=False)


# wastage monitor settings
class WastageMonitor(db.Model):
    __tablename__ = 'wastagemonitor'

    monitorId = db.Column(db.Integer, primary_key=True)
    checkInterval = db.Column(db.Integer, default=6)


# cooperative combined listings
class CooperativeListing(db.Model):
    __tablename__ = 'cooperative_listing'

    combinedListingId = db.Column(db.Integer, primary_key=True)
    coopId = db.Column(db.Integer, db.ForeignKey('cooperative.coopId'), nullable=False)

    cropType = db.Column(db.String(100), nullable=False)
    totalQuantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)

    # Expiry of the complete cooperative batch.
    shelfLife = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.Enum(ListingStatus), default=ListingStatus.ACTIVE)
    createdAt = db.Column(db.DateTime, nullable=False)

    farmers = db.relationship('CooperativeFarmer', backref='listing', cascade='all, delete-orphan')

    # One buyer-facing CropListing represents this cooperative batch.
    shadow_listing = db.relationship(
        'CropListing',
        back_populates='cooperative_listing',
        uselist=False,
        foreign_keys='CropListing.cooperativeListingId'
    )

    # Source stock allocations for this batch.
    source_allocations = db.relationship(
        'CooperativeSourceAllocation',
        backref='cooperative_listing',
        cascade='all, delete-orphan'
    )


# bridge table - cooperative listing <-> farmer
class CooperativeFarmer(db.Model):
    __tablename__ = 'cooperative_farmer'

    combinedListingId = db.Column(
        db.Integer,
        db.ForeignKey('cooperative_listing.combinedListingId'),
        primary_key=True
    )
    farmerId = db.Column(db.Integer, db.ForeignKey('farmer.farmerId'), primary_key=True)

    quantityContributed = db.Column(db.Float, nullable=False)


# tracks exactly which farmer listing supplied a cooperative combined batch
class CooperativeSourceAllocation(db.Model):
    __tablename__ = 'cooperative_source_allocation'

    allocationId = db.Column(db.Integer, primary_key=True)
    combinedListingId = db.Column(
        db.Integer,
        db.ForeignKey('cooperative_listing.combinedListingId'),
        nullable=False
    )
    listingId = db.Column(db.Integer, db.ForeignKey('croplisting.listingId'), nullable=False)
    farmerId = db.Column(db.Integer, db.ForeignKey('farmer.farmerId'), nullable=False)

    quantityAllocated = db.Column(db.Float, nullable=False)

    source_listing = db.relationship(
        'CropListing',
        foreign_keys=[listingId],
        backref='cooperative_allocations'
    )


# snapshots how a cooperative order's payment is distributed among contributing farmers
class CooperativeOrderShare(db.Model):
    __tablename__ = 'cooperative_order_share'

    shareId = db.Column(db.Integer, primary_key=True)
    orderId = db.Column(db.Integer, db.ForeignKey('order.orderId'), nullable=False)
    farmerId = db.Column(db.Integer, db.ForeignKey('farmer.farmerId'), nullable=False)

    quantityShare = db.Column(db.Float, nullable=False)
    amountShare = db.Column(db.Float, nullable=False)

    order = db.relationship(
        'Order',
        backref=db.backref('cooperative_shares', cascade='all, delete-orphan')
    )