# Student Persona Generator

A FastAPI application that generates detailed student personas using AI (OpenAI GPT). 
It collects student information via a web form and uses LangChain to generate a streaming response of a student persona.
**Langfuse** is integrated for monitoring and tracing LLM executions.

## Setup & Running

1.  **Activate Virtual Environment**
    ```bash
    source venv/bin/activate   # macOS/Linux
    venv\Scripts\activate      # Windows
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Setup**
    Create a `.env` file with your API keys:
    ```env
    OPENAI_API_KEY=...
    LANGFUSE_SECRET_KEY=...
    LANGFUSE_PUBLIC_KEY=...
    LANGFUSE_HOST=https://cloud.langfuse.com
    ```

4.  **Run the Application**
    ```bash
    uvicorn main:app --reload
    ```

The application will be available at `http://127.0.0.1:8000`.
