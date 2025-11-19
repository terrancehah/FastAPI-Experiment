from pydantic import BaseModel
from typing import Optional
from models import CustomerInfo
from datetime import datetime

def customer_text(c: CustomerInfo) -> str:
    """
    Default values if not provided:
    gender -> 'UNDISCLOSED'
    occupation -> 'UNDISCLOSED'
    occupation_field -> 'UNDISCLOSED'
    income -> 'UNDISCLOSED'
    age -> 'UNDISCLOSED'
    insurance_type-> 'UNDISCLOSED'
    insurance_coverage -> 'UNDISCLOSED'
    """

    # gender
    gender = (c.gender or "UNDISCLOSED").lower()
    if gender == "male":
        pronoun = "he"
        pronoun2 = "his"
    elif gender == "female":
        pronoun = "she"
        pronoun2 = "her"
    else:
        pronoun = "they"
        pronoun2 = "their"

    # age and generation
    if isinstance(c.age, (int, float)) and c.age > 0:
        born_year = datetime.now().year - c.age
        if born_year >= 2025:
            generation = "Generation Beta"
        elif born_year >= 2010:
            generation = "Generation Alpha"
        elif born_year >= 1997:
            generation = "Generation Z"
        elif born_year >= 1981:
            generation = "Generation Y (Millennial)"
        elif born_year >= 1965:
            generation = "Generation X"
        elif born_year >= 1946:
            generation = "Boomer Generation"
        else:
            generation = "Silent Generation"

        intro = (
            f"{c.name} is a {gender} born in {born_year}. "
            f"{pronoun.capitalize()} is currently {c.age} years old and is part of {generation}."
        )
    else:
        intro = f"{c.name} is a {gender} with an undisclosed age."

    # occupation
    occupation_text = ""
    occ = str(c.occupation).strip()

    if occ.upper() == "RETIREE":
        occupation_text = f" {pronoun.capitalize()} is currently retired."
    elif isinstance(c.age, (int, float)):
        if 50 <= c.age <= 60:
            occupation_text = f" {pronoun.capitalize()} is approaching retirement age."
        elif 40 < c.age < 50:
            occupation_text = f" {pronoun.capitalize()} is in the career advancement stage."
        elif 30 <= c.age <= 40:
            occupation_text = f" {pronoun.capitalize()} is in the career establishment stage."
        elif 20 <= c.age < 30:
            occupation_text = f" {pronoun.capitalize()} is in the career exploration stage."
        else:
            occupation_text = f" {pronoun.capitalize()} is not in the workforce yet."

    # If occupation is provided
    if occ.upper() not in ["UNDISCLOSED", "NAN", "RETIREE"]:
        occupation_text += f" {pronoun.capitalize()} works as a {c.occupation} in the field of {c.occupation_field}."

    # income
    if isinstance(c.income, (int, float)) and c.income > 0:
        income_text = f" {pronoun2.capitalize()} monthly income is RM{c.income:,.2f}."
    else:
        income_text = f" {pronoun2.capitalize()} income is not disclosed."

    # insurance 
    if c.insurance_type and c.insurance_coverage:
        insurance = f"Currently, {pronoun} has active insurance {c.insurance_type} with coverage RM{c.insurance_coverage}."
    elif c.insurance_type:
        insurance = f"Currently, {pronoun} has active insurance {c.insurance_type}."
    else:
        insurance = f"Currently, {pronoun} has no active insurance."
    
    # final
    paragraph = intro + occupation_text + income_text + insurance
    return paragraph

def create_persona_prompt(text_summary: str) -> str:
    return f"""
        
        You are an expert insurance advisor creating a customer persona to assess insurance needs.

        Customer Information: {text_summary}

        Based on the information above, generate a single-paragraph persona summary (maximum 400 words). Describe the customer’s possible personality, 
        interests, lifestyle outlook, and life vision. From this persona, infer potential insurance product needs, including saving, medical, legacy, investment, education, 
        and retirement solutions, and explain the rationale for each within the same paragraph.
        
        Apply this takaful preference rule:
        - If all existing products are takaful AND the customer is Malay or Muslim, conclude that the customer prefers takaful products.
        - Otherwise, conclude that the customer is open to non-takaful or conventional products.

        Within the same paragraph, also identify all active and non-active insurance products mentioned. 
        Note that “Smart Golden Life” should be treated as both a retirement and saving product.

        Do not use bullet points or separate sections. 
        Produce the output in English only, and do not add information not present in the customer data.
        
        """
