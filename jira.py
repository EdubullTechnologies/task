import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px
from datetime import datetime, timedelta
import hashlib
import re
import time
import random
import string
from io import StringIO
import os
from mysql.connector import Error

# Set page configuration
st.set_page_config(
    page_title="Edubull Task Tracker",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state if not already done
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if 'show_profile' not in st.session_state:
    st.session_state['show_profile'] = False

if 'show_notifications' not in st.session_state:
    st.session_state['show_notifications'] = False

if 'current_page' not in st.session_state:
    st.session_state['current_page'] = "Dashboard"

# Database connection configuration using Streamlit secrets
try:
    # When running on Streamlit Cloud, use secrets management
    DB_CONFIG = st.secrets["mysql"]
except Exception as e:
    # For local development, use a local .streamlit/secrets.toml file
    # or display instructions on how to set up the database connection
    st.error("Database configuration not found!")
    st.info("""
    To run this app locally, please create a `.streamlit/secrets.toml` file with your database credentials:
    ```
    [mysql]
    host = "your-database-host"
    database = "edubull_tasks"
    user = "your-database-user"
    password = "your-database-password"
    ```
    Make sure to add `.streamlit/secrets.toml` to your `.gitignore` file to avoid exposing your credentials.
    """)
    # Set empty credentials to prevent errors, the app will show connection errors later
    DB_CONFIG = {
        "host": "",
        "database": "",
        "user": "",
        "password": ""
    }

# Function to create database connection
def create_connection():
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            return connection
    except Error as e:
        st.error(f"Error while connecting to MySQL: {e}")
    return connection

# Function to execute database queries
def execute_query(query, params=None, fetch=False):
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch:
                result = cursor.fetchall()
                return result
            else:
                connection.commit()
                return True
        except Error as e:
            st.error(f"Error: {e}")
            return None
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    return None

# Function to create necessary database tables if they don't exist
def initialize_database():
    # Create users table with password field and role
    create_users_table = """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        full_name VARCHAR(100) NOT NULL,
        email VARCHAR(100) NOT NULL,
        department VARCHAR(100),
        password_hash VARCHAR(64),
        role VARCHAR(20) DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    # Create statuses table
    create_statuses_table = """
    CREATE TABLE IF NOT EXISTS statuses (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(50) NOT NULL UNIQUE,
        display_order INT NOT NULL
    );
    """
    
    # Create tasks table
    create_tasks_table = """
    CREATE TABLE IF NOT EXISTS tasks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        description TEXT,
        assignee_id INT,
        reporter_id INT NOT NULL,
        status_id INT NOT NULL,
        priority VARCHAR(20) NOT NULL,
        deadline DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (assignee_id) REFERENCES users(id),
        FOREIGN KEY (reporter_id) REFERENCES users(id),
        FOREIGN KEY (status_id) REFERENCES statuses(id)
    );
    """
    
    # Create comments table
    create_comments_table = """
    CREATE TABLE IF NOT EXISTS comments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        task_id INT NOT NULL,
        user_id INT NOT NULL,
        comment TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES tasks(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """
    
    # Initialize default statuses if needed
    insert_default_statuses = """
    INSERT IGNORE INTO statuses (name, display_order)
    VALUES 
        ('To Do', 1),
        ('In Progress', 2),
        ('Review', 3),
        ('Done', 4);
    """
    
    execute_query(create_users_table)
    execute_query(create_statuses_table)
    execute_query(create_tasks_table)
    execute_query(create_comments_table)
    execute_query(insert_default_statuses)

# Authentication functions
def hash_password(password):
    """Create a SHA-256 hash of a password"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    """Verify username and password"""
    hashed_pwd = hash_password(password)
    query = "SELECT id, username, full_name, role FROM users WHERE username = %s AND password_hash = %s"
    user = execute_query(query, (username, hashed_pwd), fetch=True)
    if user and len(user) > 0:
        return user[0]
    return None

def login_page():
    """Display login page and handle authentication"""
    st.title("Edubull Task Tracker - Login")
    
    # Check if user is already authenticated
    if 'user_id' in st.session_state and st.session_state['user_id']:
        return True
    
    # Login form
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if username and password:
                user = verify_user(username, password)
                if user:
                    # Store user info in session state
                    st.session_state['user_id'] = user['id']
                    st.session_state['username'] = user['username']
                    st.session_state['full_name'] = user['full_name']
                    st.session_state['role'] = user['role']
                    st.success(f"Welcome back, {user['full_name']}!")
                    return True
                else:
                    st.error("Invalid username or password")
            else:
                st.error("Please enter both username and password")
    
    # Display registration option
    st.markdown("---")
    st.subheader("New User?")
    if st.button("Register"):
        st.session_state['show_register'] = True
    
    # Registration form
    if 'show_register' in st.session_state and st.session_state['show_register']:
        with st.form("register_form"):
            st.subheader("Create an Account")
            new_username = st.text_input("Username", key="reg_username")
            new_full_name = st.text_input("Full Name", key="reg_full_name")
            new_email = st.text_input("Email", key="reg_email")
            new_department = st.text_input("Department", key="reg_department")
            new_password = st.text_input("Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
            
            register_submitted = st.form_submit_button("Register")
            
            if register_submitted:
                if new_username and new_full_name and new_email and new_password and confirm_password:
                    if new_password == confirm_password:
                        # Check if username exists
                        check_query = "SELECT id FROM users WHERE username = %s"
                        existing_user = execute_query(check_query, (new_username,), fetch=True)
                        
                        if existing_user:
                            st.error("Username already exists. Please choose another.")
                        else:
                            # Create the new user
                            hashed_pwd = hash_password(new_password)
                            insert_query = """
                            INSERT INTO users (username, full_name, email, department, password_hash)
                            VALUES (%s, %s, %s, %s, %s)
                            """
                            success = execute_query(insert_query, (
                                new_username, new_full_name, new_email, new_department, hashed_pwd
                            ))
                            
                            if success:
                                st.success("Account created successfully! You can now log in.")
                                st.session_state['show_register'] = False
                    else:
                        st.error("Passwords do not match")
                else:
                    st.error("All fields are required")
    
    return False

# UI Components
def sidebar():
    st.sidebar.image("https://placeholder.com/150x150", width=150)  # Replace with Edubull logo
    st.sidebar.title("Edubull Task Tracker")
    
    # Show user info
    if 'full_name' in st.session_state:
        st.sidebar.markdown(f"**Logged in as:** {st.session_state['full_name']}")
        st.sidebar.markdown(f"**Role:** {st.session_state['role']}")
        
        # Check for unread notifications
        if 'user_id' in st.session_state:
            unread_count = get_unread_notification_count(st.session_state['user_id'])
            if unread_count > 0:
                st.sidebar.markdown(f"**Notifications:** {unread_count} unread")
        
        col1, col2, col3 = st.sidebar.columns(3)
        with col1:
            if st.button("Profile"):
                st.session_state['show_profile'] = True
                st.session_state['current_page'] = "User Profile"
        with col2:
            if st.button("Notifications"):
                st.session_state['show_notifications'] = True
                st.session_state['current_page'] = "Notifications"
        with col3:
            if st.button("Logout"):
                for key in ['user_id', 'username', 'full_name', 'role', 'show_profile', 'show_notifications', 'current_page']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.experimental_rerun()
    
    # Navigation items based on role and permissions
    if st.session_state.get('show_profile', False):
        menu = "User Profile"
    elif st.session_state.get('show_notifications', False):
        menu = "Notifications"
    else:
        # Get available departments for this user
        available_departments = []
        if 'user_id' in st.session_state:
            available_departments = get_user_accessible_departments(st.session_state['user_id'])
        
        # Base menu items
        menu_items = ["Dashboard", "My Tasks", "Task Board"]
        
        # Add department-specific menu items
        for dept in available_departments:
            menu_items.append(f"{dept['name']} Department")
        
        # Add additional menu items based on role
        menu_items.extend(["Create Task", "Reports", "Team Members"])
        
        if st.session_state.get('role') == 'admin':
            menu_items.append("Admin Panel")
        
        menu = st.sidebar.selectbox("Navigation", menu_items)
        st.session_state['current_page'] = menu
    
    st.sidebar.divider()
    
    # Quick filters
    st.sidebar.subheader("Quick Filters")
    priority_filter = st.sidebar.multiselect(
        "Priority",
        ["High", "Medium", "Low"]
    )
    
    assignee_filter = st.sidebar.multiselect(
        "Assignee",
        ["Me", "Unassigned"] + get_all_users_names()
    )
    
    status_filter = st.sidebar.multiselect(
        "Status",
        get_all_statuses()
    )
    
    return menu, priority_filter, assignee_filter, status_filter

def department_page(department_name):
    # Get department ID
    department = get_department_by_name(department_name)
    if not department:
        st.error(f"Department '{department_name}' not found")
        return
    
    department_id = department['id']
    
    # Check if user has permission
    if 'user_id' in st.session_state:
        has_access = check_department_access(st.session_state['user_id'], department_id)
        if not has_access:
            st.error(f"You don't have permission to access the {department_name} department")
            return
    
    st.title(f"{department_name} Department")
    
    # Department tabs
    tabs = st.tabs(["Overview", "Tasks", "Team"])
    
    with tabs[0]:
        st.subheader(f"{department_name} Overview")
        
        # Department stats
        col1, col2 = st.columns(2)
        
        with col1:
            # Tasks by status
            dept_tasks_by_status = get_tasks_by_status_for_department(department_id)
            if dept_tasks_by_status:
                fig = px.pie(dept_tasks_by_status, values='count', names='status', hole=0.4,
                            title=f"Tasks by Status in {department_name}")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"No tasks found for {department_name} department")
        
        with col2:
            # Upcoming deadlines
            st.subheader("Upcoming Deadlines")
            show_upcoming_deadlines_for_department(department_id)
    
    with tabs[1]:
        st.subheader(f"{department_name} Tasks")
        
        # Department task tabs
        task_tabs = st.tabs(["All Tasks", "To Do", "In Progress", "Review", "Done"])
        
        with task_tabs[0]:
            show_department_tasks(department_id)
        
        # Show tasks by status
        statuses = get_all_statuses_with_id()
        for i, status in enumerate(statuses):
            if i < len(task_tabs) - 1:  # Skip the "All Tasks" tab
                with task_tabs[i + 1]:
                    show_department_tasks_by_status(department_id, status['id'])
    
    with tabs[2]:
        st.subheader(f"{department_name} Team")
        
        # Show team members with access to this department
        team_members = get_department_team_members(department_id)
        if team_members:
            team_df = pd.DataFrame(team_members)
            # Remove sensitive columns
            if 'password_hash' in team_df.columns:
                team_df = team_df.drop(columns=['password_hash'])
            
            st.dataframe(team_df, use_container_width=True)
        else:
            st.info(f"No team members found for {department_name} department")

def show_department_tasks(department_id):
    query = """
    SELECT t.id, t.title, t.description, t.priority, t.deadline, s.name as status, 
           u_assignee.full_name as assignee, u_reporter.full_name as reporter
    FROM tasks t
    JOIN statuses s ON t.status_id = s.id
    LEFT JOIN users u_assignee ON t.assignee_id = u_assignee.id
    JOIN users u_reporter ON t.reporter_id = u_reporter.id
    WHERE t.department_id = %s
    ORDER BY t.deadline
    """
    tasks = execute_query(query, (department_id,), fetch=True)
    
    if tasks:
        for task in tasks:
            with st.expander(f"**{task['title']}** ({task['status']})"):
                st.markdown(f"**Priority:** {task['priority']}")
                if task['deadline']:
                    st.markdown(f"**Deadline:** {task['deadline'].strftime('%Y-%m-%d')}")
                st.markdown(f"**Assignee:** {task['assignee'] if task['assignee'] else 'Unassigned'}")
                st.markdown(f"**Reporter:** {task['reporter']}")
                
                st.markdown("---")
                st.markdown("**Description:**")
                st.markdown(task['description'] if task['description'] else "*No description provided*")
                
                # Comments section
                st.markdown("---")
                st.subheader("Comments")
                
                # Display existing comments
                comments = get_task_comments(task['id'])
                if comments:
                    for comment in comments:
                        st.markdown(f"**{comment['full_name']}** - _{comment['created_at'].strftime('%Y-%m-%d %H:%M')}_")
                        st.markdown(comment['comment'])
                        st.markdown("---")
                else:
                    st.info("No comments yet")
                
                # Add comment form
                with st.form(key=f"comment_form_{task['id']}"):
                    comment_text = st.text_area("Add a comment", key=f"comment_text_{task['id']}")
                    submit_comment = st.form_submit_button("Add Comment")
                    
                    if submit_comment and comment_text:
                        # Process @mentions
                        mentioned_users = extract_mentions(comment_text)
                        
                        # Add comment to database
                        comment_id = add_comment(task['id'], st.session_state['user_id'], comment_text)
                        
                        # Process mentions and create notifications
                        if comment_id and mentioned_users:
                            for user_id in mentioned_users:
                                # Create mention record
                                add_mention(comment_id, user_id)
                                
                                # Create notification
                                notification_content = f"{st.session_state['full_name']} mentioned you in a comment on task '{task['title']}'"
                                add_notification(user_id, notification_content, f"/task/{task['id']}")
                        
                        st.success("Comment added successfully!")
                        st.experimental_rerun()
    else:
        st.info("No tasks found for this department")

def show_department_tasks_by_status(department_id, status_id):
    query = """
    SELECT t.id, t.title, t.description, t.priority, t.deadline,
           u_assignee.full_name as assignee, u_reporter.full_name as reporter
    FROM tasks t
    LEFT JOIN users u_assignee ON t.assignee_id = u_assignee.id
    JOIN users u_reporter ON t.reporter_id = u_reporter.id
    WHERE t.department_id = %s AND t.status_id = %s
    ORDER BY t.deadline
    """
    tasks = execute_query(query, (department_id, status_id), fetch=True)
    
    if tasks:
        for task in tasks:
            with st.expander(f"**{task['title']}**"):
                st.markdown(f"**Priority:** {task['priority']}")
                if task['deadline']:
                    st.markdown(f"**Deadline:** {task['deadline'].strftime('%Y-%m-%d')}")
                st.markdown(f"**Assignee:** {task['assignee'] if task['assignee'] else 'Unassigned'}")
                st.markdown(f"**Reporter:** {task['reporter']}")
                
                # Action buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("View Details", key=f"view_{task['id']}_{status_id}"):
                        st.session_state['selected_task'] = task['id']
                        st.experimental_rerun()
                
                # If task not in final status, show "Move to Next Status" button
                status_list = get_all_statuses_with_id()
                current_status_index = next((i for i, s in enumerate(status_list) if s['id'] == status_id), None)
                
                if current_status_index is not None and current_status_index < len(status_list) - 1:
                    with col2:
                        next_status = status_list[current_status_index + 1]
                        if st.button(f"Move to {next_status['name']}", key=f"move_{task['id']}_{status_id}"):
                            # Update task status
                            update_query = """
                            UPDATE tasks
                            SET status_id = %s
                            WHERE id = %s
                            """
                            success = execute_query(update_query, (next_status['id'], task['id']))
                            
                            if success:
                                # Create notification for assignee if there is one
                                if task.get('assignee_id'):
                                    notification_content = f"Task '{task['title']}' has been moved to {next_status['name']}"
                                    add_notification(task['assignee_id'], notification_content, f"/task/{task['id']}")
                                
                                st.success(f"Task moved to {next_status['name']}")
                                st.experimental_rerun()
    else:
        st.info("No tasks found with this status")

def notifications_page():
    st.title("Notifications")
    
    if 'user_id' not in st.session_state:
        st.error("You must be logged in to view notifications")
        return
    
    # Get user notifications
    notifications = get_user_notifications(st.session_state['user_id'])
    
    # Mark all as read button
    if notifications and any(not notif['is_read'] for notif in notifications):
        if st.button("Mark All as Read"):
            mark_all_notifications_read(st.session_state['user_id'])
            st.success("All notifications marked as read")
            st.experimental_rerun()
    
    # Display notifications
    st.subheader("Your Notifications")
    
    if not notifications:
        st.info("You have no notifications")
        return
    
    # Sort by date, newest first
    notifications.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Group by date
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Today's notifications
    today_notifs = [n for n in notifications if n['created_at'].date() == today]
    if today_notifs:
        st.markdown("### Today")
        for notif in today_notifs:
            display_notification(notif)
    
    # Yesterday's notifications
    yesterday_notifs = [n for n in notifications if n['created_at'].date() == yesterday]
    if yesterday_notifs:
        st.markdown("### Yesterday")
        for notif in yesterday_notifs:
            display_notification(notif)
    
    # Older notifications
    older_notifs = [n for n in notifications if n['created_at'].date() < yesterday]
    if older_notifs:
        st.markdown("### Older")
        for notif in older_notifs:
            display_notification(notif)

def display_notification(notification):
    # Create notification UI
    col1, col2 = st.columns([0.9, 0.1])
    
    with col1:
        if not notification['is_read']:
            st.markdown(f"**🔔 {notification['content']}**")
        else:
            st.markdown(notification['content'])
        st.caption(f"{notification['created_at'].strftime('%Y-%m-%d %H:%M')}")
    
    with col2:
        if not notification['is_read']:
            if st.button("Read", key=f"read_{notification['id']}"):
                mark_notification_read(notification['id'])
                st.experimental_rerun()
    
    st.divider()

# Helper functions for departments, comments, and notifications
def get_department_by_name(name):
    query = "SELECT id, name, description FROM departments WHERE name = %s"
    result = execute_query(query, (name,), fetch=True)
    return result[0] if result else None

def check_department_access(user_id, department_id):
    query = """
    SELECT can_view
    FROM user_department_permissions
    WHERE user_id = %s AND department_id = %s AND can_view = TRUE
    """
    result = execute_query(query, (user_id, department_id), fetch=True)
    return bool(result)

def get_user_accessible_departments(user_id):
    query = """
    SELECT d.id, d.name, d.description, udp.can_edit
    FROM departments d
    JOIN user_department_permissions udp ON d.id = udp.department_id
    WHERE udp.user_id = %s AND udp.can_view = TRUE
    ORDER BY d.name
    """
    return execute_query(query, (user_id,), fetch=True) or []

def get_tasks_by_status_for_department(department_id):
    query = """
    SELECT s.name as status, COUNT(t.id) as count
    FROM tasks t
    JOIN statuses s ON t.status_id = s.id
    WHERE t.department_id = %s
    GROUP BY s.name
    ORDER BY s.display_order
    """
    return execute_query(query, (department_id,), fetch=True)

def show_upcoming_deadlines_for_department(department_id):
    query = """
    SELECT t.title, t.deadline, s.name as status, u.full_name as assignee
    FROM tasks t
    JOIN statuses s ON t.status_id = s.id
    LEFT JOIN users u ON t.assignee_id = u.id
    WHERE t.department_id = %s AND t.deadline >= CURDATE() AND t.deadline <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
    ORDER BY t.deadline
    """
    deadlines = execute_query(query, (department_id,), fetch=True)
    if deadlines:
        for task in deadlines:
            st.markdown(f"**{task['title']}** ({task['deadline'].strftime('%Y-%m-%d')})")
            st.markdown(f"Status: {task['status']} | Assignee: {task['assignee'] if task['assignee'] else 'Unassigned'}")
            st.divider()
    else:
        st.info("No upcoming deadlines for the next 7 days")

def get_department_team_members(department_id):
    query = """
    SELECT u.id, u.username, u.full_name, u.email, u.department, 
           udp.can_view, udp.can_edit
    FROM users u
    JOIN user_department_permissions udp ON u.id = udp.user_id
    WHERE udp.department_id = %s AND udp.can_view = TRUE
    ORDER BY u.full_name
    """
    return execute_query(query, (department_id,), fetch=True) or []

def get_task_comments(task_id):
    query = """
    SELECT c.id, c.comment, c.created_at, u.full_name
    FROM comments c
    JOIN users u ON c.user_id = u.id
    WHERE c.task_id = %s
    ORDER BY c.created_at
    """
    return execute_query(query, (task_id,), fetch=True) or []

def add_comment(task_id, user_id, comment):
    query = """
    INSERT INTO comments (task_id, user_id, comment)
    VALUES (%s, %s, %s)
    """
    execute_query(query, (task_id, user_id, comment))
    
    # Get the ID of the inserted comment
    get_id_query = "SELECT LAST_INSERT_ID() as id"
    result = execute_query(get_id_query, fetch=True)
    
    return result[0]['id'] if result else None

def extract_mentions(text):
    # Get all users
    all_users = get_all_users()
    username_map = {user['username']: user['id'] for user in all_users}
    
    # Simple regex to find @username mentions
    import re
    mentioned_usernames = re.findall(r'@(\w+)', text)
    
    # Map to user IDs
    mentioned_user_ids = [username_map[username] for username in mentioned_usernames if username in username_map]
    
    return mentioned_user_ids

def add_mention(comment_id, user_id):
    query = """
    INSERT INTO user_mentions (comment_id, user_id, is_read)
    VALUES (%s, %s, FALSE)
    """
    return execute_query(query, (comment_id, user_id))

def add_notification(user_id, content, link=None):
    query = """
    INSERT INTO notifications (user_id, content, link, is_read)
    VALUES (%s, %s, %s, FALSE)
    """
    return execute_query(query, (user_id, content, link))

def get_user_notifications(user_id):
    query = """
    SELECT id, content, link, is_read, created_at
    FROM notifications
    WHERE user_id = %s
    ORDER BY created_at DESC
    LIMIT 50
    """
    return execute_query(query, (user_id,), fetch=True) or []

def get_unread_notification_count(user_id):
    query = """
    SELECT COUNT(*) as count
    FROM notifications
    WHERE user_id = %s AND is_read = FALSE
    """
    result = execute_query(query, (user_id,), fetch=True)
    return result[0]['count'] if result else 0

def mark_notification_read(notification_id):
    query = """
    UPDATE notifications
    SET is_read = TRUE
    WHERE id = %s
    """
    return execute_query(query, (notification_id,))

def mark_all_notifications_read(user_id):
    query = """
    UPDATE notifications
    SET is_read = TRUE
    WHERE user_id = %s
    """
    return execute_query(query, (user_id,))

def dashboard_page():
    st.title("Dashboard")
    
    # Check if user is logged in
    if 'user_id' not in st.session_state:
        st.warning("Please log in to view your dashboard")
        return
    
    # Get user's tasks
    user_id = st.session_state['user_id']
    
    # Welcome message
    st.markdown(f"### Welcome, {st.session_state.get('full_name', 'User')}!")
    st.markdown("Here's an overview of your tasks and team progress.")
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Tasks assigned to me
        query = """
        SELECT COUNT(*) as count
        FROM tasks
        WHERE assignee_id = %s
        """
        result = execute_query(query, (user_id,), fetch=True)
        assigned_count = result[0]['count'] if result else 0
        
        st.metric(label="Tasks Assigned", value=assigned_count)
    
    with col2:
        # Tasks I've reported
        query = """
        SELECT COUNT(*) as count
        FROM tasks
        WHERE reporter_id = %s
        """
        result = execute_query(query, (user_id,), fetch=True)
        reported_count = result[0]['count'] if result else 0
        
        st.metric(label="Tasks Reported", value=reported_count)
    
    with col3:
        # Overdue tasks
        query = """
        SELECT COUNT(*) as count
        FROM tasks
        WHERE assignee_id = %s AND deadline < CURDATE() AND status_id != 
            (SELECT id FROM statuses WHERE name = 'Done' LIMIT 1)
        """
        result = execute_query(query, (user_id,), fetch=True)
        overdue_count = result[0]['count'] if result else 0
        
        st.metric(label="Overdue Tasks", value=overdue_count, delta=-overdue_count, delta_color="inverse")
    
    with col4:
        # Completed tasks this week
        query = """
        SELECT COUNT(*) as count
        FROM tasks
        WHERE assignee_id = %s 
        AND status_id = (SELECT id FROM statuses WHERE name = 'Done' LIMIT 1)
        AND updated_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        """
        result = execute_query(query, (user_id,), fetch=True)
        completed_count = result[0]['count'] if result else 0
        
        st.metric(label="Completed This Week", value=completed_count)
    
    # Charts row
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Task status chart for all my tasks
        query = """
        SELECT s.name as status, COUNT(t.id) as count
        FROM tasks t
        JOIN statuses s ON t.status_id = s.id
        WHERE t.assignee_id = %s
        GROUP BY s.name
        ORDER BY s.display_order
        """
        status_data = execute_query(query, (user_id,), fetch=True)
        
        if status_data:
            fig = px.pie(status_data, values='count', names='status', hole=0.4,
                        title="My Tasks by Status")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No tasks assigned to you yet")
    
    with col2:
        # Department distribution chart
        query = """
        SELECT d.name as department, COUNT(t.id) as count
        FROM tasks t
        JOIN departments d ON t.department_id = d.id
        WHERE t.assignee_id = %s
        GROUP BY d.name
        ORDER BY count DESC
        """
        dept_data = execute_query(query, (user_id,), fetch=True)
        
        if dept_data:
            fig = px.bar(dept_data, x='department', y='count', 
                        title="My Tasks by Department",
                        color='department')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No department-specific tasks assigned to you yet")
    
    # Recent activity and upcoming deadlines
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Recent Activity")
        
        # Get recent tasks and comments
        query = """
        (SELECT 'task' as type, t.id, t.title as content, t.created_at, u.full_name as user
         FROM tasks t
         JOIN users u ON t.reporter_id = u.id
         WHERE t.assignee_id = %s OR t.reporter_id = %s)
        UNION
        (SELECT 'comment' as type, t.id, c.comment as content, c.created_at, u.full_name as user
         FROM comments c
         JOIN tasks t ON c.task_id = t.id
         JOIN users u ON c.user_id = u.id
         WHERE t.assignee_id = %s OR c.user_id = %s)
        ORDER BY created_at DESC
        LIMIT 10
        """
        activity = execute_query(query, (user_id, user_id, user_id, user_id), fetch=True)
        
        if activity:
            for item in activity:
                if item['type'] == 'task':
                    st.markdown(f"**New Task:** {item['content']}")
                else:
                    st.markdown(f"**New Comment:** {item['content'][:50]}...")
                st.caption(f"By {item['user']} on {item['created_at'].strftime('%Y-%m-%d %H:%M')}")
                st.divider()
        else:
            st.info("No recent activity")
    
    with col2:
        st.subheader("Upcoming Deadlines")
        
        # Get tasks with upcoming deadlines
        query = """
        SELECT t.id, t.title, t.deadline, s.name as status
        FROM tasks t
        JOIN statuses s ON t.status_id = s.id
        WHERE t.assignee_id = %s 
        AND t.deadline >= CURDATE() 
        AND t.deadline <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
        AND t.status_id != (SELECT id FROM statuses WHERE name = 'Done' LIMIT 1)
        ORDER BY t.deadline
        """
        deadlines = execute_query(query, (user_id,), fetch=True)
        
        if deadlines:
            for task in deadlines:
                days_remaining = (task['deadline'] - datetime.now().date()).days
                st.markdown(f"**{task['title']}** ({task['status']})")
                
                if days_remaining <= 0:
                    st.markdown("**Due: TODAY!**")
                else:
                    st.markdown(f"**Due:** {task['deadline'].strftime('%Y-%m-%d')} ({days_remaining} days)")
                st.divider()
        else:
            st.info("No upcoming deadlines for the next 7 days")

def my_tasks_page():
    st.title("My Tasks")
    
    tabs = st.tabs(["Assigned to Me", "Created by Me", "All Tasks"])
    
    with tabs[0]:
        show_assigned_tasks()
    
    with tabs[1]:
        show_created_tasks()
    
    with tabs[2]:
        show_all_tasks()

def create_task_page():
    st.title("Create New Task")
    
    # Create form for task creation
    with st.form("task_form"):
        # Task details
        title = st.text_input("Task Title")
        description = st.text_area("Description")
        
        # Task meta
        col1, col2 = st.columns(2)
        with col1:
            priority = st.selectbox("Priority", ["Low", "Medium", "High"])
            deadline = st.date_input("Deadline")
        with col2:
            # Get all users for assignee dropdown
            users = get_all_users()
            user_options = [(u['id'], u['full_name']) for u in users]
            user_options.insert(0, (None, "Unassigned"))
            
            assignee = st.selectbox(
                "Assignee",
                options=[u[0] for u in user_options],
                format_func=lambda x: next((u[1] for u in user_options if u[0] == x), "Unknown")
            )
            
            # Get all statuses for status dropdown
            statuses = get_all_statuses_with_id()
            status = st.selectbox(
                "Status",
                options=[s['id'] for s in statuses],
                format_func=lambda x: next((s['name'] for s in statuses if s['id'] == x), "Unknown")
            )
        
        # Department selection
        departments = get_all_departments()
        if departments:
            department = st.selectbox(
                "Department",
                options=[d['id'] for d in departments],
                format_func=lambda x: next((d['name'] for d in departments if d['id'] == x), "General")
            )
        else:
            st.warning("No departments found. Please contact an administrator.")
            department = None
        
        # Tags/Labels
        tags = st.text_input("Tags (comma separated)")
        
        # Add attachments placeholder (for future implementation)
        # attachments = st.file_uploader("Attachments", accept_multiple_files=True)
        
        submitted = st.form_submit_button("Create Task")
        
        if submitted:
            if not title:
                st.error("Task title is required")
            else:
                # Process tags
                tag_list = [tag.strip() for tag in tags.split(',')] if tags else []
                
                # Insert task into database
                query = """
                INSERT INTO tasks 
                (title, description, priority, deadline, assignee_id, reporter_id, status_id, department_id, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """
                
                # Convert empty assignee to None
                assignee_id = assignee if assignee else None
                
                task_data = (
                    title, 
                    description, 
                    priority, 
                    deadline,
                    assignee_id,
                    st.session_state.get('user_id'),  # Current user as reporter
                    status,
                    department
                )
                
                # Execute query and handle response
                success = execute_query(query, task_data)
                
                if success:
                    # If task creation was successful, get the task ID
                    task_id_query = "SELECT LAST_INSERT_ID() as id"
                    result = execute_query(task_id_query, fetch=True)
                    
                    if result and result[0]['id']:
                        task_id = result[0]['id']
                        
                        # Add tags if any
                        for tag in tag_list:
                            if tag:
                                # Insert tag if it doesn't exist
                                tag_query = """
                                INSERT INTO tags (name) 
                                VALUES (%s)
                                ON DUPLICATE KEY UPDATE id=id
                                """
                                execute_query(tag_query, (tag,))
                                
                                # Get tag ID
                                tag_id_query = "SELECT id FROM tags WHERE name = %s"
                                tag_result = execute_query(tag_id_query, (tag,), fetch=True)
                                
                                if tag_result and tag_result[0]['id']:
                                    # Link tag to task
                                    link_query = """
                                    INSERT INTO task_tags (task_id, tag_id)
                                    VALUES (%s, %s)
                                    """
                                    execute_query(link_query, (task_id, tag_result[0]['id']))
                        
                        # Notify assignee if assigned
                        if assignee_id:
                            notification_content = f"You have been assigned to task '{title}'"
                            add_notification(assignee_id, notification_content, f"/task/{task_id}")
                        
                        st.success("Task created successfully!")
                        # Clear form after successful submission
                        st.experimental_rerun()
                    else:
                        st.error("Failed to get task ID after creation")
                else:
                    st.error("Failed to create task. Please try again.")

def task_board_page():
    st.title("Task Board")
    
    # Get all statuses for column headers
    statuses = get_all_statuses_with_id()
    if not statuses:
        st.error("No task statuses found in the database")
        return
    
    # Filters
    with st.expander("Filters", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            priority_filter = st.multiselect(
                "Priority",
                ["High", "Medium", "Low"]
            )
        
        with col2:
            # Get all users for assignee filter
            users = get_all_users()
            user_options = ["Unassigned"] + [u['full_name'] for u in users]
            assignee_filter = st.multiselect(
                "Assignee",
                user_options
            )
        
        with col3:
            # Department filter
            departments = get_all_departments()
            dept_options = [d['name'] for d in departments]
            department_filter = st.multiselect(
                "Department",
                dept_options
            )
        
        # Tag filter
        tags = get_all_tags()
        tag_options = [t['name'] for t in tags]
        tag_filter = st.multiselect(
            "Tags",
            tag_options
        )
        
        # Apply filters button
        apply_filters = st.button("Apply Filters")
    
    # Create tabs for different views
    tab1, tab2 = st.tabs(["Board View", "List View"])
    
    with tab1:
        # Prepare the Kanban board columns
        columns = st.columns(len(statuses))
        
        # Build the filter conditions
        conditions = []
        params = []
        
        if priority_filter:
            placeholders = ', '.join(['%s'] * len(priority_filter))
            conditions.append(f"t.priority IN ({placeholders})")
            params.extend(priority_filter)
        
        if assignee_filter:
            if "Unassigned" in assignee_filter:
                other_assignees = [a for a in assignee_filter if a != "Unassigned"]
                if other_assignees:
                    placeholders = ', '.join(['%s'] * len(other_assignees))
                    conditions.append(f"(t.assignee_id IS NULL OR u_assignee.full_name IN ({placeholders}))")
                    params.extend(other_assignees)
                else:
                    conditions.append("t.assignee_id IS NULL")
            else:
                placeholders = ', '.join(['%s'] * len(assignee_filter))
                conditions.append(f"u_assignee.full_name IN ({placeholders})")
                params.extend(assignee_filter)
        
        if department_filter:
            placeholders = ', '.join(['%s'] * len(department_filter))
            conditions.append(f"d.name IN ({placeholders})")
            params.extend(department_filter)
        
        if tag_filter:
            # This requires a JOIN with the tag tables
            has_tag_join = True
            placeholders = ', '.join(['%s'] * len(tag_filter))
            conditions.append(f"tag.name IN ({placeholders})")
            params.extend(tag_filter)
        else:
            has_tag_join = False
        
        # Display each status column
        for i, status in enumerate(statuses):
            with columns[i]:
                st.subheader(status['name'])
                
                # Build query for tasks with this status
                base_query = """
                SELECT t.id, t.title, t.description, t.priority, t.deadline, 
                       u_assignee.full_name as assignee, u_reporter.full_name as reporter,
                       d.name as department
                FROM tasks t
                JOIN statuses s ON t.status_id = s.id
                LEFT JOIN users u_assignee ON t.assignee_id = u_assignee.id
                JOIN users u_reporter ON t.reporter_id = u_reporter.id
                JOIN departments d ON t.department_id = d.id
                """
                
                if has_tag_join:
                    base_query += """
                    LEFT JOIN task_tags tt ON t.id = tt.task_id
                    LEFT JOIN tags tag ON tt.tag_id = tag.id
                    """
                
                # Add status condition
                status_condition = "t.status_id = %s"
                conditions.append(status_condition)
                params.append(status['id'])
                
                # Combine all conditions
                where_clause = " WHERE " + " AND ".join(conditions)
                
                # Group by to avoid duplicates from tag join
                group_by = " GROUP BY t.id"
                
                # Order by
                order_by = " ORDER BY t.priority DESC, t.deadline ASC"
                
                # Final query
                query = base_query + where_clause + group_by + order_by
                
                # Execute query
                tasks = execute_query(query, params, fetch=True)
                
                # Remove the status condition for the next column
                conditions.pop()
                params.pop()
                
                # Display tasks
                if tasks:
                    for task in tasks:
                        with st.container():
                            st.markdown(f"**{task['title']}**")
                            
                            # Color-coded priority label
                            if task['priority'] == 'High':
                                st.markdown("🔴 **High**")
                            elif task['priority'] == 'Medium':
                                st.markdown("🟠 **Medium**")
                            else:
                                st.markdown("🟢 **Low**")
                            
                            st.markdown(f"**Dept:** {task['department']}")
                            
                            if task['assignee']:
                                st.markdown(f"**Assignee:** {task['assignee']}")
                            else:
                                st.markdown("**Assignee:** Unassigned")
                            
                            if task['deadline']:
                                days_remaining = (task['deadline'] - datetime.now().date()).days
                                if days_remaining < 0:
                                    st.markdown(f"**Deadline:** :red[{task['deadline'].strftime('%Y-%m-%d')}] (Overdue)")
                                elif days_remaining == 0:
                                    st.markdown(f"**Deadline:** :orange[{task['deadline'].strftime('%Y-%m-%d')}] (Today)")
                                else:
                                    st.markdown(f"**Deadline:** {task['deadline'].strftime('%Y-%m-%d')}")
                            
                            # Task actions
                            if st.button("View Details", key=f"view_{task['id']}_{status['id']}"):
                                st.session_state['selected_task'] = task['id']
                                st.experimental_rerun()
                            
                            st.divider()
                else:
                    st.info(f"No tasks in {status['name']}")
    
    with tab2:
        # Build query for list view (similar to board view but without status filtering)
        base_query = """
        SELECT t.id, t.title, s.name as status, t.priority, t.deadline, 
               u_assignee.full_name as assignee, u_reporter.full_name as reporter,
               d.name as department
        FROM tasks t
        JOIN statuses s ON t.status_id = s.id
        LEFT JOIN users u_assignee ON t.assignee_id = u_assignee.id
        JOIN users u_reporter ON t.reporter_id = u_reporter.id
        JOIN departments d ON t.department_id = d.id
        """
        
        if has_tag_join:
            base_query += """
            LEFT JOIN task_tags tt ON t.id = tt.task_id
            LEFT JOIN tags tag ON tt.tag_id = tag.id
            """
        
        # Remove the status condition if it was added in the board view
        list_conditions = [c for c in conditions if "t.status_id" not in c]
        list_params = [p for i, p in enumerate(params) if "t.status_id" not in conditions[i]] if conditions else []
        
        # Combine all conditions
        where_clause = " WHERE " + " AND ".join(list_conditions) if list_conditions else ""
        
        # Group by to avoid duplicates from tag join
        group_by = " GROUP BY t.id"
        
        # Order by
        order_by = " ORDER BY s.display_order, t.priority DESC, t.deadline ASC"
        
        # Final query
        query = base_query + where_clause + group_by + order_by
        
        # Execute query
        tasks = execute_query(query, list_params, fetch=True) if list_params else execute_query(query, fetch=True)
        
        # Display tasks in a table
        if tasks:
            # Convert to DataFrame for display
            df = pd.DataFrame(tasks)
            
            # Format deadline
            if 'deadline' in df.columns:
                df['deadline'] = df['deadline'].apply(lambda x: x.strftime('%Y-%m-%d') if x else '')
            
            # Add action column
            st.dataframe(df, use_container_width=True)
            
            # Action for selected row
            selected_indices = st.multiselect('Select rows:', df.index)
            if selected_indices:
                selected_task = df.iloc[selected_indices[0]]
                st.session_state['selected_task'] = selected_task['id']
                st.experimental_rerun()
        else:
            st.info("No tasks match the selected filters")

def get_all_tags():
    query = "SELECT id, name FROM tags ORDER BY name"
    return execute_query(query, fetch=True) or []

def reports_page():
    st.title("Reports")
    
    report_type = st.selectbox(
        "Report Type",
        ["Tasks by Status", "Tasks by Priority", "Overdue Tasks", "Task Completion Time"]
    )
    
    if report_type == "Tasks by Status":
        tasks_by_status = get_tasks_by_status()
        if tasks_by_status:
            fig = px.pie(tasks_by_status, values='count', names='status')
            st.plotly_chart(fig, use_container_width=True)
    
    elif report_type == "Tasks by Priority":
        tasks_by_priority = get_tasks_by_priority()
        if tasks_by_priority:
            fig = px.bar(tasks_by_priority, x='priority', y='count')
            st.plotly_chart(fig, use_container_width=True)
    
    elif report_type == "Overdue Tasks":
        overdue_tasks = get_overdue_tasks()
        if overdue_tasks:
            st.dataframe(overdue_tasks)
    
    elif report_type == "Task Completion Time":
        completion_data = get_task_completion_time()
        if completion_data:
            fig = px.box(completion_data, x='priority', y='days_to_complete')
            st.plotly_chart(fig, use_container_width=True)

def team_members_page():
    st.title("Team Members")
    
    tab1, tab2, tab3 = st.tabs(["View Team", "Add Team Member", "Bulk Add Members"])
    
    with tab1:
        team_members = get_all_users()
        if team_members:
            # Exclude admin users from regular view if not an admin
            if st.session_state.get('role') != 'admin':
                team_members = [member for member in team_members if member.get('role') != 'admin']
            
            st.dataframe(pd.DataFrame(team_members), use_container_width=True)
        else:
            st.info("No team members found")
    
    with tab2:
        with st.form("add_team_member_form"):
            username = st.text_input("Username")
            full_name = st.text_input("Full Name")
            email = st.text_input("Email")
            department = st.text_input("Department")
            
            submitted = st.form_submit_button("Add Team Member")
            
            if submitted:
                if username and full_name and email:
                    initial_password = add_team_member(username, full_name, email, department)
                    if initial_password:
                        st.success("Team member added successfully!")
                        st.info(f"""
                        **Initial Password**: `{initial_password}`
                        
                        Please share this with the team member and ask them to change it after first login.
                        """)
                else:
                    st.error("Username, full name, and email are required")
    
    with tab3:
        st.subheader("Bulk Add Team Members")
        
        # Only admins can use the bulk upload feature
        if st.session_state.get('role') != 'admin':
            st.warning("You need admin privileges to use bulk upload.")
        else:
            st.markdown("""
            Upload a CSV file with the following columns:
            - username
            - full_name
            - email
            - department (optional)
            
            You can also download a template below.
            """)
            
            # CSV Template download
            template_data = pd.DataFrame({
                'username': ['john_doe', 'jane_smith'],
                'full_name': ['John Doe', 'Jane Smith'],
                'email': ['john@edubull.com', 'jane@edubull.com'],
                'department': ['Engineering', 'Marketing'],
            })
            
            csv = template_data.to_csv(index=False)
            st.download_button(
                label="Download CSV Template",
                data=csv,
                file_name="team_members_template.csv",
                mime="text/csv"
            )
            
            # File uploader
            uploaded_file = st.file_uploader("Upload CSV file", type="csv")
            
            if uploaded_file is not None:
                data = pd.read_csv(uploaded_file)
                
                # Validate required columns
                required_columns = ['username', 'full_name', 'email']
                if not all(col in data.columns for col in required_columns):
                    st.error(f"CSV must contain the following columns: {', '.join(required_columns)}")
                else:
                    # Add department column if missing
                    if 'department' not in data.columns:
                        data['department'] = ""
                    
                    # Display preview
                    st.subheader("Preview")
                    st.dataframe(data, use_container_width=True)
                    
                    # Process bulk upload
                    if st.button("Process Bulk Upload"):
                        results = []
                        success_count = 0
                        error_count = 0
                        
                        for _, row in data.iterrows():
                            # Check if user already exists
                            check_query = "SELECT id FROM users WHERE username = %s"
                            existing_user = execute_query(check_query, (row['username'],), fetch=True)
                            
                            if existing_user:
                                results.append({
                                    'username': row['username'],
                                    'status': 'Error',
                                    'message': 'Username already exists',
                                    'password': ''
                                })
                                error_count += 1
                            else:
                                initial_password = add_team_member(
                                    row['username'], 
                                    row['full_name'], 
                                    row['email'], 
                                    row['department']
                                )
                                
                                if initial_password:
                                    results.append({
                                        'username': row['username'],
                                        'status': 'Success',
                                        'message': 'User created',
                                        'password': initial_password
                                    })
                                    success_count += 1
                                else:
                                    results.append({
                                        'username': row['username'],
                                        'status': 'Error',
                                        'message': 'Failed to create user',
                                        'password': ''
                                    })
                                    error_count += 1
                        
                        # Show results
                        st.success(f"Processed {len(data)} users: {success_count} successes, {error_count} errors")
                        st.dataframe(pd.DataFrame(results), use_container_width=True)
                        
                        # Provide download of results including passwords
                        results_csv = pd.DataFrame(results).to_csv(index=False)
                        st.download_button(
                            label="Download Results with Passwords",
                            data=results_csv,
                            file_name="user_creation_results.csv",
                            mime="text/csv"
                        )
                        st.warning("**Important**: This file contains initial passwords. Make sure to distribute them securely!")

def admin_panel_page():
    st.title("Admin Panel")
    
    # Check if user is admin
    if st.session_state.get('role') != 'admin':
        st.error("You don't have permission to access this page.")
        return
    
    tabs = st.tabs(["User Management", "Department Permissions", "System Settings"])
    
    # User Management Tab
    with tabs[0]:
        st.subheader("User Management")
        user_tabs = st.tabs(["View Users", "Add Users", "Edit Users"])
        
        with user_tabs[0]:
            st.subheader("All Users")
            users = get_all_users_with_roles()
            if users:
                users_df = pd.DataFrame(users)
                # Don't show password hash in the view
                if 'password_hash' in users_df.columns:
                    users_df = users_df.drop(columns=['password_hash'])
                st.dataframe(users_df, use_container_width=True)
            else:
                st.info("No users found")
        
        with user_tabs[1]:
            st.subheader("Add New User")
            
            with st.form("add_user_form"):
                new_username = st.text_input("Username")
                new_full_name = st.text_input("Full Name")
                new_email = st.text_input("Email")
                new_department = st.text_input("Department")
                new_role = st.selectbox("Role", ["user", "admin"])
                new_password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                
                add_user_submitted = st.form_submit_button("Add User")
                
                if add_user_submitted:
                    if all([new_username, new_full_name, new_email, new_password, confirm_password]):
                        if new_password == confirm_password:
                            # Check if username exists
                            check_query = "SELECT id FROM users WHERE username = %s"
                            existing_user = execute_query(check_query, (new_username,), fetch=True)
                            
                            if existing_user:
                                st.error("Username already exists. Please choose another.")
                            else:
                                # Create the new user
                                hashed_pwd = hash_password(new_password)
                                insert_query = """
                                INSERT INTO users (username, full_name, email, department, password_hash, role)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                """
                                success = execute_query(insert_query, (
                                    new_username, new_full_name, new_email, new_department, hashed_pwd, new_role
                                ))
                                
                                if success:
                                    st.success(f"User '{new_username}' created successfully!")
                        else:
                            st.error("Passwords do not match")
                    else:
                        st.error("All fields are required")
        
        with user_tabs[2]:
            st.subheader("Edit User")
            
            # Get list of users
            users = get_all_users_with_roles()
            
            if users:
                # Select user to edit
                usernames = [user['username'] for user in users]
                selected_username = st.selectbox("Select User to Edit", usernames)
                
                # Get selected user details
                selected_user = next((user for user in users if user['username'] == selected_username), None)
                
                if selected_user:
                    with st.form("edit_user_form"):
                        edit_full_name = st.text_input("Full Name", value=selected_user['full_name'])
                        edit_email = st.text_input("Email", value=selected_user['email'])
                        edit_department = st.text_input("Department", value=selected_user['department'] or "")
                        edit_role = st.selectbox("Role", ["user", "admin"], index=0 if selected_user['role'] == "user" else 1)
                        
                        change_password = st.checkbox("Change Password")
                        
                        edit_password = st.text_input("New Password", type="password", disabled=not change_password)
                        edit_confirm_password = st.text_input("Confirm New Password", type="password", disabled=not change_password)
                        
                        edit_user_submitted = st.form_submit_button("Update User")
                        
                        if edit_user_submitted:
                            if edit_full_name and edit_email:
                                # Update user details
                                update_query = """
                                UPDATE users 
                                SET full_name = %s, email = %s, department = %s, role = %s
                                WHERE username = %s
                                """
                                
                                params = (edit_full_name, edit_email, edit_department, edit_role, selected_username)
                                
                                # If changing password, update that too
                                if change_password:
                                    if edit_password and edit_confirm_password:
                                        if edit_password == edit_confirm_password:
                                            hashed_pwd = hash_password(edit_password)
                                            update_query = """
                                            UPDATE users 
                                            SET full_name = %s, email = %s, department = %s, role = %s, password_hash = %s
                                            WHERE username = %s
                                            """
                                            params = (edit_full_name, edit_email, edit_department, edit_role, hashed_pwd, selected_username)
                                        else:
                                            st.error("Passwords do not match")
                                            return
                                    else:
                                        st.error("Please enter and confirm the new password")
                                        return
                                
                                success = execute_query(update_query, params)
                                
                                if success:
                                    st.success(f"User '{selected_username}' updated successfully!")
                            else:
                                st.error("Full Name and Email are required")
            else:
                st.info("No users found")
    
    # Department Permissions Tab
    with tabs[1]:
        st.subheader("Department Permissions")
        
        # Get all users and departments
        users = get_all_users()
        departments = get_all_departments()
        
        if not users or not departments:
            st.warning("Users or departments not found.")
            return
        
        # User selection
        selected_user = st.selectbox(
            "Select User", 
            options=[f"{user['username']} ({user['full_name']})" for user in users],
            format_func=lambda x: x
        )
        
        if selected_user:
            # Extract username from selection
            username = selected_user.split(" (")[0]
            
            # Get user ID
            user_id = next((user['id'] for user in users if user['username'] == username), None)
            
            if user_id:
                # Get current permissions
                current_permissions = get_user_department_permissions(user_id)
                
                st.subheader(f"Permissions for {selected_user}")
                
                # Create form for permission updates
                with st.form("update_permissions_form"):
                    # Create a DataFrame to display current permissions with checkboxes
                    permissions_data = []
                    
                    for dept in departments:
                        # Find existing permission or set defaults
                        perm = next((p for p in current_permissions if p['department_id'] == dept['id']), None)
                        
                        can_view = st.checkbox(
                            f"Can view {dept['name']}", 
                            value=perm['can_view'] if perm else False,
                            key=f"view_{dept['id']}"
                        )
                        
                        can_edit = st.checkbox(
                            f"Can edit {dept['name']}", 
                            value=perm['can_edit'] if perm else False,
                            key=f"edit_{dept['id']}"
                        )
                        
                        permissions_data.append({
                            'department_id': dept['id'],
                            'department_name': dept['name'],
                            'can_view': can_view,
                            'can_edit': can_edit
                        })
                    
                    update_submitted = st.form_submit_button("Update Permissions")
                    
                    if update_submitted:
                        success_count = 0
                        for perm in permissions_data:
                            # Check if permission already exists
                            check_query = """
                            SELECT id FROM user_department_permissions 
                            WHERE user_id = %s AND department_id = %s
                            """
                            existing_perm = execute_query(check_query, (user_id, perm['department_id']), fetch=True)
                            
                            if existing_perm:
                                # Update existing permission
                                update_query = """
                                UPDATE user_department_permissions 
                                SET can_view = %s, can_edit = %s 
                                WHERE user_id = %s AND department_id = %s
                                """
                                result = execute_query(update_query, (
                                    perm['can_view'], 
                                    perm['can_edit'], 
                                    user_id, 
                                    perm['department_id']
                                ))
                            else:
                                # Insert new permission
                                insert_query = """
                                INSERT INTO user_department_permissions 
                                (user_id, department_id, can_view, can_edit) 
                                VALUES (%s, %s, %s, %s)
                                """
                                result = execute_query(insert_query, (
                                    user_id, 
                                    perm['department_id'], 
                                    perm['can_view'], 
                                    perm['can_edit']
                                ))
                            
                            if result:
                                success_count += 1
                        
                        if success_count == len(permissions_data):
                            st.success(f"Permissions updated successfully for {selected_user}")
                        else:
                            st.warning(f"Some permissions could not be updated. {success_count} of {len(permissions_data)} updated.")
    
    # System Settings Tab  
    with tabs[2]:
        st.subheader("System Settings")
        st.info("System settings functionality will be implemented in a future update.")

# Helper functions for data retrieval and manipulation
def get_all_users_names():
    query = "SELECT full_name FROM users ORDER BY full_name"
    result = execute_query(query, fetch=True)
    return [user['full_name'] for user in result] if result else []

def get_all_users():
    query = "SELECT id, username, full_name, email, department, created_at FROM users ORDER BY full_name"
    return execute_query(query, fetch=True)

def get_all_statuses():
    query = "SELECT name FROM statuses ORDER BY display_order"
    result = execute_query(query, fetch=True)
    return [status['name'] for status in result] if result else []

def get_all_statuses_with_id():
    query = "SELECT id, name FROM statuses ORDER BY display_order"
    return execute_query(query, fetch=True) or []

def get_tasks_by_status():
    query = """
    SELECT s.name as status, COUNT(t.id) as count
    FROM tasks t
    JOIN statuses s ON t.status_id = s.id
    GROUP BY s.name
    ORDER BY s.display_order
    """
    return execute_query(query, fetch=True)

def get_tasks_by_priority():
    query = """
    SELECT priority, COUNT(id) as count
    FROM tasks
    GROUP BY priority
    ORDER BY FIELD(priority, 'High', 'Medium', 'Low')
    """
    return execute_query(query, fetch=True)

def get_tasks_by_status_id(status_id):
    query = """
    SELECT t.id, t.title, t.description, t.priority, t.deadline, u.full_name as assignee_name
    FROM tasks t
    LEFT JOIN users u ON t.assignee_id = u.id
    WHERE t.status_id = %s
    """
    return execute_query(query, (status_id,), fetch=True) or []

def show_upcoming_deadlines():
    query = """
    SELECT t.title, t.deadline, s.name as status, u.full_name as assignee
    FROM tasks t
    JOIN statuses s ON t.status_id = s.id
    LEFT JOIN users u ON t.assignee_id = u.id
    WHERE t.deadline >= CURDATE() AND t.deadline <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
    ORDER BY t.deadline
    """
    deadlines = execute_query(query, fetch=True)
    if deadlines:
        for task in deadlines:
            st.markdown(f"**{task['title']}** ({task['deadline'].strftime('%Y-%m-%d')})")
            st.markdown(f"Status: {task['status']} | Assignee: {task['assignee'] if task['assignee'] else 'Unassigned'}")
            st.divider()
    else:
        st.info("No upcoming deadlines for the next 7 days")

def show_recent_activity():
    query = """
    SELECT t.title, u.full_name as user, 
           CASE 
               WHEN t.created_at = t.updated_at THEN 'created'
               ELSE 'updated'
           END as action,
           t.updated_at as timestamp
    FROM tasks t
    JOIN users u ON t.reporter_id = u.id
    ORDER BY t.updated_at DESC
    LIMIT 5
    """
    activities = execute_query(query, fetch=True)
    if activities:
        for activity in activities:
            st.markdown(f"**{activity['user']}** {activity['action']} task **{activity['title']}**")
            st.markdown(f"_{activity['timestamp'].strftime('%Y-%m-%d %H:%M')}_")
            st.divider()
    else:
        st.info("No recent activity")

def show_assigned_tasks():
    # Use authenticated user from session
    query = """
    SELECT t.id, t.title, t.description, t.priority, t.deadline, s.name as status
    FROM tasks t
    JOIN statuses s ON t.status_id = s.id
    JOIN users u ON t.assignee_id = u.id
    WHERE u.id = %s
    ORDER BY t.deadline
    """
    # Use the logged-in user's ID
    user_id = st.session_state.get('user_id', 0)
    tasks = execute_query(query, (user_id,), fetch=True)
    if tasks:
        for task in tasks:
            st.markdown(f"**{task['title']}**")
            st.markdown(f"Status: {task['status']} | Priority: {task['priority']}")
            if task['deadline']:
                st.markdown(f"Deadline: {task['deadline'].strftime('%Y-%m-%d')}")
            st.markdown(task['description'])
            st.divider()
    else:
        st.info("No tasks assigned to you")

def show_created_tasks():
    # Use authenticated user from session
    query = """
    SELECT t.id, t.title, t.description, t.priority, t.deadline, s.name as status, 
           u.full_name as assignee
    FROM tasks t
    JOIN statuses s ON t.status_id = s.id
    LEFT JOIN users u ON t.assignee_id = u.id
    WHERE t.reporter_id = %s
    ORDER BY t.deadline
    """
    # Use the logged-in user's ID
    user_id = st.session_state.get('user_id', 0)
    tasks = execute_query(query, (user_id,), fetch=True)
    if tasks:
        for task in tasks:
            st.markdown(f"**{task['title']}**")
            st.markdown(f"Status: {task['status']} | Priority: {task['priority']}")
            st.markdown(f"Assignee: {task['assignee'] if task['assignee'] else 'Unassigned'}")
            if task['deadline']:
                st.markdown(f"Deadline: {task['deadline'].strftime('%Y-%m-%d')}")
            st.divider()
    else:
        st.info("No tasks created by you")

def show_all_tasks():
    query = """
    SELECT t.id, t.title, t.priority, t.deadline, s.name as status, 
           u_assignee.full_name as assignee, u_reporter.full_name as reporter
    FROM tasks t
    JOIN statuses s ON t.status_id = s.id
    LEFT JOIN users u_assignee ON t.assignee_id = u_assignee.id
    JOIN users u_reporter ON t.reporter_id = u_reporter.id
    ORDER BY t.deadline
    """
    tasks = execute_query(query, fetch=True)
    if tasks:
        task_df = pd.DataFrame(tasks)
        st.dataframe(task_df, use_container_width=True)
    else:
        st.info("No tasks found")

def get_overdue_tasks():
    query = """
    SELECT t.id, t.title, t.priority, t.deadline, DATEDIFF(CURDATE(), t.deadline) as days_overdue,
           s.name as status, u.full_name as assignee
    FROM tasks t
    JOIN statuses s ON t.status_id = s.id
    LEFT JOIN users u ON t.assignee_id = u.id
    WHERE t.deadline < CURDATE() AND s.name != 'Done'
    ORDER BY t.deadline
    """
    return execute_query(query, fetch=True)

def get_task_completion_time():
    query = """
    SELECT t.priority, DATEDIFF(t.updated_at, t.created_at) as days_to_complete
    FROM tasks t
    JOIN statuses s ON t.status_id = s.id
    WHERE s.name = 'Done'
    """
    return execute_query(query, fetch=True)

def create_new_task(title, description, priority, status, assignee, deadline):
    # Get status ID
    status_query = "SELECT id FROM statuses WHERE name = %s"
    status_result = execute_query(status_query, (status,), fetch=True)
    
    if not status_result:
        st.error(f"Status '{status}' not found")
        return False
    
    status_id = status_result[0]['id']
    
    # Get assignee ID if not Unassigned
    assignee_id = None
    if assignee != "Unassigned":
        assignee_query = "SELECT id FROM users WHERE full_name = %s"
        assignee_result = execute_query(assignee_query, (assignee,), fetch=True)
        if assignee_result:
            assignee_id = assignee_result[0]['id']
    
    # Get reporter ID from session state
    reporter_id = st.session_state.get('user_id')
    
    if not reporter_id:
        st.error("You must be logged in to create tasks")
        return False
    
    # Insert the task
    insert_query = """
    INSERT INTO tasks (title, description, assignee_id, reporter_id, status_id, priority, deadline)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    
    return execute_query(insert_query, (
        title, description, assignee_id, reporter_id, status_id, priority, deadline
    ))

def add_team_member(username, full_name, email, department):
    query = """
    INSERT INTO users (username, full_name, email, department, password_hash)
    VALUES (%s, %s, %s, %s, %s)
    """
    # Generate a random initial password
    random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    hashed_pwd = hash_password(random_password)
    
    success = execute_query(query, (username, full_name, email, department, hashed_pwd))
    
    if success:
        return random_password
    return None

def get_all_users_with_roles():
    query = "SELECT id, username, full_name, email, department, role, created_at FROM users ORDER BY full_name"
    return execute_query(query, fetch=True)

def get_all_departments():
    query = "SELECT id, name, description FROM departments ORDER BY name"
    return execute_query(query, fetch=True) or []

def get_user_department_permissions(user_id):
    query = """
    SELECT udp.id, udp.department_id, d.name as department_name, udp.can_view, udp.can_edit
    FROM user_department_permissions udp
    JOIN departments d ON udp.department_id = d.id
    WHERE udp.user_id = %s
    """
    return execute_query(query, (user_id,), fetch=True) or []

def user_profile_page():
    st.title("User Profile")
    
    if 'user_id' not in st.session_state:
        st.error("You must be logged in to view your profile.")
        return
    
    # Get current user information
    query = """
    SELECT id, username, full_name, email, department, role, created_at
    FROM users
    WHERE id = %s
    """
    user_data = execute_query(query, (st.session_state['user_id'],), fetch=True)
    
    if not user_data:
        st.error("Could not retrieve user information.")
        return
    
    user = user_data[0]
    
    # Profile Tabs
    profile_tabs = st.tabs(["Profile Information", "Change Password", "Department Access", "Notification Settings"])
    
    with profile_tabs[0]:
        # Profile Information
        col1, col2 = st.columns([1, 3])
        
        with col1:
            # Avatar - use hashlib to generate a unique identicon URL from username
            username_hash = hashlib.md5(user['username'].encode()).hexdigest()
            avatar_url = f"https://www.gravatar.com/avatar/{username_hash}?s=200&d=identicon"
            st.image(avatar_url, width=150)
            
            # Avatar upload placeholder (for future implementation)
            st.caption("Profile Image")
            # file_uploader = st.file_uploader("Upload new avatar", type=["jpg", "jpeg", "png"])
        
        with col2:
            st.subheader("Basic Information")
            st.markdown(f"**Username:** {user['username']}")
            st.markdown(f"**Full Name:** {user['full_name']}")
            st.markdown(f"**Email:** {user['email']}")
            st.markdown(f"**Department:** {user['department']}")
            st.markdown(f"**Role:** {user['role']}")
            st.markdown(f"**Member Since:** {user['created_at'].strftime('%Y-%m-%d')}")
        
        # User statistics
        st.subheader("Your Activity")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Total tasks assigned
            query = """
            SELECT COUNT(*) as count
            FROM tasks
            WHERE assignee_id = %s
            """
            result = execute_query(query, (user['id'],), fetch=True)
            task_count = result[0]['count'] if result else 0
            
            st.metric("Tasks Assigned", task_count)
        
        with col2:
            # Completed tasks
            query = """
            SELECT COUNT(*) as count
            FROM tasks
            WHERE assignee_id = %s AND status_id = (SELECT id FROM statuses WHERE name = 'Done')
            """
            result = execute_query(query, (user['id'],), fetch=True)
            completed_count = result[0]['count'] if result else 0
            
            st.metric("Tasks Completed", completed_count)
        
        with col3:
            # Completion rate
            completion_rate = int((completed_count / task_count) * 100) if task_count > 0 else 0
            st.metric("Completion Rate", f"{completion_rate}%")
        
        # Edit profile button
        if st.button("Edit Profile Information"):
            st.session_state['editing_profile'] = True
        
        # Edit profile form
        if st.session_state.get('editing_profile', False):
            with st.form("edit_profile_form"):
                st.subheader("Edit Profile")
                
                full_name = st.text_input("Full Name", value=user['full_name'])
                email = st.text_input("Email", value=user['email'])
                department = st.text_input("Department", value=user['department'])
                
                submitted = st.form_submit_button("Save Changes")
                
                if submitted:
                    # Update user information
                    update_query = """
                    UPDATE users
                    SET full_name = %s, email = %s, department = %s
                    WHERE id = %s
                    """
                    success = execute_query(update_query, (full_name, email, department, user['id']))
                    
                    if success:
                        st.success("Profile updated successfully!")
                        # Update session state
                        st.session_state['full_name'] = full_name
                        st.session_state['editing_profile'] = False
                        st.experimental_rerun()
                    else:
                        st.error("Failed to update profile. Please try again.")
    
    with profile_tabs[1]:
        # Change Password
        st.subheader("Change Your Password")
        
        with st.form("change_password_form"):
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            
            submitted = st.form_submit_button("Change Password")
            
            if submitted:
                # Check if all fields are filled
                if not current_password or not new_password or not confirm_password:
                    st.error("All fields are required")
                    return
                
                # Check if new password and confirmation match
                if new_password != confirm_password:
                    st.error("New password and confirmation do not match")
                    return
                
                # Check if new password meets requirements
                if len(new_password) < 8:
                    st.error("New password must be at least 8 characters long")
                    return
                
                # Verify current password
                query = "SELECT password_hash FROM users WHERE id = %s"
                result = execute_query(query, (user['id'],), fetch=True)
                
                if result and result[0]['password_hash']:
                    current_hash = result[0]['password_hash']
                    
                    # Hash the provided current password
                    salt = current_hash.split('$')[0]
                    input_hash = salt + '$' + hashlib.sha256((salt + current_password).encode()).hexdigest()
                    
                    if input_hash != current_hash:
                        st.error("Current password is incorrect")
                        return
                    
                    # Generate new password hash
                    salt = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
                    new_hash = salt + '$' + hashlib.sha256((salt + new_password).encode()).hexdigest()
                    
                    # Update password
                    update_query = """
                    UPDATE users
                    SET password_hash = %s
                    WHERE id = %s
                    """
                    success = execute_query(update_query, (new_hash, user['id']))
                    
                    if success:
                        st.success("Password changed successfully!")
                    else:
                        st.error("Failed to update password. Please try again.")
                else:
                    st.error("Failed to verify current password")
    
    with profile_tabs[2]:
        # Department Access
        st.subheader("Your Department Access")
        
        # Get user's department permissions
        query = """
        SELECT d.name, udp.can_view, udp.can_edit
        FROM user_department_permissions udp
        JOIN departments d ON udp.department_id = d.id
        WHERE udp.user_id = %s
        ORDER BY d.name
        """
        permissions = execute_query(query, (user['id'],), fetch=True)
        
        if permissions:
            # Display permissions in a table
            data = [
                {
                    "Department": p['name'],
                    "Can View": "✅" if p['can_view'] else "❌",
                    "Can Edit": "✅" if p['can_edit'] else "❌"
                }
                for p in permissions
            ]
            
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("You don't have access to any departments. Contact an administrator for assistance.")
    
    with profile_tabs[3]:
        # Notification Settings
        st.subheader("Notification Settings")
        
        # User notification preferences
        # This is a placeholder for future implementation
        notification_types = [
            "Task assignments",
            "Status changes",
            "Comments on your tasks",
            "Mentions in comments",
            "Deadline reminders"
        ]
        
        for notif_type in notification_types:
            st.checkbox(notif_type, value=True)
        
        if st.button("Save Notification Settings"):
            st.success("Notification settings saved!")
    
    # Back button
    st.divider()
    if st.button("Back to Dashboard"):
        st.session_state['show_profile'] = False
        st.session_state['current_page'] = "Dashboard"
        st.experimental_rerun()

# Main application
def main():
    # Initialize database
    initialize_database()
    
    # Check if user is authenticated
    is_authenticated = login_page()
    
    if is_authenticated:
        # Sidebar navigation
        menu, priority_filter, assignee_filter, status_filter = sidebar()
        
        # Display the selected page
        if menu == "User Profile":
            user_profile_page()
        elif menu == "Dashboard":
            dashboard_page()
        elif menu == "My Tasks":
            my_tasks_page()
        elif menu == "Create Task":
            create_task_page()
        elif menu == "Task Board":
            task_board_page()
        elif menu == "Reports":
            reports_page()
        elif menu == "Team Members":
            team_members_page()
        elif menu == "Admin Panel" and st.session_state.get('role') == 'admin':
            admin_panel_page()
        elif menu == "Notifications":
            notifications_page()
        elif "Department" in menu:
            # Handle department-specific pages
            department_name = menu.replace(" Department", "")
            department_page(department_name)
        else:
            st.error("Page not found")
    
    # Add app footer
    st.markdown("---")
    st.markdown("© 2023 Edubull | Task Management System")

if __name__ == "__main__":
    main()
