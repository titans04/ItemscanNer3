from flask import Flask, request, render_template, redirect, flash, session, url_for, send_file
from models import db, Item  # Import only the necessary models
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors  
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.platypus import Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from datetime import datetime


app = Flask(__name__) 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
db.init_app(app)  

app.secret_key = "your-secret-key"  # Needed for flash messages


# Removed the / route and borrow_or_return function
@app.route("/", methods=["GET"]) 
def home():
    """
    This route now simply displays a message.  It could be expanded
    to show a welcome page or instructions for the admin.
    """
    return render_template("home.html")  # Create a simple home.html



ADMIN_USERNAME = 'bandile'
ADMIN_PASSWORD = 'bandile123'

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('admin_login.html')

# the admin dashboard
@app.route("/admin_dashboard")
def admin_dashboard():
    # Ensure only logged-in admin can access
    if not session.get("admin"):
        flash("Please log in as admin to access the dashboard.", "warning")
        return redirect(url_for("admin_login"))

    # Fetch all items
    items = Item.query.all() 

    # Prepare data for the inventory overview table
    inventory_data = {}
    for item in items:
        if item.item_name not in inventory_data:
            inventory_data[item.item_name] = {
                "total": 0,
                "working": 0,
                "damaged": 0,
            }
        inventory_data[item.item_name]["total"] += 1
        if item.status.value.upper() == "WORKING":  # Access Enum value
            inventory_data[item.item_name]["working"] += 1
        else:
            inventory_data[item.item_name]["damaged"] += 1

    return render_template( 
        "admin_dashboard.html", items=items,  inventory_data=inventory_data
    )

# the logout for the button
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home')) # Redirect to the home page


# the admin to add the item
@app.route("/admin/add-item", methods=["GET", "POST"])
def add_item():
    if not session.get("admin"):
        flash("Please log in as admin to add an item.", "warning")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        item_id = request.form["item_id"].strip()
        item_name = request.form["item_name"].strip() 
        location = request.form["location"].strip()
        status = request.form["status"].strip() # Get status from form
 
        # Check if item already exists 
        if Item.query.get(item_id):
            flash("Item already exists.")
            return redirect("/admin/add-item")
        
        # Validate the status.
        if status not in ['WORKING', 'DAMAGED']:
            flash("Invalid item status.  Please select 'Working' or 'Damaged'.")
            return redirect("/admin/add-item")

        # Add the item
        new_item = Item(
            item_id=item_id,
            item_name=item_name,
            location=location,
            status=status  # Use the status from the form
        )
        db.session.add(new_item)
        db.session.commit()

        flash("Item added successfully.")
        return redirect("/admin_dashboard")

    return render_template("add_item.html")



@app.route("/admin/delete-item/<string:item_id>")
def delete_item(item_id):
    # Ensure only logged-in admin can access
    if not session.get("admin"):
        flash("Please log in as admin.", "warning")
        return redirect(url_for("admin_login"))

    item_to_delete = Item.query.get_or_404(item_id)
    db.session.delete(item_to_delete)
    db.session.commit()
    flash(f"Item '{item_to_delete.item_name}' deleted successfully.", "success")
    return redirect(url_for("admin_dashboard"))



@app.route("/admin/edit-item/<string:item_id>", methods=["GET", "POST"])
def edit_item(item_id):
    """
    Allows the admin to edit an existing item's details.
    """
    if not session.get("admin"):
        flash("Please log in as admin to edit items.", "warning")
        return redirect(url_for("admin_login"))

    item_to_edit = Item.query.get_or_404(item_id) 

    if request.method == "POST": 
        item_to_edit.item_name = request.form["item_name"].strip()
        item_to_edit.location = request.form["location"].strip() 
        new_status = request.form["status"].strip() 

         # Validate the status.
        if new_status not in ['WORKING', 'DAMAGED']:
            flash("Invalid item status.  Please select 'Working' or 'Damaged'.")
            return render_template("edit_item.html", item=item_to_edit)

        item_to_edit.status = new_status 
        db.session.commit()
        flash("Item updated successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("edit_item.html", item=item_to_edit) #show the current data

@app.route("/admin/export-items-pdf")
def export_items_pdf():
    """
    Exports all items from the database to a PDF file with professional styling.
    """
    if not session.get("admin"):
        flash("Please log in as admin to export items.", "warning")
        return redirect(url_for("admin_login"))
    
    # Fetch all items from the database
    items = Item.query.all()
    
    # Create a buffer to hold the PDF data
    buffer = io.BytesIO()
    
    # Set up the document with proper margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=72,
        bottomMargin=36
    )
    
    # Get available width for the table
    available_width = doc.width
    
    # Define column widths - proportional to make it fill the page width
    col_widths = [
        available_width * 0.15,  # Item ID - 15%
        available_width * 0.35,  # Item Name - 35%
        available_width * 0.3,   # Location - 30%
        available_width * 0.2    # Status - 20%
    ]
    
    # Prepare data for the PDF table
    data = [["Item ID", "Item Name", "Location", "Status"]]  # Table header
    
    # Add item data with status formatting
    for item in items:
        status = item.status.value
        data.append([
            item.item_id, 
            item.item_name, 
            item.location, 
            status
        ])
    
    # Get styles and create custom styles
    styles = getSampleStyleSheet()
    
    # Create custom title style with underline
    title_style = ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        spaceAfter=12,
        fontSize=18,
        leading=22,
        textColor=colors.darkblue,
        underlineWidth=1,
        underlineColor=colors.darkblue,
        underlineOffset=-2
    )
    
    # Create custom date style
    date_style = ParagraphStyle(
        name='DateStyle',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.grey
    )
    
    normal_style = styles['Normal']
    
    # Create a title for the document
    title = Paragraph("Lab Equipment Inventory", title_style)
    date_text = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", date_style)
    
    # Create the table with specified column widths
    table = Table(data, colWidths=col_widths)
    
    # Apply professional styling
    table.setStyle(TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows styling
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Center ID column
        ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Center Status column
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        
        # Table grid
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),  # Thicker line below header
        ('GRID', (0, 1), (-1, -1), 0.5, colors.grey),     # Lighter grid for data rows
        
        # Alternating row colors for better readability
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    # Add conditional formatting for status column
    for i in range(1, len(data)):
        status = data[i][3]
        if status == "WORKING":
            table.setStyle(TableStyle([
                ('TEXTCOLOR', (3, i), (3, i), colors.darkgreen),
                ('FONTNAME', (3, i), (3, i), 'Helvetica-Bold')
            ]))
        elif status == "DAMAGED":
            table.setStyle(TableStyle([
                ('TEXTCOLOR', (3, i), (3, i), colors.red),
                ('FONTNAME', (3, i), (3, i), 'Helvetica-Bold')
            ]))
    
    # Add a footer with page numbers
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.drawRightString(letter[0] - 36, 30, text)
        canvas.drawString(36, 30, "Lab Equipment Inventory")
        canvas.restoreState()
    
    # Create content for the document
    content = [
        title,
        Spacer(1, 12),
        date_text,
        Spacer(1, 24),
        table,
        Spacer(1, 12),
        Paragraph(f"Total Items: {len(items)}", normal_style)
    ]
    
    # Build the PDF document with page numbers
    doc.build(content, onFirstPage=add_page_number, onLaterPages=add_page_number)
    
    # Seek to the beginning of the buffer
    buffer.seek(0)
    
    # Return the buffer as a file attachment
    return send_file(
        buffer,
        mimetype='application/pdf',
        download_name='lab_inventory.pdf',
        as_attachment=True
    )

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Create tables if they do not exist
    app.run(debug=True)
