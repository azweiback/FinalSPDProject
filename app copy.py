from flask import Flask, render_template, request, redirect, url_for, flash, session, g
import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATABASE = 'smart_neighborhood_exchange.db'
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed file types for images
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Helper function to get the user ID from the session
def get_user_id():
    return session.get('user_id')

#----------------------------------------------------------------------------------------------------------------------------------

"""
Login Routes
"""

# Main Page
@app.route('/')
def main():
    return render_template('login/main.html')

# Login Page
@app.route('/login')
def login():
    return render_template('login/login.html')

# Login processing route
@app.route('/process-login', methods=['POST'])
def process_login():
    email = request.form.get('email')
    password = request.form.get('password')

    # Query the database for the user
    con = get_db()
    cur = con.execute("SELECT * FROM Users WHERE email = ?", (email,))
    user = cur.fetchone()

    # Check if user exists and password matches
    if user and user[3] == password:  # Assuming password is in the 4th column
        session['user_id'] = user[0]  # Store user_id in session
        flash("Login successful!")
        return redirect(url_for('homepage'))
    else:
        flash("Invalid email or password.")
        return redirect(url_for('login'))

# Sign Up Page
@app.route('/signup')
def signup():
    return render_template('login/signup.html')

# Route to save email and password temporarily in session during signup
@app.route('/save-email-password', methods=['POST'])
def save_email_password():
    session['email'] = request.form.get('email')
    session['password'] = request.form.get('password')
    return redirect(url_for('signup'))

# Sign Up processing route
@app.route('/process-signup', methods=['POST'])
def process_signup():
    # Retrieve stored email and password from session
    email = session.get('email')
    password = session.get('password')

    # If email or password is missing, redirect to main page
    if not email or not password:
        flash("Session expired. Please start the registration again.")
        return redirect(url_for('main'))

    # Retrieve additional data from the signup form
    name = request.form.get('name')
    location = request.form.get('address')

    # Handle profile image upload
    profile_photo = request.files['profile_photo']
    if profile_photo and allowed_file(profile_photo.filename):
        filename = secure_filename(profile_photo.filename)
        profile_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        profile_photo.save(profile_photo_path)
    else:
        profile_photo_path = None

    # Insert new user data into the Users table
    con = get_db()
    try:
        con.execute("INSERT INTO Users (name, email, password, profile_image, location) VALUES (?, ?, ?, ?, ?)",
                    (name, email, password, profile_photo_path, location))
        con.commit()
        flash("Signup successful! Please confirm your registration.")
        return redirect(url_for('confirm_registration'))
    except sqlite3.IntegrityError:
        flash("This email is already registered. Please use a different email.")
        return redirect(url_for('signup'))

# Confirm Registration Page
@app.route('/confirm-registration', methods=['GET', 'POST'])
def confirm_registration():
    if request.method == 'POST':
        flash("Registration confirmed. You can now log in.")
        return redirect(url_for('homepage'))
    return render_template('login/confirm_registration.html')

#------------------------------------------------------------------------------------------------------------------------------------

# Home Page
@app.route('/homepage')
def homepage():
    con = get_db()

    # Fetch the newest resource
    newest_resource = con.execute("""
        SELECT r.resource_id, r.title, r.description, r.user_id, u.name
        FROM Resources r
        JOIN Users u ON r.user_id = u.user_id
        ORDER BY r.date_posted DESC
        LIMIT 1
    """).fetchone()

    # Fetch the newest space
    newest_space = con.execute("""
        SELECT s.space_id, s.title, s.description, s.user_id, u.name
        FROM Spaces s
        JOIN Users u ON s.user_id = u.user_id
        ORDER BY s.date_posted DESC
        LIMIT 1
    """).fetchone()

    # Fetch the newest event
    newest_event = con.execute("""
        SELECT e.event_id, e.title, e.description, e.user_id, u.name
        FROM Events e
        JOIN Users u ON e.user_id = u.user_id
        ORDER BY e.date DESC
        LIMIT 1
    """).fetchone()

    # Fetch the top-rated users based on average review rating
    top_rated_users = con.execute("""
        SELECT u.user_id, u.name, AVG(r.rating) as avg_rating
        FROM Users u
        JOIN Reviews r ON u.user_id = r.user_id
        GROUP BY u.user_id
        ORDER BY avg_rating DESC
        LIMIT 3
    """).fetchall()

    return render_template(
        'homepage.html',
        newest_resource=newest_resource,
        newest_space=newest_space,
        newest_event=newest_event,
        top_rated_users=top_rated_users
    )

