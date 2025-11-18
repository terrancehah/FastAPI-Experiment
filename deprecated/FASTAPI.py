from fastapi import FastAPI
from langchain.chains import LLMChain #prob
from langchain.prompts import PromptTemplate #prob
from langchain.llms import OpenAI #prob
from langfuse import Langfuse 
from langfuse import LangfuseCallbackHandler
import os

from .main import CustomerInfo, customer_text, create_persona_prompt

app = FastAPI()

# ----------------------
# Langfuse setup
# ----------------------
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://api.langfuse.com")
)
lf_callback = LangfuseCallbackHandler(langfuse=langfuse)

# ----------------------
# LLM setup
# ----------------------
llm = OpenAI(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.2,
    model_name="gpt-4o"
)

# ----------------------
# Endpoint
# ----------------------
@app.post("/persona/")
def generate_persona(customer: CustomerInfo):
    # Step 1: Create customer text summary
    text_summary = customer_text(customer)

    # Step 2: Build prompt
    prompt_str = create_persona_prompt(text_summary)
    prompt = PromptTemplate(input_variables=["text_summary"], template=prompt_str)

    # Step 3: Build LCEL chain
    chain = LLMChain(llm=llm, prompt=prompt)

    # Step 4: Run chain with Langfuse callback
    result = chain.run({"text_summary": text_summary}, callbacks=[lf_callback])

    # Step 5: Flush Langfuse traces
    langfuse.flush()

    return {
        "customer_text": text_summary,
        "persona_prompt": prompt_str,
        "persona_result": result
    }
