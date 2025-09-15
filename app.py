from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import re
from fpdf import FPDF
from datetime import date, timedelta, datetime
import io
import os

# 1. Initialize the App and Database
app = Flask(__name__)
CORS(app)

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 2. Define the Database Models (Tables)
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    image_url = db.Column(db.String(255), nullable=True)
    daily_rate = db.Column(db.Float, default=10.0)

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    phone_no = db.Column(db.String(20), nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Float, default=0.0)
    book = db.relationship('Book', backref=db.backref('transactions', lazy=True))
    member = db.relationship('Member', backref=db.backref('transactions', lazy=True))


# 3. Command to initialize and reset the database for Render
@app.cli.command("reset-db")
def reset_db_command():
    """Destroys and recreates the database with fresh data."""
    db.drop_all()
    db.create_all()
    
    books_to_add = [
        {'title': 'The Hobbit', 'author': 'J.R.R. Tolkien', 'is_available': True, 'image_url': 'https://picsum.photos/id/11/100/150', 'daily_rate': 10.00},
        {'title': '1984', 'author': 'George Orwell', 'is_available': True, 'image_url': 'https://picsum.photos/id/13/100/150', 'daily_rate': 7.50},
        {'title': 'To Kill a Mockingbird', 'author': 'Harper Lee', 'is_available': True, 'image_url': 'https://picsum.photos/id/20/100/150', 'daily_rate': 8.00},
        {'title': 'Pride and Prejudice', 'author': 'Jane Austen', 'is_available': True, 'image_url': 'https://picsum.photos/id/22/100/150', 'daily_rate': 5.00},
        {'title': 'The Great Gatsby', 'author': 'F. Scott Fitzgerald', 'is_available': False, 'image_url': 'https://picsum.photos/id/21/100/150', 'daily_rate': 9.00},
        {'title': 'The Catcher in the Rye', 'author': 'J.D. Salinger', 'is_available': True, 'image_url': 'https://picsum.photos/id/23/100/150', 'daily_rate': 7.00},
        {'title': 'Moby Dick', 'author': 'Herman Melville', 'is_available': False, 'image_url': 'https://picsum.photos/id/24/100/150', 'daily_rate': 10.00},
        {'title': 'The Lord of the Rings', 'author': 'J.R.R. Tolkien', 'is_available': True, 'image_url': 'https://picsum.photos/id/25/100/150', 'daily_rate': 15.00},
        {'title': 'Harry Potter and the Sorcerer\'s Stone', 'author': 'J.K. Rowling', 'is_available': True, 'image_url': 'https://picsum.photos/id/26/100/150', 'daily_rate': 10.00},
        {'title': 'Fahrenheit 451', 'author': 'Ray Bradbury', 'is_available': False, 'image_url': 'https://picsum.photos/id/27/100/150', 'daily_rate': 8.50},
        {'title': 'Brave New World', 'author': 'Aldous Huxley', 'is_available': True, 'image_url': 'https://picsum.photos/id/28/100/150', 'daily_rate': 9.50},
        {'title': 'The Diary of a Young Girl', 'author': 'Anne Frank', 'is_available': True, 'image_url': 'https://picsum.photos/id/29/100/150', 'daily_rate': 6.00},
        {'title': 'The Alchemist', 'author': 'Paulo Coelho', 'is_available': False, 'image_url': 'https://picsum.photos/id/30/100/150', 'daily_rate': 11.00},
        {'title': 'Sapiens: A Brief History of Humankind', 'author': 'Yuval Noah Harari', 'is_available': True, 'image_url': 'https://picsum.photos/id/39/100/150', 'daily_rate': 15.00},
        {'title': 'Atomic Habits', 'author': 'James Clear', 'is_available': False, 'image_url': 'https://picsum.photos/id/40/100/150', 'daily_rate': 12.00}
    ]
    for book_data in books_to_add:
        db.session.add(Book(**book_data))
    
    m1 = Member(name="John Doe", phone_no="555-1234")
    m2 = Member(name="Jane Smith", phone_no="555-5678")
    db.session.add_all([m1, m2])
    db.session.commit()
    print("Database has been reset and seeded with 15 books.")


# --- WEBSITE ROUTES ---
# (The rest of the code remains the same)
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/ask', methods=['POST'])
def ask_chatbot():
    # ... (chatbot logic)
    pass

@app.route('/download_receipt/<int:transaction_id>')
def download_receipt(transaction_id):
    # ... (pdf logic)
    pass

if __name__ == '__main__':
    app.run(debug=True)