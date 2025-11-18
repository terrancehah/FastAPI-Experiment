from fastapi import FastAPI
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langfuse import observe
from dotenv import load_dotenv
import os

from models import CustomerInfo
from utils import customer_text, create_persona_prompt

app = FastAPI()

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

# ----------------------
# Endpoint
# ----------------------
@app.post("/persona/")
@observe()
def generate_persona(customer: CustomerInfo):
    # Step 1: Create customer text summary
    text_summary = customer_text(customer)

    # Step 2: Build prompt
    prompt_str = create_persona_prompt(text_summary)
    
    # Step 3: Build LCEL chain
    chain = (
        PromptTemplate.from_template(
            prompt_str
        )
        | llm
    )

    # Step 4: Run chain with Langfuse callback
    result = chain.invoke({"text_summary": text_summary})

    return {
        "customer_text": text_summary,
        "persona_prompt": prompt_str,
        "persona_result": result
    }
