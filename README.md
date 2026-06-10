```python
# File: containerized_app_guide.py
# Project: Flask + MySQL Containerized Application for Kubernetes
# This guide provides step-by-step instructions for building and deploying a containerized Flask app with MySQL database on Kubernetes

guide_content = """
# Building a Containerized Flask + MySQL Application for Kubernetes

## Overview
You'll create a containerized application with:
- Flask web application (deployed as a Kubernetes Deployment)
- MySQL database (deployed as a stateful service)
- Both in separate namespaces on a public cloud Kubernetes cluster
- Configuration management using ConfigMaps and Secrets

## Step 1: Project Structure

Create this directory structure:
```
flask-mysql-k8s/
├── app/
│   ├── __init__.py
│   ├── requirements.txt
│   └── Dockerfile
├── mysql/
│   ├── init.sql
│   └── Dockerfile
├── k8s/
│   ├── namespace-flask.yaml
│   ├── namespace-mysql.yaml
│   ├── flask-configmap.yaml
│   ├── flask-secret.yaml
│   ├── flask-deployment.yaml
│   ├── flask-service.yaml
│   ├── mysql-statefulset.yaml
│   ├── mysql-service.yaml
│   └── mysql-secret.yaml
├── docker-compose.yml
└── README.md
```

## Step 2: Flask Application Code

### app/__init__.py
```python
from flask import Flask
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(
        host='mysql-service',
        database='flask_db',
        user='flask_user',
        password='flask_password'
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

@app.route('/health')
def health():
    return 'OK'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### app/requirements.txt
```
Flask==3.0.0
mysql-connector-python==8.2.0
gunicorn==21.2.0
```

### app/Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "__init__.py:app"]
```

## Step 3: MySQL Database Setup

### mysql/init.sql
```sql
CREATE DATABASE IF NOT EXISTS flask_db;
USE flask_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (username, email) VALUES ('test_user', 'test@example.com');
```

### mysql/Dockerfile
```dockerfile
FROM mysql:8.0

COPY init.sql /docker-entrypoint-initdb.d/

EXPOSE 3306
```

## Step 4: Kubernetes Namespace Configurations

### k8s/namespace-flask.yaml
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: flask-app
  labels:
    app: flask
```

### k8s/namespace-mysql.yaml
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mysql-db
  labels:
    app: mysql
```

## Step 5: ConfigMaps and Secrets

### k8s/flask-configmap.yaml
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: flask-config
  namespace: flask-app
data:
  FLASK_ENV: "production"
  DB_HOST: "mysql-service.mysql-db"
  DB_NAME: "flask_db"
  APP_PORT: "5000"
```

### k8s/flask-secret.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: flask-secret
  namespace: flask-app
type: Opaque
data:
  DB_USER: "flask_user"
  DB_PASSWORD: "flask_password"
```

### k8s/mysql-secret.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mysql-secret
  namespace: mysql-db
type: Opaque
data:
  MYSQL_USER: "flask_user"
  MYSQL_PASSWORD: "flask_password"
  MYSQL_DATABASE: "flask_db"
```

## Step 6: Flask Deployment and Service

### k8s/flask-deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flask-app
  namespace: flask-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: flask
  template:
    metadata:
      labels:
        app: flask
    spec:
      containers:
      - name: flask-container
        image: your-registry/flask-app:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 5000
        envFrom:
        - configMapRef:
            name: flask-config
        - secretRef:
            name: flask-secret
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
```

### k8s/flask-service.yaml
```yaml
apiVersion: v1
kind: Service
metadata:
  name: flask-service
  namespace: flask-app
spec:
  selector:
    app: flask
  ports:
  - protocol: TCP
    port: 80
    targetPort: 5000
  type: LoadBalancer
```

## Step 7: MySQL StatefulSet and Service

### k8s/mysql-statefulset.yaml
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
  namespace: mysql-db
spec:
  serviceName: mysql-service
  replicas: 1
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
      - name: mysql-container
        image: your-registry/mysql:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 3306
        envFrom:
        - secretRef:
            name: mysql-secret
        volumeMounts:
        - name: mysql-data
          mountPath: /var/lib/mysql
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "512Mi"
            cpu: "400m"
  volumeClaimTemplates:
  - metadata:
      name: mysql-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
      storageClassName: standard
```

### k8s/mysql-service.yaml
```yaml
apiVersion: v1
kind: Service
metadata:
  name: mysql-service
  namespace: mysql-db
spec:
  ports:
  - port: 3306
    targetPort: 3306
  selector:
    app: mysql
  type: ClusterIP
```

## Step 8: Docker Compose for Local Testing

### docker-compose.yml
```yaml
version: '3.8'

services:
  flask:
    build: ./app
    ports:
      - "5000:5000"
    environment:
      - DB_HOST=mysql
      - DB_NAME=flask_db
      - DB_USER=flask_user
      - DB_PASSWORD=flask_password
    depends_on:
      - mysql

  mysql:
    build: ./mysql
    ports:
      - "3306:3306"
    environment:
      - MYSQL_USER=flask_user
      - MYSQL_PASSWORD=flask_password
      - MYSQL_DATABASE=flask_db
```

## Step 9: Deployment Commands

### Create Namespaces
```bash
kubectl apply -f k8s/namespace-flask.yaml
kubectl apply -f k8s/namespace-mysql.yaml
```

### Build and Push Docker Images
```bash
# Build Flask image
docker build -t your-registry/flask-app:latest ./app

# Build MySQL image
docker build -t your-registry/mysql:latest ./mysql

# Push to registry
docker push your-registry/flask-app:latest
docker push your-registry/mysql:latest
```

### Deploy to Kubernetes
```bash
# Apply ConfigMaps and Secrets
kubectl apply -f k8s/flask-configmap.yaml
kubectl apply -f k8s/flask-secret.yaml
kubectl apply -f k8s/mysql-secret.yaml

# Deploy Flask application
kubectl apply -f k8s/flask-deployment.yaml
kubectl apply -f k8s/flask-service.yaml

# Deploy MySQL database
kubectl apply -f k8s/mysql-statefulset.yaml
kubectl apply -f k8s/mysql-service.yaml
```

### Verify Deployment
```bash
# Check Flask pods
kubectl get pods -n flask-app

# Check MySQL pods
kubectl get pods -n mysql-db

# Get Flask service endpoint
kubectl get service -n flask-app

kubectl port-forward pod/mysql-0 -n mysql-db 3306:3306
# try with workbench 

# Test Flask application
kubectl run test --rm --image=busybox --restart=Never --wget http://flask-service.flask-app.svc.cluster.local/
```

## Step 10: Public Cloud Specifics

### Google Cloud Kubernetes (GKE)
```bash
# Create GKE cluster
gcloud container clusters create flask-mysql-cluster \
  --region=us-central1 \
  --num-nodes=3

# Get credentials
gcloud container clusters get-credentials flask-mysql-cluster \
  --region=us-central1
```

### AWS Elastic Kubernetes (EKS)
```bash
# Create EKS cluster
eksctl create cluster --name flask-mysql-cluster \
  --region=us-east-1 \
  --nodes=3 \
  --nodes-min=3 \
  --nodes-max=5
```

### Azure Kubernetes (AKS)
```bash
# Create AKS cluster
az aks create --resource-group myResourceGroup \
  --name flask-mysql-cluster \
  --node-count 3 \
  --enable-addons monitoring
```

## Key Configuration Notes

1. **Separate Namespaces**: Flask app in `flask-app`, MySQL in `mysql-db`
2. **Stateful MySQL**: Uses StatefulSet with persistent volume claims (10Gi storage)
3. **Configured Deployment**: Flask uses Deployment with 3 replicas
4. **Secret Management**: Database credentials stored in Kubernetes Secrets
5. **ConfigMap Usage**: Environment variables and configuration in ConfigMaps
6. **Service Discovery**: MySQL accessible via `mysql-service.mysql-db` from Flask namespace
7. **Resource Limits**: Both services have defined CPU/memory requests and limits
8. **Public Cloud Ready**: Deployment commands compatible with GKE, EKS, AKS

## Security Best Practices

- Use Kubernetes Secrets for sensitive data (never hardcode passwords)
- Implement network policies to restrict cross-namespace access
- Use non-root containers in Docker images
- Enable TLS for MySQL connections
- Implement regular security updates for base images

This setup provides a production-ready containerized Flask + MySQL application deployed on Kubernetes with proper configuration management.
"""

print(guide_content)
```