# 🚛 Food Truck Finder API (FastAPI)

This repository contains the backend server for a real-time food truck tracking and ordering application. It is built using FastAPI, PostgreSQL (with PostGIS for geospatial queries), and Redis (for Geo-caching and real-time Pub/Sub).

## 💡 Key Features

  * **Real-Time Geospatial Search:** Customers find active trucks within a radius using high-speed Redis GeoSet caching.
  * **Live Location Tracking:** Truck owners send continuous location updates via dedicated WebSockets.
  * **Zero Location History:** Only the current position is stored; no historical location data is accumulated.
  * **Real-Time Orders:** Instantaneous order notifications and status updates via Redis Pub/Sub and WebSockets.
  * **Secure API:** Implements JWT authentication and Role-Based Access Control (RBAC) for `customer` and `truck` roles.

## 🚀 Getting Started

These instructions will get your complete application stack running locally using Docker Compose.

### Prerequisites

You need the following software installed on your machine:

1.  **Docker Desktop** (or Docker Engine if using Linux).
2.  **Git** (to clone the repository).

### Setup Steps

1.  **Clone the repository:**

    ```bash
    git clone [your-repo-link]
    cd food-truck-finder
    ```

2.  **Create `.env` File:** Copy the example file and populate it with your secure credentials.

    ```bash
    cp .env.example .env 
    # (Then edit .env with your secrets)
    ```

3.  **Launch the Stack:** This command builds the FastAPI Docker image, starts the PostGIS database, and starts the Redis cache.

    ```bash
    docker compose up --build
    ```

    The console output will show the services starting. Look for the message indicating Uvicorn is running.

4.  **Access the API:**
    The server should now be running and accessible:

      * **Swagger UI (Documentation):** `http://localhost:8000/docs`
      * **Health Check:** `http://localhost:8000/health`

-----

## ⚙️ Architecture and Technology Stack

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **Server** | FastAPI | High-performance ASGI framework. |
| **ASGI Runner** | Gunicorn + Uvicorn | Production-grade process management and async serving. |
| **Database** | PostgreSQL + PostGIS | Primary data storage; handles complex spatial indexing (`GIST`). |
| **Real-Time / Cache** | Redis | Geospatial caching (`GEOADD`, `GEOSEARCH`) and Order Pub/Sub. |
| **Authentication** | JWT (`python-jose`) | Token-based security with bcrypt password hashing. |

### Project Structure

```
food-truck-finder/
├── app/
│   ├── api/             # FastAPI Routers (REST endpoints and WebSockets)
│   ├── core/            # Configuration and security utilities
│   └── db/              # Database models, connection, and Redis services
│       ├── models.py    # SQLAlchemy ORM Models (incl. GeoAlchemy2)
│       ├── schemas.py   # Pydantic Schemas for validation
│       └── services.py  # Business logic (PostGIS updates, Redis Geo/PubSub)
├── Dockerfile           # Defines the FastAPI image
├── docker-compose.yml   # Defines services: app, db (PostGIS), redis
├── .env.example         # Example configuration file
├── postgis_schema.sql   # SQL script to enable PostGIS extension and create spatial index
└── README.md            # This file
```

-----

## 🛡️ API Endpoints Summary

| Feature | Method | Endpoint | Access | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Auth** | `POST` | `/api/v1/register/truck` | Public | Creates owner account; returns JWT token. |
| **Auth** | `POST` | `/api/v1/login` | Public | Authenticates user; returns JWT token. |
| **Search** | `POST` | `/api/v1/trucks/nearby` | Public | Uses location (lat/lon) to search active trucks via Redis GeoSet. |
| **Location** | `PUT` | `/api/v1/owner/status` | Owner | Toggles the `is_active` status (Open/Closed). |
| **Order** | `POST` | `/api/v1/orders/place` | Customer | Places order; publishes to Redis Pub/Sub for owner notification. |
| **WS (Owner)** | `WS` | `/api/v1/ws/location/update` | Owner | Truck sends high-frequency location pings. Removes location on disconnect. |
| **WS (Both)** | `WS` | `/api/v1/ws/notifications` | All | Real-time stream for new orders (owner) or status updates (customer). |

-----

## 🛑 Testing and Cleanup

### Running Specific Services

To run only the database and Redis without the API server:

```bash
docker compose up db redis
```

### Stopping the Stack

To stop and remove all containers, networks, and volumes:

```bash
docker compose down
```