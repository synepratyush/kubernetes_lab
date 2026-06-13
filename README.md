```python
# File: app-cluster.py
# Project: Flask + Postgress Containerized Application for Kubernetes
# This guide provides step-by-step instructions for building and deploying a containerized Flask app with Postgress database on Kubernetes
#Your YAML manifest defines a high-availability, 3-replica PostgreSQL 16 cluster managed via a Kubernetes StatefulSet and a Headless Service.
#Stateful Orchestration: The StatefulSet guarantees ordered pod creation (postgres-0 to postgres-2), persistent network identities, and dedicated storage volumes (1Gi each) via volumeClaimTemplates.
#Headless Networking: Setting clusterIP: None allows pods to bypass standard load balancing and discover each other directly via internal DNS (e.g., postgres-0.postgres).
#Cluster Initialization: An initContainer uses a custom script (init-replica.sh) to synchronize standby replicas with the primary instance, while the main container injects a network configuration script (setup-primary-hba.sh) into the PostgreSQL entry point.

guide_content = """
# Building a local Flask web app + Postgress Application in Kubernetes

## Overview
You'll create a containerized application of Postgress :
- Flask web application (deployed in local)
- Postgress database (deployed as a stateful service)

## Step 1: Project Structure

Create this directory structure:
## Project Structure

```text
flask-mysql-k8s/
├── postgres-cluster.yaml
├── app-cluster.py
└── README.md
```

## Step 2: Flask Application Code

### app=cluster.py
```python
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)

# Fixed local configurations
DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_NAME = "postgres"

