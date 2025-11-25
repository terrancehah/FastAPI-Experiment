# Student Persona Generator

A FastAPI application that generates detailed student personas using AI (OpenAI GPT). It collects student information via a web form and uses LangChain to generate a narrative persona.

## Setup & Running

1.  **Activate Virtual Environment**

    ```bash
    source venv/bin/activate
    ```

2.  **Install Dependencies** (if not already installed)

    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Application**
    ```bash
    uvicorn main:app --reload
    ```

The application will be available at `http://127.0.0.1:8000`.
