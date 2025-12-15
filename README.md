# Subscription & Entitlement Engine

A backend-first **Subscription & Entitlement Management System** built with **Django and Django REST Framework**. This application manages **plans, subscriptions, usage limits, and meters** in a clean, scalable, and industry-aligned way.

---

## 🚀 Features

* 🔐 **JWT Authentication** (Login / Secure APIs)
* 📦 **Subscription Plans** (Free, Basic, Pro, etc.)
* 📊 **Usage Meters** (API calls, credits, feature usage)
* 🚦 **Entitlements & Limits** per plan
* 🔁 **Atomic Transactions** (ACID compliant)
* 🧩 **Modular App Design** (Subscriptions, Metering, Core)
* 📈 **Scalable & Production-Ready Architecture**

---

## 🏗️ Tech Stack

* **Backend:** Django 5.x, Django REST Framework
* **Auth:** JWT (djangorestframework-simplejwt)
* **Database:** PostgreSQL (SQLite for local dev)
* **Caching (optional):** Redis
* **API Docs:** DRF / Swagger (optional)

---

## 📁 Project Structure

```
subscriptionEngine/
│── core/              # Users, base models, utilities
│── subscriptions/     # Plans, subscriptions, entitlements
│── metering/          # Usage meters & limits
│── resources/         # Courts, coaches, equipment (if enabled)
│── manage.py
│── requirements.txt
```

---

## 🔐 Authentication Flow

1. User logs in using `/api/token/`
2. Receives **access & refresh tokens**
3. Access token is sent in headers:

```
Authorization: Bearer <access_token>
```

4. Protected APIs validate subscription & limits

---

## 📦 Subscription Flow (High Level)

1. User subscribes to a plan
2. Plan defines:

   * Feature access
   * Usage limits
3. Each API call:

   * Checks active subscription
   * Validates entitlement
   * Updates usage meter atomically

---

## 🧠 Key Concepts Used

* **ACID Transactions** (`transaction.atomic()`)
* **Row-level locking** to prevent race conditions
* **Clean separation of concerns**
* **RESTful API design**

---

## ⚙️ Setup Instructions

### 1️⃣ Clone Repository

```bash
git clone <repo-url>
cd subscriptionEngine
```

### 2️⃣ Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\\Scripts\\activate
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Configure Database

Update `settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'subscription_db',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 5️⃣ Migrate & Run

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

---

## 🧪 API Example

**Get active subscription details**

```
GET /api/subscriptions/me/
```

**Response:**

```json
{
  "plan": "Pro",
  "limits": {
    "api_calls": 1000
  },
  "usage": {
    "api_calls": 120
  }
}
```

---



## 🔮 Future Enhancements

* Payment gateway integration (Stripe / Razorpay)
* Webhook-based subscription updates
* Admin analytics dashboard
* Rate limiting middleware
* Flutter / React frontend integration

---

## 👤 Author

**Aryan Singh**
Backend Developer | Django | REST APIs

---

⭐ If you found this project useful, give it a star!
