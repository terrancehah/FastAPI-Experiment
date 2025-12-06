from pydantic import BaseModel, Field
from typing import Optional, List

# ----------------------
# Pydantic Model
# ----------------------
class CustomerInfo(BaseModel):
    name: str
    gender: str
    occupation: str
    occupation_field: str
    income: float
    age: int
    insurance_type: Optional[str] = None
    insurance_coverage: Optional[float] = None

class StudentInfo(BaseModel):
    name: str
    gender: str
    form: str
    school: str
    preferred_language: str
    favourite_subjects: List[str]
    study_frequency: str

# --- New Structured Output Models ---

class LearningMethod(BaseModel):
    """Details for a specific learning method recommendation."""
    method_name: str = Field(..., description="Name of the learning method (e.g., 'Feynman Technique', 'Mnemonics')")
    rationale: str = Field(..., description="Why this method fits this specific student's profile.")
    example: str = Field(..., description="A concrete example of applying this method to the student's subjects.")
    icon: str = Field(..., description="A single emoji icon representing this method (e.g., 🧠, 🧩).")

class PersonaAnalysis(BaseModel):
    """Complete analysis of the student persona and learning recommendations."""
    thinking_process: str = Field(..., description="The step-by-step reasoning process used to analyze the student.")
    student_persona: str = Field(..., description="A concise paragraph describing the student's personality, study preferences, and life vision.")
    language_preference: str = Field(..., description="Conclusion on the primary studying language based on the rules.")
    learning_methods: List[LearningMethod] = Field(..., description="A list of 6 recommended learning methods.")
