import os
from flask import Flask, jsonify  # Added jsonify to handle JSON responses safely
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'mysql-service.mysql-db.svc.cluster.local'),
        database=os.environ.get('DB_NAME', 'flask_db'),
        user=os.environ.get('DB_USER', 'flask_user'),
        password=os.environ.get('DB_PASSWORD', 'flask_password')
    )

@app.route('/')
def home():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        return f'Connected to MySQL! Database version: {result}'
    except Error as e:
        return f'Database connection error: {str(e)}'

# --- NEW SELECT QUERY ROUTE ---
@app.route('/users')
def get_users():
    try:
        connection = get_db_connection()
        # dictionary=True converts rows into key-value pairs automatically
        cursor = connection.cursor(dictionary=True) 
        
        # Execute the SELECT query
        query = "SELECT id, username, email FROM users"
        cursor.execute(query)
        
        # Fetch all matching rows
        users = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        # Return results structured as clean JSON
        return jsonify(users)
        
    except Error as e:
        return jsonify({"error": f"Failed to fetch data: {str(e)}"}), 500

@app.route('/health')
def health():
    return 'OK'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
