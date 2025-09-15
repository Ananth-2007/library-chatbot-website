from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for, session, flash
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

# Secret key for session management (needed for admin login)
app.secret_key = os.urandom(24)
ADMIN_PASSWORD = "admin"

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
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


# 3. Simple NLP: Intent and Entity Recognition
def parse_user_query(query):
    query = query.lower().strip()
    match = re.search(r"book\s+'(.*?)'", query)
    if match:
        book_title = match.group(1)
        return {"intent": "start_booking", "entity": book_title}
    if "list" in query and "available" in query:
        return {"intent": "list_available_books", "entity": None}
    if "confirm" in query:
        return {"intent": "confirm_booking", "entity": None}
    return {"intent": "unknown", "entity": None}


# --- NEW: HOMEPAGE ROUTE ---
@app.route('/')
def home():
    return render_template('index.html')


# 4. Create the API Endpoint for the Chatbot
@app.route('/ask', methods=['POST'])
def ask_chatbot():
    data = request.json
    user_message = data['message']
    conversation_state = data.get('state', {})
    response_data = {"type": "text", "content": "I'm sorry, I don't understand."}
    
    if conversation_state.get('step') == 'awaiting_name':
        member_name = user_message
        response_data = {"type": "prompt_phone", "content": f"Got it. What is the phone number for {member_name}?", "state": {"step": "awaiting_phone", "book_title": conversation_state['book_title'], "member_name": member_name}}
    
    elif conversation_state.get('step') == 'awaiting_phone':
        member_phone = user_message
        response_data = {"type": "prompt_due_date", "content": "Okay. What is the due date for returning the book? (Please use YYYY-MM-DD format)", "state": {"step": "awaiting_due_date", "book_title": conversation_state['book_title'], "member_name": conversation_state['member_name'], "member_phone": member_phone}}
    
    elif conversation_state.get('step') == 'awaiting_due_date':
        due_date_str = user_message
        try:
            issue_date = date.today()
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            if due_date <= issue_date:
                raise ValueError("Due date must be in the future.")
            days = (due_date - issue_date).days
            book_title = conversation_state['book_title']
            book = Book.query.filter(Book.title.ilike(f"%{book_title}%")).first()
            total_amount = days * book.daily_rate
            confirmation_message = (f"Booking Details:\n- Days: {days}\n- Rate: ₹{book.daily_rate:.2f}/day\n- Total Amount: ₹{total_amount:.2f}\n\nPlease confirm to proceed.")
            response_data = {"type": "prompt_confirmation", "content": confirmation_message, "state": {**conversation_state, "step": "awaiting_confirmation", "issue_date": issue_date.isoformat(), "due_date": due_date.isoformat(), "total_amount": total_amount}}
        except ValueError as e:
            response_data = {"type": "error_date_format", "content": str(e) or "Incorrect date format. Please use YYYY-MM-DD and a future date.", "state": conversation_state}
    
    elif conversation_state.get('step') == 'awaiting_confirmation':
        if "confirm" in user_message.lower() or "yes" in user_message.lower():
            state = conversation_state
            book = Book.query.filter(Book.title.ilike(f"%{state['book_title']}%")).first()
            member = Member.query.filter_by(name=state['member_name']).first()
            if not member:
                member = Member(name=state['member_name'], phone_no=state['member_phone'])
                db.session.add(member)
                db.session.commit()
            new_transaction = Transaction(book_id=book.id, member_id=member.id, issue_date=date.fromisoformat(state['issue_date']), due_date=date.fromisoformat(state['due_date']), total_amount=state['total_amount'])
            book.is_available = False
            db.session.add(new_transaction)
            db.session.commit()
            response_data = {"type": "booking_success", "content": {"message": f"Success! '{book.title}' has been booked.", "transaction_id": new_transaction.id}, "state": {"step": "done"}}
        else:
            response_data = {"type": "text", "content": "Booking cancelled.", "state": {"step": "done"}}
    else:
        parsed_query = parse_user_query(user_message)
        intent = parsed_query['intent']
        entity = parsed_query['entity']
        if intent == "start_booking":
            book = Book.query.filter(Book.title.ilike(f"%{entity}%")).first()
            if not book:
                response_data["content"] = f"Sorry, I couldn't find the book '{entity}'."
            elif not book.is_available:
                response_data["content"] = f"Sorry, the book '{book.title}' is currently checked out."
            else:
                response_data = {"type": "prompt_name", "content": f"Great! I can book '{book.title}'. What is the customer's full name?", "state": {"step": "awaiting_name", "book_title": book.title}}
        elif intent == "list_available_books":
            available_books = Book.query.filter_by(is_available=True).all()
            if available_books:
                response_data["type"] = "books_list"
                response_data["content"] = [{"title": b.title, "author": b.author, "image_url": b.image_url} for b in available_books]
            else:
                response_data["content"] = "Sorry, there are no books available at the moment."

    return jsonify({"response": response_data})


# 5. Endpoint to Generate and Download PDF
@app.route('/download_receipt/<int:transaction_id>')
def download_receipt(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.image('logo.png', x=10, y=8, w=30)
    except FileNotFoundError:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(40, 10, 'Library Logo')
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Library Booking Receipt", ln=True, align='C')
    pdf.ln(20)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 8, txt=f"Transaction ID: {transaction.id}", ln=True)
    pdf.cell(200, 8, txt=f"Member Name: {transaction.member.name}", ln=True)
    pdf.cell(200, 8, txt=f"Member Phone: {transaction.member.phone_no}", ln=True)
    pdf.cell(200, 8, txt=f"Book Title: {transaction.book.title}", ln=True)
    pdf.cell(200, 8, txt=f"Issue Date: {transaction.issue_date.strftime('%d-%m-%Y')}", ln=True)
    pdf.cell(200, 8, txt=f"Due Date: {transaction.due_date.strftime('%d-%m-%Y')}", ln=True)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 8, txt=f"Total Amount: Rs. {transaction.total_amount:.2f}", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, txt="Thank you for using our library!", ln=True, align='C')
    pdf_output = pdf.output(dest='S')
    return send_file(io.BytesIO(pdf_output), as_attachment=True, download_name=f'receipt_{transaction.id}.pdf', mimetype='application/pdf')


# (Admin routes remain the same, but are not included in this snippet for brevity)
# --- ADMIN ROUTES ---
@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    else:
        all_books = Book.query.all()
        return render_template('admin_dashboard.html', books=all_books)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Wrong password!')
            return redirect(url_for('admin_login'))
    return render_template('admin_login.html')

@app.route('/admin/add_book', methods=['POST'])
def add_book():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    
    new_book = Book(
        title=request.form['title'],
        author=request.form['author'],
        image_url=request.form['image_url'],
        daily_rate=float(request.form['daily_rate']),
        is_available=True
    )
    db.session.add(new_book)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_book/<int:book_id>')
def delete_book(book_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
        
    book_to_delete = Book.query.get_or_404(book_id)
    db.session.delete(book_to_delete)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


# 6. Function to Create and Populate the Database
def setup_database(app):
    with app.app_context():
        db.create_all() 

# Main entry point
if __name__ == '__main__':
    setup_database(app)
    app.run(debug=True)