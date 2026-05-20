# ALAIA — Project Overview & Hosting Journey

---

## 🖤 What is ALAIA?

**ALAIA** is a fully functional, production-grade **premium footwear e-commerce platform** — built from scratch using Python and Django.

Think of it like a high-end online shoe store — similar to how Myntra or Nykaa Fashion works, but crafted entirely by hand with a focus on **architectural minimalism, luxury design, and a seamless shopping experience**.

### What makes it special?

| Feature | What it does |
|---|---|
| 🛍️ **Product Catalog** | Browse shoes by brand, category, color, size, occasion, and price range |
| 🛒 **Smart Cart** | Add items, update quantity, get real-time stock warnings |
| ❤️ **Wishlist** | Save favorites — count updates instantly in the navbar |
| 💳 **Multiple Payments** | Pay via Cash on Delivery, Razorpay (UPI/Cards/NetBanking), or Wallet |
| 👜 **Wallet System** | Earn wallet credits via referrals and order refunds |
| 🎟️ **Coupon Engine** | Apply discount codes with per-user and global usage limits |
| 📦 **Order Management** | Full order lifecycle — place, track, cancel, return |
| 🧾 **Invoice Download** | PDF invoice for every order |
| 🔐 **OTP Authentication** | Email OTP for signup, login, and email changes |
| 🔗 **Referral System** | Share a code, earn wallet credit when friends sign up |
| 🌐 **Google OAuth** | Sign in with Google using Django Allauth |
| 👨‍💼 **Admin Panel** | Custom admin dashboard to manage products, orders, users, coupons |
| 📱 **Fully Responsive** | Works beautifully on mobile, tablet, and desktop |
| 🎨 **Premium UI** | Dark luxury theme, micro-animations, branded email templates |

---

## 🚀 The Hosting Journey — Step by Step

### Step 1 — Build the Project Locally

The entire project was built on a **Windows laptop** using:
- **Python + Django** → the backend framework (handles logic, database, routing)
- **PostgreSQL** → the database (stores all users, products, orders)
- **HTML + CSS + JavaScript** → the frontend (what users see)
- **Razorpay SDK** → payment gateway integration
- **Git + GitHub** → version control (like a save history for code)

> 💡 Think of Django as the engine of the car. HTML/CSS is the body and paint. PostgreSQL is the storage boot.

---

### Step 2 — Push Code to GitHub

Once the project was working locally, all the code was pushed to a **private GitHub repository**.

```
git init
git add .
git commit -m "Initial commit"
git push origin main
```

> 💡 GitHub is like Google Drive for code — it stores your project online so you can access it from anywhere.

---

### Step 3 — Create an AWS EC2 Instance (Virtual Server)

Went to **Amazon Web Services (AWS)** → **EC2 (Elastic Compute Cloud)** and launched a virtual server in the cloud.

**Choices made:**
- **OS:** Ubuntu 22.04 LTS (a popular Linux operating system)
- **Instance type:** `t2.micro` (free tier eligible — enough for a project demo)
- **Region:** Asia Pacific (Mumbai) — closest to India for low latency
- **Key pair:** Downloaded a `.pem` file — acts like a password to SSH into the server

> 💡 Think of EC2 as renting a computer in Amazon's data center. Instead of buying a server, you pay by the hour.

---

### Step 4 — Connect to the Server via SSH

Using the downloaded `.pem` key, connected to the server from the terminal:

```bash
ssh -i "key.pem" ubuntu@<EC2-public-IP>
```

> 💡 SSH (Secure Shell) is like a remote control — it lets you type commands on your server from your own laptop.

---

### Step 5 — Set Up the Server Environment

Once inside the server, installed all required software:

```bash
# Update the server
sudo apt update && sudo apt upgrade -y

# Install Python, pip, and PostgreSQL
sudo apt install python3-pip python3-venv postgresql nginx -y

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install all project dependencies
pip install -r requirements.txt
```

> 💡 A virtual environment is like a clean, isolated workspace — so your project's libraries don't conflict with the server's system libraries.

---

### Step 6 — Set Up PostgreSQL Database

Created a database and a user for the project:

```bash
sudo -u postgres psql

CREATE DATABASE alaia_db;
CREATE USER alaia_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE alaia_db TO alaia_user;
```

Then updated the Django `settings.py` to point to this database using environment variables stored in a `.env` file (for security — no passwords in code).

---

### Step 7 — Pull the Code from GitHub

```bash
cd /var/www/html/
git clone https://github.com/your-username/alaia-footwear.git
cd alaia-footwear
```

Then ran Django setup commands:

