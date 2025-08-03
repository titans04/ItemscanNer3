from flask import Flask, request, render_template, redirect, flash, session, url_for, send_file
from models import db, Item as ItemModel, ItemStatus  # Import only the necessary models
#from app.models import db, Item 
import io
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors  
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.platypus import Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
from reportlab.lib.enums import TA_LEFT
from sqlalchemy import desc


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
    with app.app_context():  # Push the application context
            # Fetch recently added items, ordered by item_id in descending order and limited to 5
            recent_scans = Item.query.order_by(desc(Item.item_id)).limit(3).all()

    return render_template("home.html",recent_scans=recent_scans)  # Create a simple home.html



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
    return render_template('admin_dashboard.html')  # Updated to render index.html

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
                "not_working": 0,
                "not_setup": 0,
                "brands": set(),  # Track unique brands
                "colors": set(),  # Track unique colors
            }
        
        inventory_data[item.item_name]["total"] += 1
        
        # Track brands and colors if available
        if item.brand:
            inventory_data[item.item_name]["brands"].add(item.brand)
        if item.color:
            inventory_data[item.item_name]["colors"].add(item.color)
        
        # Count by status
        status_value = item.status.value.upper()
        if status_value in ["WORKING", "WORKING"]:  # Handle both cases for WORKING
            inventory_data[item.item_name]["working"] += 1
        elif status_value == "DAMAGED":
            inventory_data[item.item_name]["damaged"] += 1
        elif status_value == "NOT_WORKING":
            inventory_data[item.item_name]["not_working"] += 1
        elif status_value == "NOT_SETUP": 
            inventory_data[item.item_name]["not_setup"] += 1
    
    # Convert sets to sorted comma-separated strings for the template
    for item_name, data in inventory_data.items():
        data["brands"] = ", ".join(sorted(data["brands"])) if data["brands"] else "N/A"
        data["colors"] = ", ".join(sorted(data["colors"])) if data["colors"] else "N/A"
    
    # Get total counts by status for summary statistics
    total_items = len(items)
    total_working = sum(1 for item in items if item.status.value.upper() in ["WORKING", "WORKING"])
    total_damaged = sum(1 for item in items if item.status.value.upper() == "DAMAGED")
    total_not_working = sum(1 for item in items if item.status.value.upper() == "NOT_WORKING")
    total_not_setup = sum(1 for item in items if item.status.value.upper() == "NOT_SETUP") 
    
    # Get unique locations for the location filter
    locations = sorted(set(item.location for item in items)) 
    
    # Get unique brands for the brand filter
    brands = sorted(set(item.brand for item in items if item.brand))
    recently_added_items = Item.query.order_by(Item.item_id.desc()).limit(5).all()
    
    return render_template( 
        "admin_dashboard.html", 
        items=items,
        inventory_data=inventory_data,
        total_items=total_items,
        total_working=total_working,
        total_damaged=total_damaged,
        total_not_working=total_not_working,
        total_not_setup=total_not_setup,
        locations=locations,
        brands=brands,
        recently_added_items=recently_added_items
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
    """
    Route for adding a new item to the inventory.
    Handles both GET (display form) and POST (process form submission) requests.
    """
    if not session.get("admin"):
        flash("Please log in as admin to add an item.", "warning")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        item_id    = request.form["item_id"].strip()
        item_name  = request.form["item_name"].strip()
        location   = request.form["location"].strip()
        status_str = request.form["status"].strip()  # status as string from form
        brand      = request.form.get("brand", "").strip() or None
        color      = request.form.get("color", "").strip() or None

        # Check if item already exists
        if ItemModel.query.get(item_id):
            flash("Item already exists.", "danger")
            return redirect(url_for("add_item"))

        # Convert status string to Enum member
        try:
            item_status = ItemStatus(status_str)
        except ValueError:
            flash(
                "Invalid item status. Please select one of: "
                f"{', '.join([s.value for s in ItemStatus])}",
                "danger"
            )
            return redirect(url_for("add_item"))

        # Create and save new item
        new_item = ItemModel(
            item_id   = item_id,
            item_name = item_name,
            location  = location,
            status    = item_status,
            brand     = brand,
            color     = color,
        )
        db.session.add(new_item)
        db.session.commit()

        flash("Item added successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    # GET: build dropdown choices from the Python enum
    valid_statuses = [s.value for s in ItemStatus]
    return render_template("add_item.html", valid_statuses=valid_statuses)



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
        # Update basic item information
        item_to_edit.item_name = request.form["item_name"].strip()
        item_to_edit.location = request.form["location"].strip()
        
        # Update brand and color (handle empty strings as None)
        brand = request.form.get("brand", "").strip()
        color = request.form.get("color", "").strip()
        item_to_edit.brand = brand if brand else None
        item_to_edit.color = color if color else None
        
        # Get and validate new status
        new_status = request.form["status"].strip() 
        
        # Validate the status.  
        valid_statuses = [status.value for status in ItemStatus]
        if new_status not in valid_statuses:
            flash(f"Invalid item status. Please select one of: {', '.join(valid_statuses)}", "danger")
            return render_template("edit_item.html", item=item_to_edit, valid_statuses=valid_statuses)
        
        # Convert status string to enum and update
        item_to_edit.status = ItemStatus(new_status)  
        
        db.session.commit()   
        flash("Item updated successfully.", "success") 
        return redirect(url_for("admin_dashboard"))  
    
    # For GET requests, pass the valid statuses to the template
    valid_statuses = [status.value for status in ItemStatus] 
    return render_template("edit_item.html", item=item_to_edit, valid_statuses=valid_statuses)


#for exporting the pdf
@app.route("/admin/export-items-pdf")
def export_items_pdf():
    """
    Exports inventory overview table to a PDF file with professional black and white styling.
    """
    if not session.get("admin"):
        flash("Please log in as admin to export items.", "warning")
        return redirect(url_for("admin_login"))
    
    # Fetch all items from the database
    items = Item.query.all()   
    
    # Prepare inventory data similar to admin_dashboard
    inventory_data = {} 
    for item in items:
        if item.item_name not in inventory_data:
            inventory_data[item.item_name] = {
                "total": 0,
                "working": 0,
                "damaged": 0,
                "not_working": 0,
                "not_setup": 0,
                "brands": set(),  # Track unique brands
                "colors": set(),  # Track unique colors
            }
            
        inventory_data[item.item_name]["total"] += 1
            
        # Track brands and colors if available
        if item.brand:
            inventory_data[item.item_name]["brands"].add(item.brand)
        if item.color:
            inventory_data[item.item_name]["colors"].add(item.color)
            
        # Count by status
        status_value = item.status.value.upper()
        if status_value in ["WORKING", "WORKING"]:  # Handle both cases for WORKING
            inventory_data[item.item_name]["working"] += 1
        elif status_value == "DAMAGED":
            inventory_data[item.item_name]["damaged"] += 1
        elif status_value == "NOT_WORKING":
            inventory_data[item.item_name]["not_working"] += 1
        elif status_value == "NOT_SETUP":
            inventory_data[item.item_name]["not_setup"] += 1
    
    # Convert sets to sorted comma-separated strings for the PDF
    for item_name, data in inventory_data.items():
        data["brands"] = ", ".join(sorted(data["brands"])) if data["brands"] else "N/A"
        data["colors"] = ", ".join(sorted(data["colors"])) if data["colors"] else "N/A"
    
    # Calculate totals for summary
    total_items = len(items)
    total_working = sum(1 for item in items if item.status.value.upper() in ["WORKING", "WORKING"])
    total_damaged = sum(1 for item in items if item.status.value.upper() == "DAMAGED")
    total_not_working = sum(1 for item in items if item.status.value.upper() == "NOT_WORKING")
    total_not_setup = sum(1 for item in items if item.status.value.upper() == "NOT_SETUP")
    
    # Create a buffer to hold the PDF data
    buffer = io.BytesIO()
    
    # Set up the document with proper margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),  # Use landscape for wider table
        rightMargin=36,
        leftMargin=36,
        topMargin=72,
        bottomMargin=36
    )
    
    # Get available width for the table
    available_width = doc.width
    
    # Define column widths - proportional to make it fill the page width
    col_widths = [
        available_width * 0.20,  # Item Name - 20%
        available_width * 0.10,  # Total Items - 10%
        available_width * 0.10,  # Working Items - 10%
        available_width * 0.10,  # Damaged Items - 10%
        available_width * 0.10,  # Not Working - 10%
        available_width * 0.10,  # Not Setup - 10%
        available_width * 0.15,  # Brands - 15%
        available_width * 0.15   # Colors - 15%
    ]
    
    # Prepare data for the PDF table
    data = [["Item Name", "Total Items", "Working Items", "Damaged Items", "Not Working", "Not Setup", "Brands", "Colors"]]  # Table header
    
    # Add inventory data
    for item_name, item_data in inventory_data.items():
        data.append([
            item_name,
            item_data["total"],
            item_data["working"],
            item_data["damaged"],
            item_data["not_working"],
            item_data["not_setup"],
            item_data["brands"],
            item_data["colors"]  
        ])
    
    # Get styles and create custom styles
    styles = getSampleStyleSheet()
    
    # Create custom title style
    title_style = ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        spaceAfter=12,
        fontSize=18,
        leading=22,
        textColor=colors.black
    )
    
    # Create custom date style
    date_style = ParagraphStyle(
        name='DateStyle',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.black
    )
    
    # Create custom stat style for item counts
    stat_style = ParagraphStyle(
        name='StatStyle',
        parent=styles['Normal'],
        alignment=TA_LEFT,
        fontSize=10,
        spaceBefore=2,
        spaceAfter=2
    )
    
    # Create a title for the document
    title = Paragraph("Lab Equipment Inventory Overview", title_style)
    date_text = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", date_style)
    
    # Create the table with specified column widths
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    # Apply professional black and white styling 
    table.setStyle(TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), 
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        
        # Data rows styling
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (1, 1), (5, -1), 'CENTER'),  # Center numeric columns
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        
        # Table grid
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),  # Line below header
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),    # Grid for all cells
        
        # Alternating row colors for better readability
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.white])
    ]))
     
    # Add a footer with page numbers
    def add_page_number(canvas, doc):   
        canvas.saveState() 
        canvas.setFont('Helvetica', 9) 
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.drawRightString(landscape(letter)[0] - 36, 30, text)
        canvas.drawString(36, 30, "Lab Equipment Inventory Overview")
        canvas.restoreState()
    
    # Create summary statistics paragraphs
    total_items_text = Paragraph(f"Total Items: {total_items}", stat_style)
    working_items_text = Paragraph(f"Working Items: {total_working}", stat_style)
    damaged_items_text = Paragraph(f"Damaged Items: {total_damaged}", stat_style)
    not_working_text = Paragraph(f"Not Working Items: {total_not_working}", stat_style)
    not_setup_text = Paragraph(f"Not Setup Items: {total_not_setup}", stat_style)
    
    # Create content for the document
    content = [
        title,
        Spacer(1, 12),
        date_text,
        Spacer(1, 24),
        table,
        Spacer(1, 24),
        total_items_text,
        working_items_text,
        damaged_items_text,
        not_working_text,
        not_setup_text
    ]
    
    # Build the PDF document with page numbers
    doc.build(content, onFirstPage=add_page_number, onLaterPages=add_page_number)
    
    # Seek to the beginning of the buffer
    buffer.seek(0)
    
    # Return the buffer as a file attachment
    return send_file(
        buffer,
        mimetype='application/pdf',
        download_name='lab_inventory_overview.pdf',
        as_attachment=True
    )

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
