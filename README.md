# Luma Event Aggregator

This project aggregates events from Luma, classifies them using AI, and provides a web interface to explore and filter them. It consists of a Python FastAPI backend and a React frontend.

## Project Structure

-   **`backend/`**: Python-based backend that handles event fetching, aggregation, classification (using LLMs), and serves a REST API.
-   **`frontend/`**: React-based frontend that provides the user interface for browsing events.

## Getting Started

To set up the entire project, you will need to configure and run both the backend and the frontend.

### 1. Backend Setup

The backend requires Python, several dependencies, and API keys (Google Maps, etc.).

👉 **[Read the Backend README](backend/README.md)** for detailed setup and usage instructions.

### 2. Frontend Setup

The frontend is a React application that connects to the backend API.

👉 **[Read the Frontend README](frontend/README.md)** for installation and running instructions.

## Quick Run Guide

1.  **Start the Backend**:
    ```bash
    cd backend
    # (Activate your virtual environment)
    uvicorn main:app --reload
    ```

2.  **Start the Frontend**:
    ```bash
    cd frontend
    npm start
    ```

3.  Access the application at `http://localhost:3000`.