```bash
python manage.py migrate          # Creates all database tables
python manage.py collectstatic    # Gathers all CSS/JS/images into one folder
python manage.py createsuperuser  # Creates admin login
```

---

### Step 8 — Configure Gunicorn (Application Server)

Django's built-in server is for development only. For production, used **Gunicorn** — a production-grade WSGI server.

Created a systemd service so Gunicorn starts automatically:

```
# /etc/systemd/system/gunicorn.service
[Service]
ExecStart=/path/to/venv/bin/gunicorn alaia.wsgi:application
```

```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn   # Auto-start on server reboot
```

> 💡 Gunicorn is the "waiter" between the internet and your Django app. It handles multiple requests at the same time.

---

### Step 9 — Configure Nginx (Web Server / Reverse Proxy)

**Nginx** sits in front of Gunicorn and handles:
- Routing HTTP requests to Gunicorn
- Serving static files (CSS, JS, images) directly — much faster
- Handling HTTPS (SSL)

Created an Nginx config file:

```nginx
server {
    server_name alaiaa.shop www.alaiaa.shop;

    location /static/ {
        root /var/www/html/alaia-footwear;
    }

    location /media/ {
        root /var/www/html/alaia-footwear;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

> 💡 Nginx is the "receptionist" — it greets every visitor, handles simple requests itself, and forwards complex ones to Gunicorn (the waiter).

---

### Step 10 — Register a Domain Name

Bought the domain **`alaiaa.shop`** from a domain registrar.

Then in the domain's **DNS settings**, pointed it to the EC2 server's public IP:

```
A record:  alaiaa.shop      → <EC2 Public IP>
A record:  www.alaiaa.shop  → <EC2 Public IP>
```

> 💡 DNS (Domain Name System) is like a phone book — it converts `alaiaa.shop` into the actual IP address `43.204.25.155`.

---

### Step 11 — Enable HTTPS with SSL Certificate

Used **Let's Encrypt** (free SSL certificate provider) with the `certbot` tool:

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d alaiaa.shop -d www.alaiaa.shop
```

Certbot automatically:
- Generated a free SSL certificate
- Updated the Nginx config to redirect HTTP → HTTPS
- Set up auto-renewal every 90 days

> 💡 SSL (the padlock 🔒 in your browser) encrypts all data between the user and your server. Without it, passwords would be sent in plain text.

---

### Step 12 — Set Environment Variables Securely

Sensitive values (database password, secret key, email password, Razorpay keys) were stored in a `.env` file on the server — **never committed to GitHub**.

```env
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://alaia_user:password@localhost/alaia_db
RAZORPAY_KEY_ID=rzp_live_xxx
EMAIL_HOST_USER=your@email.com
DEBUG=False
```

> 💡 Never put passwords in your code. A `.env` file keeps them safe on the server only.

---

### Step 13 — Go Live! ✅

The site is now live at **[https://alaiaa.shop](https://alaiaa.shop)**

**The full stack in production:**

```
User's Browser
      ↓  HTTPS
    Nginx  (web server — handles SSL, static files)
      ↓
  Gunicorn  (app server — runs Django)
      ↓
   Django  (framework — business logic, templates)
      ↓
 PostgreSQL  (database — stores all data)
```

---

## 🔄 Deployment Workflow (After Every Code Change)

```bash
# 1. Push changes from laptop
git push origin main

# 2. SSH into server
ssh -i key.pem ubuntu@<IP>

# 3. Pull latest code
cd /var/www/html/alaia-footwear
git pull origin main

# 4. Apply any database changes
python manage.py migrate

# 5. Collect static files
python manage.py collectstatic --noinput

# 6. Restart the app server
sudo systemctl restart gunicorn
```

---

## 🧰 Full Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Language** | Python 3.13 | Core programming language |
| **Framework** | Django 5.x | Web framework — routing, ORM, templates |
| **Database** | PostgreSQL | Relational database |
| **Frontend** | HTML5, CSS3, Vanilla JS | UI and interactivity |
| **Payment** | Razorpay | UPI, cards, net banking |
| **Auth** | Django Allauth | Google OAuth + email OTP |
| **App Server** | Gunicorn | Serves Django in production |
| **Web Server** | Nginx | Reverse proxy + static files |
| **SSL** | Let's Encrypt / Certbot | Free HTTPS certificate |
| **Cloud** | AWS EC2 (Mumbai) | Virtual server |
| **Domain** | alaiaa.shop | Custom domain |
| **Version Control** | Git + GitHub | Source code management |
| **Email** | Gmail SMTP | OTP and transactional emails |
| **Environment** | python-environ | Secure secrets management |
