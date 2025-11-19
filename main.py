from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langfuse import observe
from dotenv import load_dotenv
import os
from datetime import datetime
from typing import List

from models import CustomerInfo
# from utils import customer_text, create_persona_prompt
from utils_modified import customer_text, create_persona_prompt

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ----------------------
# Load environment variables
# ----------------------
load_dotenv()

# ----------------------
# LLM setup
# ----------------------
llm = ChatOpenAI(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.8,
    model_name="gpt-5-nano"
)


@app.get("/", response_class=HTMLResponse)
async def show_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

# ----------------------
# Endpoint
# ----------------------
@app.post("/persona/", response_class=HTMLResponse)
@observe()  # Langfuse observation decorator for monitoring 
def generate_persona(
    request: Request,
    name: str = Form(...),
    gender: str = Form(...),
    age: int = Form(...),
    occupation: str = Form(...),
    occupation_field: str = Form(...),
    income: float = Form(...),
    insurance_type: List[str] = Form([]),
    insurance_coverage: float = Form(None)
):
    # Step 1: Convert list of insurance types to comma-separated string
    insurance_type_str = ", ".join(insurance_type) if insurance_type else None
    
    # Step 2: Create CustomerInfo object
    customer = CustomerInfo(
        name=name,
        gender=gender,
        age=age,
        occupation=occupation,
        occupation_field=occupation_field,
        income=income,
        insurance_type=insurance_type_str,
        insurance_coverage=insurance_coverage
    )
    
    # Step 3: Create customer text summary
    text_summary = customer_text(customer)

    # Step 4: Build prompt
    prompt_str = create_persona_prompt(text_summary)
    
    # Step 5: Build LCEL chain
    chain = (
        PromptTemplate.from_template(
            prompt_str
        )
        | llm
    )

    # Step 6: Run chain with Langfuse callback
    result = chain.invoke({"text_summary": text_summary})
    
    # Step 7: Extract the AI-generated text from result
    persona_text = result.content if hasattr(result, 'content') else str(result)

    # Step 8: Render the result template
    return templates.TemplateResponse("result.html", {
        "request": request,
        "customer_text": text_summary,
        "persona_result": persona_text,
        "timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p")
    })
