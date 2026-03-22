import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ZUHAKI_SECURE_2026')

# Cloudinary Setup (Pulled from Environment Variables)
cloudinary.config(
  cloud_name = os.environ.get('CLOUDINARY_NAME'),
  api_key = os.environ.get('CLOUDINARY_API_KEY'),
  api_secret = os.environ.get('CLOUDINARY_API_SECRET')
)

# Database Setup
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'zuhaki_realestate.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(50)) 
    title = db.Column(db.String(100))
    price = db.Column(db.Float)
    features = db.Column(db.Text)
    image_url = db.Column(db.String(500))

class Listing(db.Model): # For Plots & Short Stays
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    type = db.Column(db.String(50)) 
    price = db.Column(db.Float)
    image_url = db.Column(db.String(500))

class Inquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100))
    client_phone = db.Column(db.String(20))
    property_name = db.Column(db.String(100))
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(id): return User.query.get(int(id))

# Initialize Database and Default Admin
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password='Zuhaki_Admin_2026'))
        db.session.commit()

# --- PUBLIC ROUTES ---
@app.route('/')
def index():
    search = request.args.get('search')
    loc = request.args.get('location')
    
    prop_query = Property.query
    list_query = Listing.query

    if search:
        prop_query = prop_query.filter(Property.title.contains(search))
        list_query = list_query.filter(Listing.name.contains(search))
    if loc:
        prop_query = prop_query.filter_by(location=loc)

    locations = [l[0] for l in db.session.query(Property.location).distinct().all() if l[0]]
    
    return render_template('index.html', 
                           properties=prop_query.all(), 
                           listings=list_query.all(), 
                           locations=locations)

@app.route('/inquire/<item_type>/<int:id>', methods=['POST'])
def inquire(item_type, id):
    # Bug Fix: Properly identify which model to query based on item_type
    if item_type == 'prop':
        item = Property.query.get(id)
        name = item.title if item else "Unknown Property"
    else:
        item = Listing.query.get(id)
        name = item.name if item else "Unknown Listing"

    new_inquiry = Inquiry(
        client_name=request.form.get('name'),
        client_phone=request.form.get('phone'),
        property_name=name
    )
    db.session.add(new_inquiry)
    db.session.commit()
    flash('Inquiry submitted successfully! We will call you soon.')
    return redirect(url_for('index'))

# --- ADMIN ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.password == request.form.get('password'):
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    inquiries = Inquiry.query.order_by(Inquiry.date_created.desc()).all()
    return render_template('admin.html', inquiries=inquiries)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    upload_result = cloudinary.uploader.upload(file)
    img_url = upload_result['secure_url']
    
    mode = request.form.get('mode')
    if mode == 'property':
        item = Property(location=request.form.get('loc'), 
                        title=request.form.get('name'), 
                        price=float(request.form.get('price')), 
                        features=request.form.get('desc'), 
                        image_url=img_url)
    else:
        item = Listing(name=request.form.get('name'), 
                       type=request.form.get('type'), 
                       price=float(request.form.get('price')), 
                       image_url=img_url)
    
    db.session.add(item)
    db.session.commit()
    flash('Listing uploaded successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    new_pass = request.form.get('new_password')
    if new_pass:
        current_user.password = new_pass
        db.session.commit()
        flash('Admin password updated successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
