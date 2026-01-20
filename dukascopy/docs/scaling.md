# Developer's Guide: Horizontal Scaling Strategy

## 1. Overview
This documentation provides a strategic framework for scaling the platform. While the software is currently in an MVP state, its architectural characteristics—specifically its single-threaded, high-performance event loop—offer precise opportunities for horizontal scaling within a Kubernetes environment.

## 2. Component Analysis

### 2.1 The ETL Process
The ETL (Extract, Transform, Load) engine is natively designed for high-concurrency. It automatically leverages all available CPU cores to distribute ingestion and processing loads.
* **Scaling Behavior:** Vertical scaling (allocating more CPU cores) directly improves ingestion throughput.

### 2.2 The API HTTP Service
The API leverages zero-copy IO for high performance. It currently operates on a single-threaded, event-loop based FastAPI implementation.
* **Limitation:** A single instance is bound to one CPU core.
* **Opportunity:** This deterministic behavior allows for predictable scaling "units." By deploying multiple single-threaded pods, we achieve horizontal scale without the complexity of multi-worker management within a single container.

---

## 3. Kubernetes (K8s) Deployment Configuration

To ensure stability, each pod must be treated as a discrete resource unit with strict boundaries and lifecycle management.

### 3.1 Resource Parametrics (Guaranteed QoS)
Set requests and limits identically to ensure the pod is assigned to a node with guaranteed resources and to prevent CPU/Memory overcommitment.

| Resource | Value | Note |
| :--- | :--- | :--- |
| **CPU Request/Limit** | `1` | Pins instance to exactly one core to prevent context switching. |
| **Memory Request/Limit** | `1024Mi` | Sufficient for standard operations and memory-mapped buffers. |

### 3.2 Lifecycle & Health Probes
Given the **proprietary** binary data handling and memory-mapped (mmap) cache initialization, the following probes are required to prevent routing traffic to unready instances.

* **Startup Probe:** Recommended for mmap-heavy initialization. This provides the container extra time to load large binary files into memory before the readiness checks begin.
* **Readiness Probe:** Implement an `HTTP GET /healthz` endpoint.
    * *Config:* `initialDelaySeconds: 10–30`, `periodSeconds: 10`.
    * *Purpose:* Prevents traffic from reaching pods that are still warming up caches or loading configurations.

### 3.3 Availability & Traffic Management
* **Pod Disruption Budget (PDB):** To maintain service availability during node maintenance or upgrades, a PDB must be defined.
    * *Config:* `minAvailable: 1` (for small clusters) or `minAvailable: 50%` (for larger fleets).
* **Ingress / Service:** Use a standard Ingress Controller.
    * *Config:* Use `ClusterIP` + `Ingress`.
    * *Session Affinity:* Since FastAPI is stateless, keep **sticky sessions off**. This ensures a more even distribution of requests across the single-threaded pod fleet.

---

## 4. Implementation Strategy

1.  **Storage:** Mount the proprietary binary files as **Read-Only-Many (ROX)**. This allows an unlimited number of pods to read the source data simultaneously without locking issues.
2.  **Autoscaling (HPA):** Use the Horizontal Pod Autoscaler to scale based on CPU utilization. Since each pod is restricted to 1 CPU, a consistent 80% CPU load is a high-fidelity signal to trigger a replica increase.
3.  **Efficiency:** The single-threaded design simplifies debugging and monitoring, as 1 pod = 1 event loop = 1 CPU core.

## 5. Summary of Constraints
* **Avoid** running multiple Uvicorn/Gunicorn workers per pod; instead, increase the replica count in Kubernetes.
* **Ensure** that the binary data mount is reliable, as mmap failure during the Startup Probe phase will correctly prevent the pod from entering the service rotation.