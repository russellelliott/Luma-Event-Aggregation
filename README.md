# Luma Event Aggregator

This project aggregates events from Luma, classifies them using AI, and provides a web interface to explore and filter them. It consists of a Python FastAPI backend and a React frontend.

## Project Structure

-   **`backend/`**: Python-based backend that handles event fetching, aggregation, classification (using LLMs), and serves a REST API.
-   **`frontend/`**: React-based frontend that provides the user interface for browsing events.

## Quick Start

The easiest way to run the application is using the provided startup script.

1.  **Make the script executable (first time only):**
    ```bash
    chmod +x start.sh
    ```

2.  **Run the application:**
    ```bash
    ./start.sh
    ```

    You will be presented with two options:
    *   **Option 1**: Start App Only (Skips data pipeline & backup, just starts servers)
    *   **Option 2**: Run Full Pipeline (Backs up database -> Fetches/Classifies events -> Starts servers)

The script uses **port 8001** for the backend and **port 3001** for the frontend to avoid conflicts.

---

## Manual Setup

If you prefer to run services individually or need development specifics:

### 1. Backend Setup

The backend requires Python, several dependencies, and API keys (Google Maps, etc.).

👉 **[Read the Backend README](backend/README.md)** for detailed setup and usage instructions.

### 2. Frontend Setup

The frontend is a React application that connects to the backend API.

👉 **[Read the Frontend README](frontend/README.md)** for installation and running instructions.

