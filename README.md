# AgriSmart

AgriSmart is a web-based Final Year Project (FYP-2) built to connect farmers 
and buyers directly in Punjab, Pakistan. Farmers list their crops, buyers 
purchase through the platform, and an escrow-based order flow protects both 
sides.

The system has 4 user roles — Farmer, Buyer, Cooperative, and Admin — with 
JWT authentication and separate dashboards for each.

## Main Features

- ML-based price prediction and demand forecasting using Random Forest
- Escrow system — buyer's payment is held until delivery is confirmed
- Automatic flash sales for near-expiry crops (Wastage Monitor)
- Cooperative combined listings — small farmers pool their stock into one 
  batch and payout is split proportionally
- Dispute handling by admin (release, hold, refund)
- Notifications for orders, flash sales, and disputes
- Location stored for delivery coordination
- Rating system for farmers and cooperatives

## Technology Used

Backend: Python, Flask, Flask-JWT-Extended
Database: SQLite, Flask-SQLAlchemy
Frontend: HTML, CSS, Vanilla JavaScript
ML: scikit-learn (RandomForestRegressor), pandas, joblib
Scheduler: APScheduler
Auth: JWT

## How It Works

Normal Order:
Farmer creates listing -> Buyer places order -> Payment held in Escrow -> 
Buyer confirms delivery -> Escrow released to farmer -> Buyer rates farmer

Cooperative Order:
Cooperative selects multiple farmers -> Creates combined listing -> Backend 
calculates each farmer's contribution -> Shadow listing created for buyer -> 
Buyer purchases -> CooperativeOrderShare records payout split -> Escrow 
released proportionally to each farmer

Dispute:
Buyer raises dispute -> Escrow status becomes DISPUTED -> Admin resolves 
with release, hold, or refund -> Wallets updated and notifications sent

Flash Sale:
Wastage Monitor runs every 6 hours -> Near-expiry listings detected -> 
Automatic flash sale triggered -> Farmers and cooperatives can Accept/Decline 
-> Buyers notified and can purchase at discounted price

## Database

16 tables in total:

User + Profiles: User, Farmer, Buyer, Admin, Cooperative
Core: CropListing, ListingPhoto, Order, Escrow, Rating, FlashSale, 
Notification, WastageMonitor
Cooperative: CooperativeListing, CooperativeFarmer, 
CooperativeSourceAllocation, CooperativeOrderShare

## Team Work

Backend, Database and ML: Config, models, app setup, auth, farmer/buyer/
cooperative/admin backends, ML model, wastage monitor

Frontend: HTML templates, CSS, JavaScript

BS Information Technology — FYP-2
