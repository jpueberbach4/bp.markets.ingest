# Developer's Guide: Horizontal Scaling Strategy

## 1. Overview
This documentation provides a strategic framework for scaling the platform. While the software is currently in an MVP state, its architectural characteristics offer specific opportunities for horizontal scaling within a distributed environment like Kubernetes.

## 2. Component Analysis

### 2.1 The ETL Process
The ETL (Extract, Transform, Load) engine is natively designed for high-concurrency. It automatically leverages all available CPUs to distribute processing loads. 
* **Scaling Behavior:** Vertical scaling (adding more CPU cores) directly improves ingestion throughput.

### 2.2 The API HTTP Service
The API is built for high performance using zero-copy IO. However, it currently operates on a single-threaded, event-loop based FastAPI implementation. 
* **Limitation:** A single instance is bound to one CPU core.
* **Opportunity:** This deterministic behavior allows for precise resource allocation and predictable scaling "units" when deploying via containers.

---

## 3. Recommended Scaling Architecture: Kubernetes (K8s)

The most efficient way to scale the API is to treat each instance as a discrete, predictable unit of work. By leveraging a "Sidecar" or "Multiple Pod" approach, we can overcome the single-threaded limitation.

### 3.1 Pod Parametrics
To ensure stability and performance, each pod should be strictly defined to prevent resource contention or "noisy neighbor" effects.

| Resource | Value | Note |
| :--- | :--- | :--- |
| **CPU Request** | `1` | Pins the instance to exactly one physical/virtual core. |
| **CPU Limit** | `1` | Prevents the event loop from competing for cycles. |
| **Memory Request** | `1024Mi` | Based on stress-test monitoring. |
| **Memory Limit** | `1024Mi` | Strict limit to prevent memory sharing and swapping. |

### 3.2 Data Access
Since the software utilizes **proprietary** binary files for its data operations, the storage layer must be handled as follows:
* **Mount Type:** Read-Only-Many (ROX).
* **Strategy:** Mount the binary data files to every pod. This ensures that as the number of pods increases, every instance has high-speed access to the source data without write-lock conflicts.

---

## 4. Implementation Strategy

1.  **Containerization:** Package the FastAPI service into a lightweight container.
2.  **Horizontal Pod Autoscaler (HPA):** Scale the number of replicas based on CPU utilization or Request-Per-Second (RPS) metrics. Because each pod is pinned to 1 CPU, an 80% CPU load on a pod is a clear indicator that a new pod "unit" is required.
3.  **Load Balancing:** Use an Ingress Controller (e.g., NGINX or Traefik) to distribute incoming HTTP traffic across the fleet of single-threaded pods.

## 5. Summary of Constraints
* **Do not** attempt to run multiple workers (Gunicorn/Uvicorn workers) within a single pod unless you increase the CPU/Memory limits proportionally.
* **Do** keep the memory limit and request identical (1024MB) to ensure the pod is assigned to a node with guaranteed resources (Guaranteed QoS class).