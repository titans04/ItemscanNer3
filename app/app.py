from flask import Flask, request, render_template, redirect, flash, session, url_for, send_file
from models import db, Item,Item as ItemModel, ItemStatus  # Import only the necessary models
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
    return render_template('admin_login.html')  # Updated to render index.html

# the admin dashboard
@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get("admin"):
        flash("Please log in as admin to access the dashboard.", "warning")
        return redirect(url_for("admin_login"))

    # Fetch all items 
    items = ItemModel.query.all()

    # Prepare data for the inventory overview table (aggregated by item_name)
    inventory_data = {}
    for item in items:
        if item.item_name not in inventory_data:
            inventory_data[item.item_name] = {
                "total": 0,
                "working": 0,
                "damaged": 0,
                "not_working": 0,
                "not_setup": 0,
                "brands": set(),
                "colors": set(),
            }

        inventory_data[item.item_name]["total"] += 1

        if item.brand:
            inventory_data[item.item_name]["brands"].add(item.brand)
        if item.color:
            inventory_data[item.item_name]["colors"].add(item.color)

        status_value = item.status.value.upper()
        if status_value == "WORKING":
            inventory_data[item.item_name]["working"] += 1
        elif status_value == "DAMAGED":
            inventory_data[item.item_name]["damaged"] += 1
        elif status_value == "NOT_WORKING":
            inventory_data[item.item_name]["not_working"] += 1
        elif status_value == "NOT_SETUP":
            inventory_data[item.item_name]["not_setup"] += 1

    # Convert sets to sorted comma-separated strings for template
    for item_name, data in inventory_data.items():
        data["brands"] = ", ".join(sorted(data["brands"])) if data["brands"] else "N/A"
        data["colors"] = ", ".join(sorted(data["colors"])) if data["colors"] else "N/A"

    # Summary counts
    total_items = len(items)
    total_working = sum(1 for item in items if item.status.value.upper() == "WORKING")
    total_damaged = sum(1 for item in items if item.status.value.upper() == "DAMAGED")
    total_not_working = sum(1 for item in items if item.status.value.upper() == "NOT_WORKING")
    total_not_setup = sum(1 for item in items if item.status.value.upper() == "NOT_SETUP")

    # Filters
    locations = sorted({item.location for item in items if item.location})
    brands = sorted({item.brand for item in items if item.brand})

    # Recently added / captured items
    # Prefer ordering by captured_date if present, else fallback to item_id desc
    def sort_key(i):
        if getattr(i, "captured_date", None):
            return i.captured_date
        return datetime.min  # ensure ones without date go to the end when reversed

    recently_captured_items = sorted(
        [i for i in items if getattr(i, "captured_date", None)],
        key=lambda x: x.captured_date,
        reverse=True
    )[:5]

    # If not enough with captured_date, fill from newest item_id
    if len(recently_captured_items) < 5:
        extras = (
            sorted(items, key=lambda i: i.item_id, reverse=True)
        )
        for ex in extras:
            if ex not in recently_captured_items:
                recently_captured_items.append(ex)
            if len(recently_captured_items) >= 5:
                break

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
        recently_added_items=recently_captured_items,  # now includes captured_date context
    )


# the logout for the button
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None) 
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home')) # Redirect to the home page



