import sqlite3
from datetime import datetime

# Connect to SQLite database (or create it if it doesn't exist)
connection = sqlite3.connect('smart_neighborhood_exchange.db')
cursor = connection.cursor()

# Create Users table
cursor.execute('''
CREATE TABLE IF NOT EXISTS Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    profile_image TEXT,
    location TEXT
);
''')

# Create Resources table
cursor.execute('''
CREATE TABLE IF NOT EXISTS Resources (
    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    images TEXT,
    category TEXT,
    availability TEXT,
    date_posted TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Spaces (
    space_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    images TEXT,
    category TEXT,
    availability TEXT,
    date_posted TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    images TEXT,
    category TEXT,
    date TEXT NOT NULL,  -- Event date instead of availability
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);
''')

# Create Messages table
cursor.execute('''
CREATE TABLE IF NOT EXISTS Messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER,
    receiver_id INTEGER,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (sender_id) REFERENCES Users(user_id),
    FOREIGN KEY (receiver_id) REFERENCES Users(user_id)
);
''')

# Create Reviews table
cursor.execute('''
CREATE TABLE IF NOT EXISTS Reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    reviewer_id INTEGER,
    rating INTEGER NOT NULL,
    comment TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (reviewer_id) REFERENCES Users(user_id)
);
''')

# Create Resource Reservations table
cursor.execute('''
CREATE TABLE IF NOT EXISTS ResourceReservations (
    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reservation_start_date TEXT NOT NULL,
    reservation_end_date TEXT NOT NULL,
    FOREIGN KEY (resource_id) REFERENCES Resources(resource_id),
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);
''')

# Create Space Reservations table
cursor.execute('''
CREATE TABLE IF NOT EXISTS SpaceReservations (
    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    space_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reservation_start_date TEXT NOT NULL,
    reservation_end_date TEXT NOT NULL,
    FOREIGN KEY (space_id) REFERENCES Spaces(space_id),
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);
''')

# Create EventAttendance table
cursor.execute('''
CREATE TABLE IF NOT EXISTS EventAttendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (event_id) REFERENCES Events(event_id),
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);
''')

# Create ResourceReviews table
cursor.execute('''
CREATE TABLE IF NOT EXISTS ResourceReviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL,
    reviewer_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),  -- Rating should be between 1 and 5
    comment TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (resource_id) REFERENCES Resources(resource_id),
    FOREIGN KEY (reviewer_id) REFERENCES Users(user_id)
);
''')

# Create SpaceReviews table
cursor.execute('''
CREATE TABLE IF NOT EXISTS SpaceReviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    space_id INTEGER NOT NULL,
    reviewer_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),  -- Rating should be between 1 and 5
    comment TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (space_id) REFERENCES Spaces(space_id),
    FOREIGN KEY (reviewer_id) REFERENCES Users(user_id)
);
''')         

# Drop Notifications table if it exists (optional)
cursor.execute("DROP TABLE IF EXISTS Notifications;")

# Add `created_at` column without a default value
cursor.execute("ALTER TABLE ResourceReservations ADD COLUMN created_at TEXT;")
cursor.execute("ALTER TABLE EventAttendance ADD COLUMN created_at TEXT;")
cursor.execute("ALTER TABLE SpaceReservations ADD COLUMN created_at TEXT;")

# Populate the `created_at` column with current timestamp for existing rows
current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
cursor.execute("UPDATE ResourceReservations SET created_at = ?", (current_timestamp,))
cursor.execute("UPDATE EventAttendance SET created_at = ?", (current_timestamp,))
cursor.execute("UPDATE SpaceReservations SET created_at = ?", (current_timestamp,))

# Commit changes and close the connection
connection.commit()
connection.close()

print("Database and tables created successfully.")