# Dashboard Page
@app.route('/dashboard')
def dashboard():
    user_id = get_user_id()  # Function to get the current user's ID
    con = get_db()

    # Get notifications for reservations made in the last 24 hours
    last_24_hours = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    notifications = []

    # Fetch ResourceReservations notifications with user names
    resource_notifications = con.execute('''
        SELECT r.title, u.name, rr.created_at
        FROM ResourceReservations rr
        JOIN Resources r ON rr.resource_id = r.resource_id
        JOIN Users u ON rr.user_id = u.user_id
        WHERE r.user_id = ? AND rr.created_at >= ?
    ''', (user_id, last_24_hours)).fetchall()
    notifications.extend([("Resource", title, user_name, created_at) for title, user_name, created_at in resource_notifications])

    # Fetch SpaceReservations notifications with user names
    space_notifications = con.execute('''
        SELECT s.title, u.name, sr.created_at
        FROM SpaceReservations sr
        JOIN Spaces s ON sr.space_id = s.space_id
        JOIN Users u ON sr.user_id = u.user_id
        WHERE s.user_id = ? AND sr.created_at >= ?
    ''', (user_id, last_24_hours)).fetchall()
    notifications.extend([("Space", title, user_name, created_at) for title, user_name, created_at in space_notifications])

    # Fetch EventAttendance notifications with user names
    event_notifications = con.execute('''
        SELECT e.title, u.name, ea.created_at
        FROM EventAttendance ea
        JOIN Events e ON ea.event_id = e.event_id
        JOIN Users u ON ea.user_id = u.user_id
        WHERE e.user_id = ? AND ea.created_at >= ?
    ''', (user_id, last_24_hours)).fetchall()
    notifications.extend([("Event", title, user_name, created_at) for title, user_name, created_at in event_notifications])

    # Get user's active and upcoming reservations
    reservations = []

    # Fetch active and upcoming resource reservations with owner names
    resource_reservations = con.execute('''
        SELECT r.title, rr.reservation_start_date, rr.reservation_end_date, u.name
        FROM ResourceReservations rr
        JOIN Resources r ON rr.resource_id = r.resource_id
        JOIN Users u ON r.user_id = u.user_id
        WHERE rr.user_id = ? AND (
            rr.reservation_end_date >= ? OR rr.reservation_start_date >= ?
        )
    ''', (user_id, datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d'))).fetchall()
    reservations.extend([("Resource", title, start_date, end_date, reserved_from) for title, start_date, end_date, reserved_from in resource_reservations])

    # Fetch active and upcoming space reservations with owner names
    space_reservations = con.execute('''
        SELECT s.title, sr.reservation_start_date, sr.reservation_end_date, u.name
        FROM SpaceReservations sr
        JOIN Spaces s ON sr.space_id = s.space_id
        JOIN Users u ON s.user_id = u.user_id
        WHERE sr.user_id = ? AND (
            sr.reservation_end_date >= ? OR sr.reservation_start_date >= ?
        )
    ''', (user_id, datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d'))).fetchall()
    reservations.extend([("Space", title, start_date, end_date, reserved_from) for title, start_date, end_date, reserved_from in space_reservations])

    # Fetch active and upcoming event attendances
    event_attendances = con.execute('''
        SELECT e.title, e.date, u.name
        FROM EventAttendance ea
        JOIN Events e ON ea.event_id = e.event_id
        JOIN Users u ON e.user_id = u.user_id
        WHERE ea.user_id = ? AND e.date >= ?
    ''', (user_id, datetime.now().strftime('%Y-%m-%d'))).fetchall()
    reservations.extend([("Event", title, start_date, None, organizer) for title, start_date, organizer in event_attendances])

    return render_template(
        'dashboard.html',
        notifications=notifications,
        reservations=reservations
    )

#----------------------------------------------------------------------------------------------------------------------------------

"""
Resource Routes
"""

# Resources Home Page
@app.route('/resources')
def resources_home():
    return render_template('resources/resources_home.html')

# View Resources
@app.route('/view-resources')
def view_resources():
    user_id = get_user_id()  # Get the current user's ID
    search_query = request.args.get('query', '')  # Get the search query
    today = datetime.now().date().strftime('%Y-%m-%d')  # Fetch today's date

    con = get_db()
    if search_query:
        # Search query - filter results by user_name, title, description, category, or availability
        cur = con.execute("""
            SELECT r.resource_id, u.name AS user_name, r.title, r.description, r.images, r.category, 
                   CASE
                       WHEN EXISTS (
                           SELECT 1 FROM ResourceReservations rr
                           WHERE rr.resource_id = r.resource_id
                           AND DATE(rr.reservation_start_date) <= ?
                           AND DATE(rr.reservation_end_date) >= ?
                       ) THEN 'Reserved'
                       ELSE r.availability
                   END AS availability,
                   r.date_posted
            FROM Resources r
            JOIN Users u ON r.user_id = u.user_id
            WHERE r.user_id != ?
            AND (
                u.name LIKE ?
                OR r.title LIKE ?
                OR r.description LIKE ?
                OR r.category LIKE ?
                OR r.availability LIKE ?
            )
        """, (today, today, user_id, f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        # No search query - show all resources not belonging to the current user
        cur = con.execute("""
            SELECT r.resource_id, u.name AS user_name, r.title, r.description, r.images, r.category, 
                   CASE
                       WHEN EXISTS (
                           SELECT 1 FROM ResourceReservations rr
                           WHERE rr.resource_id = r.resource_id
                           AND DATE(rr.reservation_start_date) <= ?
                           AND DATE(rr.reservation_end_date) >= ?
                       ) THEN 'Reserved'
                       ELSE r.availability
                   END AS availability,
                   r.date_posted
            FROM Resources r
            JOIN Users u ON r.user_id = u.user_id
            WHERE r.user_id != ?
        """, (today, today, user_id))

    other_resources = cur.fetchall()
    return render_template('resources/view_resources.html', resources=other_resources)

# Reserve Resource
@app.route('/reserve-resource/<int:resource_id>', methods=['GET', 'POST'])
def reserve_resource(resource_id):
    user_id = get_user_id()
    con = get_db()

    # Fetch existing reservations for the resource
    cur = con.execute("""
        SELECT reservation_start_date, reservation_end_date 
        FROM ResourceReservations 
        WHERE resource_id = ?
    """, (resource_id,))
    existing_reservations = cur.fetchall()

    if request.method == 'POST':
        # Get reservation dates from form input
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')

        # Convert date strings to date objects
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Validate that the end date is not earlier than the start date
        if end_date < start_date:
            error_message = "The end date cannot be earlier than the start date. Please choose valid dates."
            return render_template(
                'resources/reserve_resource.html',
                resource_id=resource_id,
                error_message=error_message,
                existing_reservations=existing_reservations
            )

        # Validate that the selected dates do not overlap with existing reservations
        for reservation in existing_reservations:
            res_start = datetime.strptime(reservation[0], '%Y-%m-%d').date()
            res_end = datetime.strptime(reservation[1], '%Y-%m-%d').date()

            # Check for overlap
            if start_date <= res_end and end_date >= res_start:
                error_message = "The selected dates overlap with an existing reservation. Please choose different dates."
                return render_template(
                    'resources/reserve_resource.html',
                    resource_id=resource_id,
                    error_message=error_message,
                    existing_reservations=existing_reservations
                )

        # Add a created_at timestamp
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # If no overlap and valid dates, proceed with the reservation
        con.execute(
            """
            INSERT INTO ResourceReservations (
                resource_id, user_id, reservation_start_date, reservation_end_date, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (resource_id, user_id, start_date_str, end_date_str, created_at)
        )
        con.commit()
        return redirect(url_for('reserved_resources'))

    # Render form for GET request
    return render_template('resources/reserve_resource.html', resource_id=resource_id, existing_reservations=existing_reservations)

# Cancel resource reservation
@app.route('/cancel-resource-reservation/<int:reservation_id>', methods=['POST'])
def cancel_reservation(reservation_id):
    user_id = get_user_id()
    con = get_db()

    # Retrieve the resource ID to update availability later
    cur = con.execute("SELECT resource_id FROM ResourceReservations WHERE reservation_id = ? AND user_id = ?", (reservation_id, user_id))
    reservation = cur.fetchone()
    
    if reservation:
        resource_id = reservation[0]
        # Delete the reservation from the ResourceReservations table
        con.execute("DELETE FROM ResourceReservations WHERE reservation_id = ? AND user_id = ?", (reservation_id, user_id))
        # Update the resource's availability back to 'available'
        con.execute("UPDATE Resources SET availability = 'available' WHERE resource_id = ?", (resource_id,))
        con.commit()
        flash("Reservation cancelled successfully.")
    else:
        flash("You do not have permission to cancel this reservation.")
    
    return redirect(url_for('reserved_resources'))

# Edit Resource
@app.route('/edit-resource/<int:resource_id>', methods=['GET', 'POST'])
def edit_resource(resource_id):
    user_id = get_user_id()
    con = get_db()
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        availability = request.form.get('availability')

        con.execute(
            "UPDATE Resources SET title = ?, description = ?, category = ?, availability = ? "
            "WHERE resource_id = ? AND user_id = ?",
            (title, description, category, availability, resource_id, user_id)
        )
        con.commit()
        flash("Resource updated successfully!")
        return redirect(url_for('my_resources'))

    cur = con.execute("SELECT * FROM Resources WHERE resource_id = ? AND user_id = ?", (resource_id, user_id))
    resource = cur.fetchone()
    if resource is None:
        flash("Resource not found or you do not have permission to edit it.")
        return redirect(url_for('my_resources'))

    return render_template('resources/edit_resource.html', resource=resource)

# Delete Resource
@app.route('/confirm-delete-resource/<int:resource_id>', methods=['GET', 'POST'])
def confirm_delete_resource(resource_id):
    user_id = get_user_id()
    con = get_db()
    
    if request.method == 'POST':
        # Delete the resource from the database
        con.execute("DELETE FROM Resources WHERE resource_id = ? AND user_id = ?", (resource_id, user_id))
        con.commit()
        flash("Resource deleted successfully!")
        return redirect(url_for('my_resources'))
    
    # Fetch the resource for confirmation display
    cur = con.execute("SELECT title, description FROM Resources WHERE resource_id = ? AND user_id = ?", (resource_id, user_id))
    resource = cur.fetchone()
    
    # If resource not found or unauthorized access
    if resource is None:
        flash("Resource not found or you do not have permission to delete it.")
        return redirect(url_for('my_resources'))
    
    return render_template('resources/confirm_delete_resource.html', resource=resource, resource_id=resource_id)

# Reserved Resources
@app.route('/reserved-resources')
def reserved_resources():
    user_id = get_user_id()
    con = get_db()
    # Fetch the user's active reservations and related resource details, including the owner's name
    cur = con.execute("""
        SELECT rr.reservation_id, r.title, rr.reservation_start_date, rr.reservation_end_date, u.name AS reserved_from
        FROM ResourceReservations rr
        JOIN Resources r ON rr.resource_id = r.resource_id
        JOIN Users u ON r.user_id = u.user_id
        WHERE rr.user_id = ?
    """, (user_id,))
    reservations = cur.fetchall()
    return render_template('resources/reserved_resources.html', reservations=reservations)

# Add New Resource
@app.route('/new-resource', methods=['GET', 'POST'])
def new_resource():
    user_id = get_user_id()
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        availability = request.form.get('availability')
        date_posted = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Handle image upload
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            # Ensure upload folder exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename).replace("\\", "/")
            image.save(image_path)
        else:
            flash("Invalid image file. Please upload a PNG, JPG, JPEG, or GIF file.")
            return redirect(url_for('new_resource'))

        # Save resource details in the database
        con = get_db()
        con.execute(
            "INSERT INTO Resources (user_id, title, description, images, category, availability, date_posted) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, title, description, image_path, category, availability, date_posted)
        )
        con.commit()

        flash("Resource added successfully!")
        return redirect(url_for('my_resources'))

    return render_template('resources/new_resource.html')

# My Resources
@app.route('/my-resources')
def my_resources():
    user_id = get_user_id()
    con = get_db()

    # Fetch today's date
    today = datetime.now().date().strftime('%Y-%m-%d')

    # Query to fetch all resources owned by the user
    cur = con.execute("""
        SELECT r.resource_id, r.user_id, r.title, r.description, r.images, r.category, 
               CASE
                   WHEN EXISTS (
                       SELECT 1 FROM ResourceReservations rr
                       WHERE rr.resource_id = r.resource_id
                       AND DATE(rr.reservation_start_date) <= ?
                       AND DATE(rr.reservation_end_date) >= ?
                   ) THEN 'Reserved'
                   ELSE r.availability
               END AS availability,
               r.date_posted
        FROM Resources r
        WHERE r.user_id = ?
    """, (today, today, user_id))
    
    resources = cur.fetchall()

    return render_template('resources/my_resources.html', resources=resources)

#----------------------------------------------------------------------------------------------------------------------------------

"""
Space Routes
"""

# Spaces Home Page
@app.route('/spaces')
def spaces_home():
    return render_template('spaces/spaces_home.html')

# View Spaces
@app.route('/view-spaces')
def view_spaces():
    user_id = get_user_id()  # Get the current user's ID
    search_query = request.args.get('query', '')  # Get the search query
    today = datetime.now().date().strftime('%Y-%m-%d')  # Fetch today's date

    con = get_db()
    if search_query:
        # Search query - filter results by user_name, title, description, category, or availability
        cur = con.execute("""
            SELECT s.space_id, u.name AS user_name, s.title, s.description, s.images, s.category, 
                   CASE
                       WHEN EXISTS (
                           SELECT 1 FROM SpaceReservations sr
                           WHERE sr.space_id = s.space_id
                           AND DATE(sr.reservation_start_date) <= ?
                           AND DATE(sr.reservation_end_date) >= ?
                       ) THEN 'Reserved'
                       ELSE s.availability
                   END AS availability,
                   s.date_posted
            FROM Spaces s
            JOIN Users u ON s.user_id = u.user_id
            WHERE s.user_id != ?
            AND (
                u.name LIKE ?
                OR s.title LIKE ?
                OR s.description LIKE ?
                OR s.category LIKE ?
                OR s.availability LIKE ?
            )
        """, (today, today, user_id, f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        # No search query - show all spaces not belonging to the current user
        cur = con.execute("""
            SELECT s.space_id, u.name AS user_name, s.title, s.description, s.images, s.category, 
                   CASE
                       WHEN EXISTS (
                           SELECT 1 FROM SpaceReservations sr
                           WHERE sr.space_id = s.space_id
                           AND DATE(sr.reservation_start_date) <= ?
                           AND DATE(sr.reservation_end_date) >= ?
                       ) THEN 'Reserved'
                       ELSE s.availability
                   END AS availability,
                   s.date_posted
            FROM Spaces s
            JOIN Users u ON s.user_id = u.user_id
            WHERE s.user_id != ?
        """, (today, today, user_id))

    other_spaces = cur.fetchall()
    return render_template('spaces/view_spaces.html', spaces=other_spaces)

# Reserve Space
@app.route('/reserve-space/<int:space_id>', methods=['GET', 'POST'])
def reserve_space(space_id):
    user_id = get_user_id()
    con = get_db()

    # Fetch existing reservations for the space
    cur = con.execute("""
        SELECT reservation_start_date, reservation_end_date 
        FROM SpaceReservations 
        WHERE space_id = ?
    """, (space_id,))
    existing_reservations = cur.fetchall()

    if request.method == 'POST':
        # Get reservation dates from form input
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')

        # Convert date strings to date objects
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Validate that the end date is not earlier than the start date
        if end_date < start_date:
            error_message = "The end date cannot be earlier than the start date. Please choose valid dates."
            return render_template(
                'spaces/reserve_space.html',
                space_id=space_id,
                error_message=error_message,
                existing_reservations=existing_reservations
            )

        # Validate that the selected dates do not overlap with existing reservations
        for reservation in existing_reservations:
            res_start = datetime.strptime(reservation[0], '%Y-%m-%d').date()
            res_end = datetime.strptime(reservation[1], '%Y-%m-%d').date()

            # Check for overlap
            if start_date <= res_end and end_date >= res_start:
                error_message = "The selected dates overlap with an existing reservation. Please choose different dates."
                return render_template(
                    'spaces/reserve_space.html',
                    space_id=space_id,
                    error_message=error_message,
                    existing_reservations=existing_reservations
                )

        # Add a created_at timestamp
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # If no overlap and valid dates, proceed with the reservation
        con.execute(
            """
            INSERT INTO SpaceReservations (
                space_id, user_id, reservation_start_date, reservation_end_date, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (space_id, user_id, start_date_str, end_date_str, created_at)
        )
        con.commit()
        return redirect(url_for('reserved_spaces'))

    # Render form for GET request
    return render_template('spaces/reserve_space.html', space_id=space_id, existing_reservations=existing_reservations)

# Cancel Space Reservation
@app.route('/cancel-space-reservation/<int:reservation_id>', methods=['POST'])
def cancel_space_reservation(reservation_id):
    user_id = get_user_id()
    con = get_db()

    # Retrieve the space ID to update availability later
    cur = con.execute("SELECT space_id FROM SpaceReservations WHERE reservation_id = ? AND user_id = ?", (reservation_id, user_id))
    reservation = cur.fetchone()
    
    if reservation:
        space_id = reservation[0]
        # Delete the reservation from the SpaceReservations table
        con.execute("DELETE FROM SpaceReservations WHERE reservation_id = ? AND user_id = ?", (reservation_id, user_id))
        # Update the space's availability back to 'available'
        con.execute("UPDATE Spaces SET availability = 'available' WHERE space_id = ?", (space_id,))
        con.commit()
        flash("Reservation cancelled successfully.")
    else:
        flash("You do not have permission to cancel this reservation.")
    
    return redirect(url_for('reserved_spaces'))

# Edit Space
@app.route('/edit-space/<int:space_id>', methods=['GET', 'POST'])
def edit_space(space_id):
    user_id = get_user_id()
    con = get_db()
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        availability = request.form.get('availability')

        con.execute(
            "UPDATE Spaces SET title = ?, description = ?, category = ?, availability = ? "
            "WHERE space_id = ? AND user_id = ?",
            (title, description, category, availability, space_id, user_id)
        )
        con.commit()
        flash("Space updated successfully!")
        return redirect(url_for('my_spaces'))

    cur = con.execute("SELECT * FROM Spaces WHERE space_id = ? AND user_id = ?", (space_id, user_id))
    space = cur.fetchone()
    if space is None:
        flash("Space not found or you do not have permission to edit it.")
        return redirect(url_for('my_spaces'))

    return render_template('spaces/edit_space.html', space=space)

# Delete Space
@app.route('/confirm-delete-space/<int:space_id>', methods=['GET', 'POST'])
def confirm_delete_space(space_id):
    user_id = get_user_id()
    con = get_db()
    
    if request.method == 'POST':
        # Delete the space from the database
        con.execute("DELETE FROM Spaces WHERE space_id = ? AND user_id = ?", (space_id, user_id))
        con.commit()
        flash("Space deleted successfully!")
        return redirect(url_for('my_spaces'))
    
    # Fetch the space for confirmation display
    cur = con.execute("SELECT title, description FROM Spaces WHERE space_id = ? AND user_id = ?", (space_id, user_id))
    space = cur.fetchone()
    
    # If space not found or unauthorized access
    if space is None:
        flash("Space not found or you do not have permission to delete it.")
        return redirect(url_for('my_spaces'))
    
    return render_template('spaces/confirm_delete_space.html', space=space, space_id=space_id)

# Reserved Spaces 
@app.route('/reserved-spaces')
def reserved_spaces():
    user_id = get_user_id()
    con = get_db()
    # Fetch the user's active reservations and related space details, including the owner's name
    cur = con.execute("""
        SELECT sr.reservation_id, s.title, sr.reservation_start_date, sr.reservation_end_date, u.name AS reserved_from
        FROM SpaceReservations sr
        JOIN Spaces s ON sr.space_id = s.space_id
        JOIN Users u ON s.user_id = u.user_id
        WHERE sr.user_id = ?
    """, (user_id,))
    reservations = cur.fetchall()
    return render_template('spaces/reserved_spaces.html', reservations=reservations)

# Add New Space
@app.route('/new-space', methods=['GET', 'POST'])
def new_space():
    user_id = get_user_id()
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        availability = request.form.get('availability')
        date_posted = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Handle image upload
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            # Ensure upload folder exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename).replace("\\", "/")
            image.save(image_path)
        else:
            flash("Invalid image file. Please upload a PNG, JPG, JPEG, or GIF file.")
            return redirect(url_for('new_space'))

        # Save space details in the database
        con = get_db()
        con.execute(
            "INSERT INTO Spaces (user_id, title, description, images, category, availability, date_posted) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, title, description, image_path, category, availability, date_posted)
        )
        con.commit()

        flash("Space added successfully!")
        return redirect(url_for('my_spaces'))

    return render_template('spaces/new_space.html')

# My Spaces route
@app.route('/my-spaces')
def my_spaces():
    user_id = get_user_id()  # Get the current user's ID
    today = datetime.now().date().strftime('%Y-%m-%d')  # Fetch today's date

    con = get_db()
    cur = con.execute("""
        SELECT s.space_id, s.user_id, s.title, s.description, s.images, s.category, 
               CASE
                   WHEN EXISTS (
                       SELECT 1 FROM SpaceReservations sr
                       WHERE sr.space_id = s.space_id
                       AND DATE(sr.reservation_start_date) <= ?
                       AND DATE(sr.reservation_end_date) >= ?
                   ) THEN 'Reserved'
                   ELSE s.availability
               END AS availability,
               s.date_posted
        FROM Spaces s
        WHERE s.user_id = ?
    """, (today, today, user_id))

    spaces = cur.fetchall()
    return render_template('spaces/my_spaces.html', spaces=spaces)

#----------------------------------------------------------------------------------------------------------------------------------
"""
Event Routes
"""

# Events Home Page
@app.route('/events')
def events_home():
    return render_template('events/events_home.html')

# View Events Page
@app.route('/view-events')
def view_events():
    user_id = get_user_id()  # Get the current user's ID
    search_query = request.args.get('query', '')  # Get the search query

    con = get_db()
    if search_query:
        # Search query - filter results by user_name, title, description, or category
        cur = con.execute("""
            SELECT e.event_id, u.name AS user_name, e.title, e.description, e.images, e.category, e.date 
            FROM Events e
            JOIN Users u ON e.user_id = u.user_id
            WHERE e.user_id != ?
            AND e.date >= date('now')  -- Only future events
            AND (
                u.name LIKE ?
                OR e.title LIKE ?
                OR e.description LIKE ?
                OR e.category LIKE ?
            )
        """, (user_id, f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        # No search query - show all future events not belonging to the current user
        cur = con.execute("""
            SELECT e.event_id, u.name AS user_name, e.title, e.description, e.images, e.category, e.date 
            FROM Events e
            JOIN Users u ON e.user_id = u.user_id
            WHERE e.user_id != ? AND e.date >= date('now')
        """, (user_id,))

    other_events = cur.fetchall()
    return render_template('events/view_events.html', events=other_events)

# Attend Event Page
@app.route('/attend-event/<int:event_id>', methods=['POST'])
def attend_event(event_id):
    user_id = get_user_id()  # Get the current user's ID

    con = get_db()

    # Check if the user has already attended this event
    cur = con.execute(
        """
        SELECT * 
        FROM EventAttendance 
        WHERE event_id = ? AND user_id = ?
        """,
        (event_id, user_id)
    )
    existing_attendance = cur.fetchone()

    if existing_attendance:
        flash("You are already attending this event!")
        return redirect(url_for('view_events'))  # Redirect to the events page

    # Add a created_at timestamp
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Insert attendance record into the EventAttendance table with created_at
    con.execute(
        """
        INSERT INTO EventAttendance (event_id, user_id, created_at) 
        VALUES (?, ?, ?)
        """,
        (event_id, user_id, created_at)
    )
    con.commit()

    flash("You are now attending this event!")
    return redirect(url_for('events_attending'))

# Cancel Event Attendance
@app.route('/cancel-event-attendance/<int:attendance_id>', methods=['POST'])
def cancel_event_attendance(attendance_id):
    user_id = get_user_id()
    con = get_db()

    # Check if the user has permission to cancel this attendance
    cur = con.execute("SELECT event_id FROM EventAttendance WHERE attendance_id = ? AND user_id = ?", (attendance_id, user_id))
    attendance = cur.fetchone()
    
    if attendance:
        # Delete the attendance record
        con.execute("DELETE FROM EventAttendance WHERE attendance_id = ? AND user_id = ?", (attendance_id, user_id))
        con.commit()
        flash("You are no longer attending this event.")
    else:
        flash("You do not have permission to cancel this attendance.")
    
    return redirect(url_for('events_attending'))

# Edit Event
@app.route('/edit-event/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    user_id = get_user_id()
    con = get_db()
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        event_date = request.form.get('date')  # Update event date

        con.execute(
            "UPDATE Events SET title = ?, description = ?, category = ?, date = ? "
            "WHERE event_id = ? AND user_id = ?",
            (title, description, category, event_date, event_id, user_id)
        )
        con.commit()
        flash("Event updated successfully!")
        return redirect(url_for('my_events'))

    cur = con.execute("SELECT * FROM Events WHERE event_id = ? AND user_id = ?", (event_id, user_id))
    event = cur.fetchone()
    if event is None:
        flash("Event not found or you do not have permission to edit it.")
        return redirect(url_for('my_events'))

    return render_template('events/edit_event.html', event=event)

# Delete Event
@app.route('/confirm-delete-event/<int:event_id>', methods=['GET', 'POST'])
def confirm_delete_event(event_id):
    user_id = get_user_id()
    con = get_db()
    
    if request.method == 'POST':
        # Delete the event from the database
        con.execute("DELETE FROM Events WHERE event_id = ? AND user_id = ?", (event_id, user_id))
        con.commit()
        flash("Event deleted successfully!")
        return redirect(url_for('my_events'))
    
    # Fetch the event for confirmation display
    cur = con.execute("SELECT title, description FROM Events WHERE event_id = ? AND user_id = ?", (event_id, user_id))
    event = cur.fetchone()
    
    # If event not found or unauthorized access
    if event is None:
        flash("Event not found or you do not have permission to delete it.")
        return redirect(url_for('my_events'))
    
    return render_template('events/confirm_delete_event.html', event=event, event_id=event_id)

# Events Attending Page
@app.route('/events-attending')
def events_attending():
    user_id = get_user_id()
    con = get_db()

    # Fetch events the user is attending along with the organizer's name
    cur = con.execute("""
        SELECT e.event_id, e.title, e.description, e.images, e.category, e.date, ea.attendance_id, u.name AS organizer
        FROM EventAttendance ea
        JOIN Events e ON ea.event_id = e.event_id
        JOIN Users u ON e.user_id = u.user_id
        WHERE ea.user_id = ?
    """, (user_id,))
    attending_events = cur.fetchall()

    return render_template('events/events_attending.html', events=attending_events)

# Add New Event
@app.route('/new-event', methods=['GET', 'POST'])
def new_event():
    user_id = get_user_id()
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        event_date = request.form.get('date')  # Get event date

        # Handle image upload
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            # Ensure upload folder exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename).replace("\\", "/")
            image.save(image_path)
        else:
            flash("Invalid image file. Please upload a PNG, JPG, JPEG, or GIF file.")
            return redirect(url_for('new_event'))

        # Save event details in the database
        con = get_db()
        con.execute(
            "INSERT INTO Events (user_id, title, description, images, category, date) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, title, description, image_path, category, event_date)
        )
        con.commit()

        flash("Event added successfully!")
        return redirect(url_for('my_events'))

    return render_template('events/new_event.html')

# My Events route
@app.route('/my-events')
def my_events():
    user_id = get_user_id()
    con = get_db()
    cur = con.execute("SELECT event_id, user_id, title, description, images, category, date FROM Events WHERE user_id = ?", (user_id,))
    events = cur.fetchall()
    return render_template('events/my_events.html', events=events)

#----------------------------------------------------------------------------------------------------------------------------------

"""
Reviews Routes
"""

# Reviews Home Page
@app.route('/reviews')
def reviews_home():
    return render_template('reviews/reviews_home.html')

# Add Review Options
@app.route('/add-review-options')
def add_review_options():
    return render_template('reviews/add_review_options.html')

# My Review Options
@app.route('/my-review-options')
def my_review_options():
    return render_template('reviews/my_review_options.html')

# Add User Review Page
@app.route('/add-user-review', methods=['GET', 'POST'])
def add_user_review():
    user_id = get_user_id()  # Get the current user's ID
    con = get_db()
    
    if request.method == 'POST':
        reviewed_user_id = request.form.get('user_id')
        rating = request.form.get('rating')
        comment = request.form.get('comment')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert review into the Reviews table
        con.execute(
            "INSERT INTO Reviews (user_id, reviewer_id, rating, comment, timestamp) VALUES (?, ?, ?, ?, ?)",
            (reviewed_user_id, user_id, rating, comment, timestamp)
        )
        con.commit()

        flash("User review submitted successfully!")
        return redirect(url_for('reviews_home'))

    # For GET request, fetch all other users to populate the dropdown list
    cur = con.execute("SELECT user_id, name FROM Users WHERE user_id != ?", (user_id,))
    users = cur.fetchall()

    return render_template('reviews/add_user_review.html', users=users)


# View My User Reviews Page
@app.route('/my-user-reviews')
def my_user_reviews():
    user_id = get_user_id()  # Get the current user's ID
    con = get_db()

    # Fetch reviews made about the user
    user_reviews = con.execute("""
        SELECT u.name AS reviewer_name, r.rating, r.comment, r.timestamp
        FROM Reviews r
        JOIN Users u ON r.reviewer_id = u.user_id
        WHERE r.user_id = ?
    """, (user_id,)).fetchall()

    return render_template('reviews/my_user_reviews.html', reviews=user_reviews)

# Add Resource Review Page
@app.route('/add-resource-review', methods=['GET', 'POST'])
def add_resource_review():
    user_id = get_user_id()
    con = get_db()

    if request.method == 'POST':
        resource_id = request.form.get('resource_id')
        rating = request.form.get('rating')
        comment = request.form.get('comment')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert review into the ResourceReviews table
        con.execute(
            "INSERT INTO ResourceReviews (resource_id, reviewer_id, rating, comment, timestamp) VALUES (?, ?, ?, ?, ?)",
            (resource_id, user_id, rating, comment, timestamp)
        )
        con.commit()

        flash("Resource review submitted successfully!")
        return redirect(url_for('reviews_home'))

    # For GET request, fetch all resources to populate the dropdown list
    cur = con.execute("SELECT resource_id, title FROM Resources")
    resources = cur.fetchall()

    return render_template('reviews/add_resource_review.html', resources=resources)


# View My Resource Reviews Page
@app.route('/my-resource-reviews')
def my_resource_reviews():
    user_id = get_user_id()  # Get the current user's ID
    con = get_db()

    # Fetch reviews about the user's resources
    resource_reviews = con.execute("""
        SELECT res.title AS resource_title, rr.rating, rr.comment, rr.timestamp
        FROM ResourceReviews rr
        JOIN Resources res ON rr.resource_id = res.resource_id
        WHERE res.user_id = ?
    """, (user_id,)).fetchall()

    return render_template('reviews/my_resource_reviews.html', reviews=resource_reviews)


# Add Space Review Page
@app.route('/add-space-review', methods=['GET', 'POST'])
def add_space_review():
    user_id = get_user_id()
    con = get_db()

    if request.method == 'POST':
        space_id = request.form.get('space_id')
        rating = request.form.get('rating')
        comment = request.form.get('comment')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert review into the SpaceReviews table
        con.execute(
            "INSERT INTO SpaceReviews (space_id, reviewer_id, rating, comment, timestamp) VALUES (?, ?, ?, ?, ?)",
            (space_id, user_id, rating, comment, timestamp)
        )
        con.commit()

        flash("Space review submitted successfully!")
        return redirect(url_for('reviews_home'))

    # For GET request, fetch all spaces to populate the dropdown list
    cur = con.execute("SELECT space_id, title FROM Spaces")
    spaces = cur.fetchall()

    return render_template('reviews/add_space_review.html', spaces=spaces)


# View My Space Reviews Page
@app.route('/my-space-reviews')
def my_space_reviews():
    user_id = get_user_id()  # Get the current user's ID
    con = get_db()

    # Fetch reviews about the user's spaces
    space_reviews = con.execute("""
        SELECT s.title AS space_title, sr.rating, sr.comment, sr.timestamp
        FROM SpaceReviews sr
        JOIN Spaces s ON sr.space_id = s.space_id
        WHERE s.user_id = ?
    """, (user_id,)).fetchall()

    return render_template('reviews/my_space_reviews.html', reviews=space_reviews)

# View all reviews with search functionality
@app.route('/view-all-reviews')
def view_all_reviews():
    con = get_db()
    search_query = request.args.get('query', '')  # Get the search query from the URL parameters

    # Fetch user reviews with search filter
    user_reviews = con.execute("""
        SELECT 'User Review' AS type, u.name AS item_name, r.rating, r.comment, r.timestamp
        FROM Reviews r
        JOIN Users u ON r.user_id = u.user_id
        WHERE u.name LIKE ? OR r.comment LIKE ?
    """, (f'%{search_query}%', f'%{search_query}%')).fetchall()

    # Fetch resource reviews with search filter
    resource_reviews = con.execute("""
        SELECT 'Resource Review' AS type, res.title AS item_name, rr.rating, rr.comment, rr.timestamp
        FROM ResourceReviews rr
        JOIN Resources res ON rr.resource_id = res.resource_id
        WHERE res.title LIKE ? OR rr.comment LIKE ?
    """, (f'%{search_query}%', f'%{search_query}%')).fetchall()

    # Fetch space reviews with search filter
    space_reviews = con.execute("""
        SELECT 'Space Review' AS type, s.title AS item_name, sr.rating, sr.comment, sr.timestamp
        FROM SpaceReviews sr
        JOIN Spaces s ON sr.space_id = s.space_id
        WHERE s.title LIKE ? OR sr.comment LIKE ?
    """, (f'%{search_query}%', f'%{search_query}%')).fetchall()

    # Combine all reviews into one list
    all_reviews = user_reviews + resource_reviews + space_reviews

    return render_template('reviews/view_all_reviews.html', all_reviews=all_reviews, search_query=search_query)

#----------------------------------------------------------------------------------------------------------------------------------
"""
Profile Routes
"""

# Profile Page
@app.route('/profile')
def profile():
    user_id = get_user_id()  # Assuming you have a function to get the current user's ID
    con = get_db()
    cur = con.execute("SELECT name, email, profile_image, location FROM Users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()

    if user:
        user_data = {
            'name': user[0],
            'email': user[1],
            'profile_image': user[2],
            'location': user[3]
        }
        return render_template('profile/profile.html', user=user_data)
    else:
        flash("User not found.")
        return redirect(url_for('homepage'))

# Edit Profile Page
@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    user_id = get_user_id()
    con = get_db()

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        location = request.form.get('location')
        
        # Handle profile image upload
        profile_image = request.files['profile_image']
        if profile_image and allowed_file(profile_image.filename):
            filename = secure_filename(profile_image.filename)
            # Ensure upload folder exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            profile_image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename).replace("\\", "/")
            profile_image.save(profile_image_path)
        else:
            # If no new image is uploaded, retain the existing path
            cur = con.execute("SELECT profile_image FROM Users WHERE user_id = ?", (user_id,))
            profile_image_path = cur.fetchone()[0]

        # Update user information in the database
        con.execute(
            "UPDATE Users SET name = ?, email = ?, location = ?, profile_image = ? WHERE user_id = ?",
            (name, email, location, profile_image_path, user_id)
        )
        con.commit()

        flash("Profile updated successfully!")
        return redirect(url_for('profile'))

    # For GET request, fetch current user information
    cur = con.execute("SELECT name, email, profile_image, location FROM Users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()

    if user:
        user_data = {
            'name': user[0],
            'email': user[1],
            'profile_image': user[2],
            'location': user[3]
        }
        return render_template('profile/edit_profile.html', user=user_data)
    else:
        flash("User not found.")
        return redirect(url_for('homepage'))

#----------------------------------------------------------------------------------------------------------------------------------

"""
Message Routes
"""

# User Inbox
@app.route('/inbox')
def inbox():
    user_id = get_user_id()
    con = get_db()

    # Select unique pairs of users where the current user is involved, along with the other user's name
    cur = con.execute("""
        SELECT DISTINCT
            CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END AS other_user_id,
            u.name AS other_user_name,
            MAX(timestamp) AS last_message_time
        FROM Messages
        JOIN Users u ON u.user_id = CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END
        WHERE sender_id = ? OR receiver_id = ?
        GROUP BY other_user_id
        ORDER BY last_message_time DESC
    """, (user_id, user_id, user_id, user_id))

    conversations = cur.fetchall()
    return render_template('messages/inbox.html', conversations=conversations)

# Conversation
@app.route('/conversation/<int:other_user_id>', methods=['GET', 'POST'])
def conversation(other_user_id):
    user_id = get_user_id()
    con = get_db()
    
    if request.method == 'POST':
        content = request.form.get('message')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert the new message
        con.execute("""
            INSERT INTO Messages (sender_id, receiver_id, content, timestamp) 
            VALUES (?, ?, ?, ?)
        """, (user_id, other_user_id, content, timestamp))
        
        con.commit()
        return redirect(url_for('conversation', other_user_id=other_user_id))
    
    # Fetch all messages between the current user and the other user
    cur = con.execute("""
        SELECT sender_id, content, timestamp 
        FROM Messages 
        WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
        ORDER BY timestamp
    """, (user_id, other_user_id, other_user_id, user_id))
    
    messages = cur.fetchall()

    # Fetch the other user's name for display in the conversation header
    other_user_name = con.execute("SELECT name FROM Users WHERE user_id = ?", (other_user_id,)).fetchone()[0]

    return render_template('messages/conversation.html', messages=messages, other_user_id=other_user_id, other_user_name=other_user_name, user_id=user_id)

# New message 
@app.route('/new-message')
def new_message():
    con = get_db()
    user_id = get_user_id()
    
    # Fetch list of all users except the current user
    users = con.execute("SELECT user_id, name FROM Users WHERE user_id != ?", (user_id,)).fetchall()
    print("Users fetched:", users)  # Debugging line
    return render_template('messages/new_message.html', users=users)

# Send a new message
@app.route('/send-new-message', methods=['POST'])
def send_new_message():
    sender_id = get_user_id()
    receiver_id = request.form['receiver_id']
    message_content = request.form['message']
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    con = get_db()
    # Insert the new message into the Messages table
    con.execute("""
        INSERT INTO Messages (sender_id, receiver_id, content, timestamp)
        VALUES (?, ?, ?, ?)
    """, (sender_id, receiver_id, message_content, timestamp))
    con.commit()

    flash("Message sent successfully.")
    return redirect(url_for('inbox'))

#----------------------------------------------------------------------------------------------------------------------------------

# Logout Page
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.")
    return redirect(url_for('main'))

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