# The admin to add the item
@app.route("/admin/add-item", methods=["GET", "POST"])
def add_item():
    if not session.get("admin"):
        flash("Please log in as admin to add an item.", "warning")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        # --- Get required fields ---
        item_id = request.form["item_id"].strip()
        item_name = request.form["item_name"].strip()
        location = request.form["location"].strip()
        status_str = request.form["status"].strip()

        # --- Handle "Other" for Item Name (Required) ---
        if item_name == "__other__":
            item_name_other = request.form.get("item_name_other", "").strip()
            if not item_name_other:
                flash("Please specify the 'Other' item name.", "danger")
                return redirect(url_for("add_item"))
            item_name = item_name_other

        # --- Handle "Other" for Location (Required) ---
        if location == "__other__":
            location_other = request.form.get("location_other", "").strip()
            if not location_other:
                flash("Please specify the 'Other' lab name.", "danger")
                return redirect(url_for("add_item"))
            location = location_other
            
        # --- Get optional fields from the form ---
        asset_number_str = request.form.get("asset_number", "").strip()
        brand = request.form.get("brand", "").strip()
        color = request.form.get("color", "").strip()
        captured_date_str = request.form.get("captured_date", "").strip()

        # --- Handle "Other" for Brand (Optional) ---
        if brand == "__other__":
            brand = request.form.get("brand_other", "").strip()

        # Convert empty strings to None for optional fields that will be saved to the DB
        asset_number = asset_number_str or None
        brand = brand or None
        color = color or None

        # --- Validation ---
        if Item.query.get(item_id):
            flash(f"Item with ID '{item_id}' already exists.", "danger")
            return redirect(url_for("add_item"))

        if asset_number and Item.query.filter_by(asset_number=asset_number).first():
            flash(f"Item with Asset Number '{asset_number}' already exists.", "danger")
            return redirect(url_for("add_item"))

        try:
            item_status = ItemStatus(status_str)
        except ValueError:
            flash("Invalid item status. Please select a valid option.", "danger")
            return redirect(url_for("add_item"))

        captured_date_obj = None
        if captured_date_str:
            try:
                captured_date_obj = datetime.strptime(captured_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid date format for Captured Date. Please use YYYY-MM-DD.", "danger")
                return redirect(url_for("add_item"))

        # --- Create and save new item ---
        new_item = Item(
            item_id=item_id,
            asset_number=asset_number,
            item_name=item_name, # This is now the corrected value
            location=location,   # This is now the corrected value
            status=item_status,
            brand=brand,         # This is now the corrected value
            color=color,
        )
        
        if captured_date_obj:
            new_item.captured_date = captured_date_obj

        db.session.add(new_item)
        db.session.commit()

        flash("Item added successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    # --- For GET request ---
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
    Allows the admin to edit an existing item's details, including the new
    asset_number and captured_date fields, with support for custom location.
    """
    if not session.get("admin"):
        flash("Please log in as admin to edit items.", "warning")
        return redirect(url_for("admin_login"))

    item_to_edit = ItemModel.query.get_or_404(item_id)  # use ItemModel consistently

    if request.method == "POST":
        # Basic updates
        item_to_edit.item_name = request.form["item_name"].strip()

        location = request.form["location"].strip()
        if location == "__other__":
            location_other = request.form.get("location_other", "").strip()
            if not location_other:
                flash("Please specify the other lab name.", "danger")
                valid_statuses = [status.value for status in ItemStatus]
                return render_template("edit_item.html", item=item_to_edit, valid_statuses=valid_statuses)
            location = location_other
        item_to_edit.location = location

        # Asset number (allow empty => None) 
        asset_number = request.form.get("asset_number", "").strip()
        item_to_edit.asset_number = asset_number if asset_number else None

        # Update brand and color (handle empty strings as None)
        brand = request.form.get("brand", "").strip()
        color = request.form.get("color", "").strip()
        item_to_edit.brand = brand if brand else None
        item_to_edit.color = color if color else None

        # Status validation
        new_status = request.form["status"].strip()
        valid_statuses = [status.value for status in ItemStatus]
        if new_status not in valid_statuses:
            flash(f"Invalid item status. Please select one of: {', '.join(valid_statuses)}", "danger")
            return render_template("edit_item.html", item=item_to_edit, valid_statuses=valid_statuses)
        item_to_edit.status = ItemStatus(new_status)

        # Captured date: optional, if provided parse, else leave existing
        captured_date_str = request.form.get("captured_date", "").strip()
        if captured_date_str:
            try:
                # HTML datetime-local gives "YYYY-MM-DDTHH:MM"
                item_to_edit.captured_date = datetime.fromisoformat(captured_date_str)
            except ValueError:
                flash("Invalid captured date format.", "danger")
                valid_statuses = [status.value for status in ItemStatus]
                return render_template("edit_item.html", item=item_to_edit, valid_statuses=valid_statuses)

        db.session.commit()
        flash("Item updated successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    # GET: supply valid statuses
    valid_statuses = [status.value for status in ItemStatus]
    return render_template("edit_item.html", item=item_to_edit, valid_statuses=valid_statuses)



@app.route("/admin/export-items-pdf")
def export_items_pdf():
    if not session.get("admin"):
        flash("Please log in as admin to export items.", "warning")
        return redirect(url_for("admin_login"))

    # Fetch all items
    items = ItemModel.query.order_by(ItemModel.item_id.desc()).all()

    # Summary counts by status (same logic as before)
    total_items = len(items)
    total_working = sum(1 for item in items if item.status.value.upper() == "WORKING")
    total_damaged = sum(1 for item in items if item.status.value.upper() == "DAMAGED")
    total_not_working = sum(1 for item in items if item.status.value.upper() == "NOT_WORKING")
    total_not_setup = sum(1 for item in items if item.status.value.upper() == "NOT_SETUP")

    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=36,
        leftMargin=36,
        topMargin=72,
        bottomMargin=36
    )

    available_width = doc.width

    # Column widths for detailed table (adjust ratios as needed)
    col_widths = [
        available_width * 0.10,  # Item ID
        available_width * 0.12,  # Asset Number
        available_width * 0.15,  # Item Name
        available_width * 0.12,  # Location
        available_width * 0.10,  # Status
        available_width * 0.10,  # Brand
        available_width * 0.10,  # Color
        available_width * 0.13,  # Captured Date
    ]

    # Header row including new fields
    data = [[
        "Item ID",
        "Asset Number",
        "Item Name",
        "Location",
        "Status",
        "Brand",
        "Color",
        "Captured Date"
    ]]

    # Populate rows
    for item in items:
        captured = (
            item.captured_date.strftime("%Y-%m-%d %H:%M")
            if getattr(item, "captured_date", None)
            else "N/A"
        )
        asset = item.asset_number if getattr(item, "asset_number", None) else "N/A"
        data.append([
            item.item_id,
            asset,
            item.item_name,
            item.location,
            item.status.value.replace("_", " ").title(),
            item.brand or "N/A",
            item.color or "N/A",
            captured
        ])

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        spaceAfter=12,
        fontSize=18,
        leading=22,
        textColor=colors.black
    )
    date_style = ParagraphStyle(
        name='DateStyle',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.black
    )
    stat_style = ParagraphStyle(
        name='StatStyle',
        parent=styles['Normal'],
        alignment=TA_LEFT,
        fontSize=10,
        spaceBefore=2,
        spaceAfter=2
    )

    title = Paragraph("Lab Equipment Inventory Detailed Report", title_style)
    date_text = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", date_style)

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),

        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('TOPPADDING', (0, 1), (-1, -1), 5),

        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        page_num = canvas.getPageNumber()
        canvas.drawRightString(landscape(letter)[0] - 36, 30, f"Page {page_num}")
        canvas.drawString(36, 30, "Lab Equipment Inventory Detailed Report")
        canvas.restoreState()

    # Summary paragraphs
    total_items_text = Paragraph(f"Total Items: {total_items}", stat_style)
    working_items_text = Paragraph(f"Working Items: {total_working}", stat_style)
    damaged_items_text = Paragraph(f"Damaged Items: {total_damaged}", stat_style)
    not_working_text = Paragraph(f"Not Working Items: {total_not_working}", stat_style)
    not_setup_text = Paragraph(f"Not Setup Items: {total_not_setup}", stat_style)

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

    doc.build(content, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return send_file( 
        buffer,
        mimetype='application/pdf',
        download_name='lab_inventory_detailed_report.pdf',
        as_attachment=True   
    )

@app.route("/admin/delete-all", methods=["POST"])
def delete_all_items():
    if not session.get("admin"):  
        flash("Please log in as admin to perform this action.", "warning")
        return redirect(url_for("admin_login"))
    try:
        num = ItemModel.query.delete()
        db.session.commit()
        flash(f"Deleted all items ({num} records).", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete all items: {e}", "danger")
    return redirect(url_for("admin_dashboard")) 



if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
   # This creates the tables if they don't exist
    app.run(debug=True)
