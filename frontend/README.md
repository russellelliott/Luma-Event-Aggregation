# Luma Event Aggregator - Frontend

This is the frontend application for the Luma Event Aggregator, built with React and Tailwind CSS. It provides a user interface to view, filter, and explore aggregated events.

## Features

-   **Event Visualization**: View events in a list or calendar view.
-   **Filtering**: Filter events by city, date, and classification.
-   **Interactive UI**: Uses `lucide-react` for icons and `tailwindcss` for styling.

## Prerequisites

-   Node.js (v14 or higher recommended)
-   npm or yarn

## Installation

1.  Navigate to the frontend directory:
    ```bash
    cd frontend
    ```

2.  Install dependencies:
    ```bash
    npm install
    ```

## Running the Application

1.  Ensure the backend API is running on `http://localhost:8000` (see [Backend README](../backend/README.md)).

2.  Start the development server:
    ```bash
    npm start
    ```

3.  Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

## Build

To build the app for production to the `build` folder:

```bash
npm run build
```

## Configuration

The application currently expects the backend API to be available at `http://localhost:8000`.
