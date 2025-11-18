from pydantic import BaseModel
from typing import Optional

from models import CustomerInfo

# ----------------------
# Functions
# ----------------------
def customer_text(c: CustomerInfo) -> str:
    
    '''
    Default values if not provided:
    gender -> 'UNDISCLOSED'
    occupation -> 'UNDISCLOSED'
    occupation_field -> 'UNDISCLOSED'
    income -> 'UNDISCLOSED'
    age -> 'UNDISCLOSED'
    insurance_type-> 'UNDISCLOSED'
    insurance_coverage -> 'UNDISCLOSED'
    
    '''
    # Tell about pronouns
    if isinstance(c.gender, str):
        gender = c.gender.lower();
    else:
        gender = 'other'
    if gender == 'male':
        pronounce = 'he'
        pronounce2 = 'his'
    elif gender == 'female':
        pronounce = 'she'
        pronounce2 = 'her'
    
    # Tell about career stage
    #if str(occupation).upper() == 'RETIREE':
        text+=f'{pronounce} is retired. '
    
    
    # if str(occupation_field).lower() in ['student', 'unemployed', 'retired']:
    #     occupation_field = 'N/A' 
    # else:
    #     occupation_field = c.occupation_field
    
    
#def infer_career_stage(occupation: str, age: int) -> str:occupation = (occupation or "").lower()

        # Career based rules
    
    if c.insurance_type and c.insurance_coverage:
        insurance = f"Currently, {pronounce} has active insurance {c.insurance_type} with coverage {c.insurance_coverage}."
    elif c.insurance_type:
        insurance = f"Currently, {pronounce} has active insurance {c.insurance_type}."
    else:
        insurance = f"Currently, {pronounce} has no active insurance."

    return (
        f"{c.name} is a {c.gender} aged {c.age}, working as {c.occupation} in {c.occupation_field}. "
        f"{pronounce2.capitalize()}'s income is {c.income}. {insurance}"
    )


def create_persona_prompt(text_summary: str) -> str:
    return f"""
You are an expert insurance advisor creating a customer persona to assess insurance needs.
Customer Information: {text_summary}

Based on this, generate a detailed persona summary explain the persona personality, interest, possible life vision, personality, interest, possible life vision,
with potential insurance product needs such as saving, medical, legacy, investment, education, and retirement
and rationales for each. Conclude also on takaful preference. 

Based on product holdings, if all the product is takaful and customer is Malay or Islam then we can conclude the customer prefer takaful product. 
Else if customer has no takaful product or not Malay or not Muslim, customer is okay with no takaful product.

Also list out active and non-active insurance product the customer have.

Side Note: Product Smart Golden Life can be consider as type retirement and type saving.

Limit it to 400 words. Make it in one paragraph essay, no bullet point. Return in English language only.
"""