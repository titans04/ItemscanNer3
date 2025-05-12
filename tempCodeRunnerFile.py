from flask import Flask
from flask import request, render_template, redirect, flash
from datetime import datetime, timedelta
from app.models import db, User, Item, BorrowLog

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

app.secret_key = "your-secret-key"  # Needed for flash messages


@app.route("/")
def home():
    return "<h1>Welcome to the Home Page!</h1>"


@app.route("/borrow", methods=["GET", "POST"])
def borrow():
    if request.method == "POST":
        user_id = request.form["user_id"].strip()
        item_id = request.form["item_id"].strip()

        user = User.query.get(user_id)
        item = Item.query.get(item_id)

        # Check if user exists
        if not user:
            flash("User not found.")
            return redirect("/register_user")

        # Check if item exists
        if not item:
            flash("Item not found.")
            return redirect("/borrow")

        # Check if item is available
        if item.status != "Available":
            flash("Item is not available.")
            return redirect("/borrow")

        # Perform borrow
        item.status = "Borrowed"
        borrow_log = BorrowLog(
            user_id=user_id,
            item_id=item_id,
            borrowed_at=datetime.now(),
            due_at=datetime.now() + timedelta(days=3)
        )

        db.session.add(borrow_log)
        db.session.commit()

        flash("Item borrowed successfully.")
        return redirect("/borrow")

    # If GET request, render the scan form
    return render_template("scan.html")

#returning the item
@app.route("/return", methods=["GET", "POST"])
def return_item():
    if request.method == "POST":
        item_id = request.form["item_id"].strip()
        user_id = request.form["user_id"].strip()  # Get user ID from the form

        item = Item.query.get(item_id)

        if not item:  
            flash("Item not found.")
            return redirect("/return")

        if item.status != "Borrowed": 
            flash("Item is not currently borrowed.")
            return redirect("/return")

        # Find the most recent borrow log for this item and user that has not been returned
        borrow_log = BorrowLog.query.filter_by(
            item_id=item_id, user_id=user_id, returned_at=None
        ).order_by(BorrowLog.borrowed_at.desc()).first()

        if borrow_log:
            # Update item status
            item.status = "Available"
            borrow_log.returned_at = datetime.now()
            db.session.commit()
            flash("Item returned successfully.")
        else:
            flash("Item was not borrowed by this user, or borrow log not found.")
        return redirect("/return")

    return render_template("scan.html")

#For the member to register
@app.route("/register_user", methods=["GET", "POST"])
def register_user():
    if request.method == "POST":
        user_id = request.form["user_id"].strip()
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip()
        role = request.form["role"].strip()

        if User.query.get(user_id):
            flash("User already exists.")
            return redirect("/borrow")

        new_user = User(
            user_id=user_id,
            full_name=full_name,
            email=email,
            role=role
        )

        db.session.add(new_user)
        db.session.commit()

        flash("User registered successfully. You can now borrow an item.")
        return redirect("/borrow")

    # GET request
    user_id = request.args.get("user_id", "")
    return render_template("register_user.html", user_id=user_id)


#the admin dashbaord 
@app.route("/admin_dashboard") 
def admin_dashboard(): 
    items = Item.query.all()
    borrow_logs = {log.item_id: log for log in BorrowLog.query.filter_by(returned_at=None).all()}
    return render_template("admin_dashboard.html", items=items, borrow_logs=borrow_logs)

#the admin to add the item
@app.route("/admin/add-item", methods=["GET", "POST"])
def add_item():
    if request.method == "POST":
        item_id = request.form["item_id"].strip()
        item_name = request.form["item_name"].strip()
        location = request.form["location"].strip()

        # Check if item already exists
        if Item.query.get(item_id):
            flash("Item already exists.")
            return redirect("/admin/add-item")

        # Add the item
        new_item = Item( 
            item_id=item_id,
            item_name=item_name,
            location=location,
            status="Available"
        )
        db.session.add(new_item)
        db.session.commit()

        flash("Item added successfully.")
        return redirect("/admin_dashboard")

    return render_template("add_item.html")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Create tables if they do not exist
    app.run(debug=True)