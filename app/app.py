import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)

# Environment Variables for Credentials
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_RW_USER = os.getenv("DB_RW_USER", "postgres")
DB_RW_PASSWORD = os.getenv("DB_RW_PASSWORD", "postgres")

# Read-Only Credentials for Replicas
DB_RO_USER = os.getenv("DB_RO_USER", "postgres")
DB_RO_PASSWORD = os.getenv("DB_RO_PASSWORD", "postgres")

POD_HOST_MAP = {
    "postgres-0": "postgres-0.postgres",
    "postgres-1": "postgres-1.postgres",
    "postgres-2": "postgres-2.postgres"
}

POOL_MAP = {}

def initialize_pools():
    """Initializes dedicated connection pools with proper security contexts."""
    for pod, host in POD_HOST_MAP.items():
        if pod in ["postgres-1", "postgres-2"]:
            user = DB_RO_USER
            password = DB_RO_PASSWORD
        else:
            user = DB_RW_USER
            password = DB_RW_PASSWORD

        try:
            POOL_MAP[pod] = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                host=host,
                port=5432,
                database=DB_NAME,
                user=user,
                password=password
            )
            print(f"Pool initialized for {pod}")
        except Exception as e:
            print(f"Failed to initialize pool for {pod}: {e}")

initialize_pools()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Postgres Cluster Viewer</title>
</head>
<body>
    <h1>Postgres Cluster Viewer</h1>
    <form method="GET">
        <label>Select Data Source (Read Node): </label>
        <select name="target_pod" onchange="this.form.submit()">
            <option value="postgres-0" {% if selected_pod == 'postgres-0' %}selected{% endif %}>Primary (postgres-0)</option>
            <option value="postgres-1" {% if selected_pod == 'postgres-1' %}selected{% endif %}>Replica 1 (postgres-1)</option>
            <option value="postgres-2" {% if selected_pod == 'postgres-2' %}selected{% endif %}>Replica 2 (postgres-2)</option>
        </select>
    </form>

    <h2>Add User (Auto-routed to Primary)</h2>
    <form method="POST" action="/add?target_pod={{ selected_pod }}">
        <input type="text" name="name" placeholder="Name" required>
        <input type="email" name="email" placeholder="Email" required>
        <button type="submit">Insert Data</button>
    </form>

    <h2>Users List (Viewing from: {{ selected_pod }})</h2>
    {% if err %}
        <p style="color:red"><strong>Error:</strong> {{ err }}</p>
    {% endif %}
    
    <table border="1">
        <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Email</th>
            <th>Created</th>
        </tr>
        {% for user in users %}
        <tr>
            <td>{{ user.id }}</td>
            <td>{{ user.name }}</td>
            <td>{{ user.email }}</td>
            <td>{{ user.created_at }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route("/")
def index():
    selected_pod = request.args.get("target_pod", "postgres-0")
    err = request.args.get("err")
    users = []
    conn = None
    
    try:
        # 1. Handle Table Initialization (Always on Primary)
        primary_conn = POOL_MAP["postgres-0"].getconn()
        try:
            cur_init = primary_conn.cursor()
            cur_init.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    email VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            primary_conn.commit()
            cur_init.close()
        finally:
            POOL_MAP["postgres-0"].putconn(primary_conn)

        # 2. Execute Data Read from the Selected Pod (Can be replica or primary)
        conn = POOL_MAP[selected_pod].getconn()
        
        # Explicitly set the connection to read-only state for replica safety
        if selected_pod in ["postgres-1", "postgres-2"]:
            conn.set_session(readonly=True, autocommit=True)
            
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT id, name, email, created_at FROM users ORDER BY id DESC")
        users = cur.fetchall()
        cur.close()
        
        # Close snapshot visibility state
        if selected_pod not in ["postgres-1", "postgres-2"]:
            conn.commit()
            
    except Exception as e:
        err = str(e)
    finally:
        if conn and selected_pod in POOL_MAP:
            # Clean connection flags before returning to pool
            try:
                conn.set_session(readonly=False, autocommit=False)
            except Exception:
                pass
            POOL_MAP[selected_pod].putconn(conn)
        
    return render_template_string(
        HTML_TEMPLATE,
        users=users,
        selected_pod=selected_pod,
        err=err
    )

@app.route("/add", methods=["POST"])
def add_user():
    target_pod = request.args.get("target_pod", "postgres-0")
    conn = None
    
    try:
        conn = POOL_MAP["postgres-0"].getconn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users(name, email) VALUES(%s, %s)",
            (request.form["name"], request.form["email"])
        )
        conn.commit()
        cur.close()
    except Exception as e:
        return redirect(url_for("index", target_pod=target_pod, err=str(e)))
    finally:
        if conn:
            POOL_MAP["postgres-0"].putconn(conn)
        
    return redirect(url_for("index", target_pod=target_pod))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9090)