# Maps the pod names to the local forwarded ports we opened in Step 1
POD_PORT_MAP = {
    "postgres-0": 5430,  # Primary (Read/Write)
    "postgres-1": 5431,  # Replica 1 (Read Only)
    "postgres-2": 5432   # Replica 2 (Read Only)
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Local K8s Postgres Controller</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f4f6f9; color: #333; }
        .container { max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1, h2 { color: #2c3e50; }
        .alert { padding: 10px; background: #e2f0d9; border-left: 5px solid #70ad47; margin-bottom: 20px; }
        .error { padding: 10px; background: #fce4d6; border-left: 5px solid #c65911; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #f2f2f2; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="email"], select { width: 100%; padding: 8px; box-sizing: border-box; }
        button { background: #2980b9; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #3498db; }
        .pod-badge { background: #8e44ad; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; }
    </style>
</head>
<body>
<div class="container">
    <h1>PostgreSQL Cluster Viewer (Running Locally)</h1>
    
    <!-- Target Pod Selector -->
    <form method="GET" action="/">
        <div class="form-group">
            <label for="target_pod">Choose Target Pod (Routes to unique local port):</label>
            <select name="target_pod" id="target_pod" onchange="this.form.submit()">
                <option value="postgres-0" {% if selected_pod == 'postgres-0' %}selected{% endif %}>postgres-0 (via Local Port 5430 - Primary)</option>
                <option value="postgres-1" {% if selected_pod == 'postgres-1' %}selected{% endif %}>postgres-1 (via Local Port 5431 - Replica)</option>
                <option value="postgres-2" {% if selected_pod == 'postgres-2' %}selected{% endif %}>postgres-2 (via Local Port 5432 - Replica)</option>
            </select>
        </div>
    </form>

    {% if msg %}<div class="alert">{{ msg }}</div>{% endif %}
    {% if err %}<div class="error">{{ err }}</div>{% endif %}

    <!-- Data Modification Form -->
    <h2>Add New User</h2>
    <form method="POST" action="/add?target_pod={{ selected_pod }}">
        <div class="form-group">
            <label>Name:</label>
            <input type="text" name="name" required placeholder="Bob Tester">
        </div>
        <div class="form-group">
            <label>Email:</label>
            <input type="email" name="email" required placeholder="bob@tester.com">
        </div>
        <button type="submit">Insert User Row</button>
    </form>

    <!-- Data View Table -->
    <h2>Current Rows on <span class="pod-badge">{{ selected_pod }}</span></h2>
    <table>
        <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Email</th>
            <th>Created At</th>
        </tr>
        {% for user in users %}
        <tr>
            <td>{{ user.id }}</td>
            <td>{{ user.name }}</td>
            <td>{{ user.email }}</td>
            <td>{{ user.created_at }}</td>
        </tr>
        {% else %}
        <tr>
            <td colspan="4" style="text-align: center;">No data found. Is port-forwarding running?</td>
        </tr>
        {% endfor %}
    </table>
</div>
</body>
</html>
"""

def get_db_connection(pod_name):
    # Connects to localhost but targets the specific forwarded port for that pod
    target_port = POD_PORT_MAP.get(pod_name, 5430)
    return psycopg2.connect(
        host="127.0.0.1",
        port=target_port,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=3
    )

@app.route("/", methods=["GET"])
def index():
    selected_pod = request.args.get("target_pod", "postgres-0")
    users = []
    err = None
    msg = request.args.get("msg")

    try:
        conn = get_db_connection(selected_pod)
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT id, name, email, created_at FROM users ORDER BY id DESC;")
        users = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        err = f"Failed connecting locally to {selected_pod} on port {POD_PORT_MAP.get(selected_pod)}: {str(e)}"

    return render_template_string(HTML_TEMPLATE, users=users, selected_pod=selected_pod, err=err, msg=msg)

@app.route("/add", methods=["POST"])
def add_user():
    target_pod = request.args.get("target_pod", "postgres-0")
    name = request.form.get("name")
    email = request.form.get("email")
    
    try:
        conn = get_db_connection(target_pod)
        cur = conn.cursor()
        cur.execute("INSERT INTO users (name, email) VALUES (%s, %s);", (name, email))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index', target_pod=target_pod, msg="User successfully inserted!"))
    except Exception as e:
        err_msg = f"Write rejected by engine: {str(e)}"
        return redirect(url_for('index', target_pod=target_pod, err=err_msg))

if __name__ == "__main__":
    # Launch local development server
    app.run(host="127.0.0.1", port=9090, debug=True)

```
### postgres-cluster.yaml
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgres-cluster-scripts
data:
  # Runs on ALL nodes, but conditionally executes ONLY on the primary node (ordinal 0)
  setup-primary-hba.sh: |
    #!/bin/bash
    set -e
    ORDINAL=$(hostname | grep -oE '[0-9]+$')
    if [ "$ORDINAL" -eq 0 ]; then
      echo "Configuring HBA rules on primary node..."
      echo "host replication postgres all trust" >> "$PGDATA/pg_hba.conf"
      # No need to run pg_ctl reload here; this directory executes BEFORE the main process starts
    else
      echo "Skipping HBA configuration on replica node $ORDINAL"
    fi

  # Orchestrates cloning loops on replicas during booting
  init-replica.sh: |
    #!/bin/bash
    set -e
    
    # Correctly parse the pod hostname string
    if [[ $(hostname) =~ -([0-9]+)$ ]]; then
        ORDINAL=${BASH_REMATCH[1]}
    else
        echo "Failed to parse ordinal from hostname"
        exit 1
    fi

    if [ "$ORDINAL" -eq 0 ]; then
      echo "Initializing Node 0 as Cluster Primary..."
      exit 0
    fi

    echo "Initializing Node ${ORDINAL} as Data Replica..."
    
    until pg_isready -h postgres-0.postgres -p 5432 -U postgres; do
      echo "Waiting for postgres-0 to accept active connections..."
      sleep 3
    done

    if [ ! -s "$PGDATA/PG_VERSION" ]; then
      echo "Directory empty. Starting streaming backup clone..."
      rm -rf "${PGDATA:?}"/* "${PGDATA:?}"/.* 2>/dev/null || true
      
      # Added -R flag to auto-generate standby.signal for Postgres 16 replication
      PGPASSWORD=postgres pg_basebackup -h postgres-0.postgres -D "$PGDATA" -U postgres -v -P -R -X stream
      echo "Replication snapshot completed successfully."
    fi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  labels:
    app: postgres
spec:
  ports:
  - name: postgres
    port: 5432
  clusterIP: None
  selector:
    app: postgres
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  selector:
    matchLabels:
      app: postgres
  serviceName: postgres
  replicas: 3
  template:
    metadata:
      labels:
        app: postgres
    spec:
      initContainers:
      - name: sync-replica-volumes
        image: postgres:16
        command: [ /bin/bash, /cluster-scripts/init-replica.sh ]
        env:
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
        - name: scripts
          mountPath: /cluster-scripts
      containers:
      - name: postgres
        image: postgres:16
        env:
        - name: POSTGRES_USER
          value: postgres
        - name: POSTGRES_PASSWORD
          value: postgres
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        ports:
        - name: postgres
          containerPort: 5432
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
        # Mount the primary setup script to docker-entrypoint-initdb.d
        - name: scripts
          mountPath: /docker-entrypoint-initdb.d/setup-primary-hba.sh
          subPath: setup-primary-hba.sh
      volumes:
      - name: scripts
        configMap:
          name: postgres-cluster-scripts
          defaultMode: 0755
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ ReadWriteOnce ]
      resources:
        requests:
          storage: 1Gi

```
### Deploy to Kubernetes
```bash
# Apply the updated production configurations
kubectl apply -f postgres-cluster.yaml

#Run this command in your terminal to connect to the primary node (postgres-0) and create the table:
kubectl exec -it postgres-0 -- psql -U postgres -c "
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);"

#Test the Live Replication AgainNow that the table structure exists across your cluster, you can verify that data streams instantly between your pods:Insert a row into the primary pod (postgres-0):
kubectl exec -it postgres-0 -- psql -U postgres -c "INSERT INTO users (name, email) VALUES ('Bob Tester', 'bob@test.com');"

Expected Output: INSERT 0 1

#Read the row immediately from the replica pod (postgres-1):
kubectl exec -it postgres-1 -- psql -U postgres -c "SELECT * FROM users;"

Expected Visual Output from your Replica:
 id |    name    |    email     |         created_at         
----+------------+--------------+----------------------------
  1 | Bob Tester | bob@test.com | 2026-06-12 14:43:25.123456
(1 row)
```

### How to Verify Your Data Replicates Live
```bash

Insert into the primary node:
kubectl exec -it postgres-0 -- psql -U postgres -c "INSERT INTO users (name, email) VALUES ('Bob Tester', 'bob@test.com');"

Read immediately from your replica node (postgres-1):
kubectl exec -it postgres-1 -- psql -U postgres -c "SELECT * FROM users;" 

This setup provides a production-ready containerized Flask + MySQL application deployed on Kubernetes with proper configuration management.
"""

print(guide_content)
```