from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langfuse import observe
from dotenv import load_dotenv
import os
import asyncio
import json
from datetime import datetime
from typing import List, Optional
from langchain_core.callbacks import AsyncCallbackHandler


from models import StudentInfo
# from utils import customer_text, create_persona_prompt
from utils import student_text, create_persona_prompt

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
    model_name="gpt-5-nano",
    streaming=True
)


@app.get("/", response_class=HTMLResponse)
async def show_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

class SimpleStreamingCallback(AsyncCallbackHandler):
    """Minimal callback for stage indicators"""
    
    def __init__(self, event_queue):
        self.event_queue = event_queue
        self.word_count = 0
        self.start_time = None
    
    async def on_llm_start(self, serialized, prompts, **kwargs) -> None:
        self.start_time = datetime.now()
        await self.event_queue.put({
            'type': 'stage',
            'stage': 'thinking',
            'message': 'AI is analyzing your profile...'
        })
    
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        if self.word_count == 0:
            await self.event_queue.put({
                'type': 'stage',
                'stage': 'streaming',
                'message': 'Generating persona...'
            })
        
        # Count words
        if token.strip():
            self.word_count += len(token.split())
        
        # Send token
        await self.event_queue.put({
            'type': 'token',
            'content': token,
            'word_count': self.word_count
        })
    
    async def on_llm_end(self, response, **kwargs) -> None:
        elapsed = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        await self.event_queue.put({
            'type': 'stage',
            'stage': 'complete',
            'message': 'Complete!',
            'elapsed': elapsed
        })

# ----------------------
# Streaming Endpoint
# ----------------------
@app.post("/persona/stream/")
@observe()  # Langfuse observation decorator for monitoring
async def generate_persona_stream(
    request: Request,
    name: str = Form(...),
    gender: str = Form(...),
    form: str = Form(...),
    school: str = Form(...),
    preferred_language: str = Form(...),
    favourite_subjects: Optional[List[str]] = Form(None),
    study_frequency: str = Form(...)
):
    """Streaming version of persona generation for Vercel timeout handling"""
    
    async def generate_stream():
        try:
            # Stage 2: Processing
            yield f"data: {json.dumps({
                'type': 'stage',
                'stage': 'processing',
                'message': 'Processing student information...'
            })}\n\n"
            
            # Step 1: Create StudentInfo object
            subjects_list = favourite_subjects or []
            
            student = StudentInfo(
                name=name,
                gender=gender,
                form=form,
                school=school,
                preferred_language=preferred_language,
                favourite_subjects=subjects_list,
                study_frequency=study_frequency
            )
            
            # Step 2: Create student text summary
            text_summary = student_text(student)
            
            # Step 3: Send student summary
            yield f"data: {json.dumps({'type': 'summary', 'content': text_summary})}\n\n"
            
            # Step 4: Setup callback and queue
            event_queue = asyncio.Queue()
            callback = SimpleStreamingCallback(event_queue)
            
            # Step 5: Build prompt
            prompt_str = create_persona_prompt(text_summary)
            
            # Step 6: Build LCEL chain
            chain = (
                PromptTemplate.from_template(prompt_str)
                | llm
            )
            
            # Step 7: Run chain in background task
            async def run_chain():
                try:
                    # We use astream but rely on the callback for events
                    # We iterate to ensure execution, but ignore the direct chunks
                    # as the callback handles them
                    async for _ in chain.astream(
                        {"text_summary": text_summary},
                        config={'callbacks': [callback]}
                    ):
                        pass
                except Exception as e:
                    await event_queue.put({
                        'type': 'error',
                        'message': str(e)
                    })
                finally:
                    # Signal done if not already handled (though on_llm_end should handle it)
                    # We can send a sentinel if needed, but on_llm_end is better
                    pass

            task = asyncio.create_task(run_chain())
            
            # Step 8: Consume queue and yield events
            while not task.done() or not event_queue.empty():
                try:
                    # Wait for next event
                    event = await asyncio.wait_for(
                        event_queue.get(),
                        timeout=0.1
                    )
                    
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    # If complete or error, we can break after sending
                    if event['type'] == 'stage' and event['stage'] == 'complete':
                        # Send final done marker with timestamp
                        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
                        yield f"data: {json.dumps({'type': 'done', 'timestamp': timestamp})}\n\n"
                        break
                    
                    if event['type'] == 'error':
                        break
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    break
            
        except Exception as e:
            # Send error to client
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# # ----------------------
# # Fixed Endpoint (Deprecated, Kept for Backward Compatibility)
# # ----------------------
# @app.post("/persona/", response_class=HTMLResponse)
# @observe()  # Langfuse observation decorator for monitoring 
# def generate_persona(
#     request: Request,
#     name: str = Form(...),
#     gender: str = Form(...),
#     form: str = Form(...),
#     school: str = Form(...),
#     preferred_language: str = Form(...),
#     favourite_subjects: Optional[List[str]] = Form(None),
#     study_frequency: str = Form(...)
# ):

#     # Step 1: Create StudentInfo object
#     # Ensure favourite_subjects is a list (handle None case)
#     subjects_list = favourite_subjects or []
    
#     student = StudentInfo(
#         name=name,
#         gender=gender,
#         form=form,
#         school=school,
#         preferred_language=preferred_language,
#         favourite_subjects=subjects_list,
#         study_frequency=study_frequency
#     )
    
#     # Step 2: Create student text summary
#     text_summary = student_text(student)

#     # Step 3: Build prompt
#     prompt_str = create_persona_prompt(text_summary)
    
#     # Step 4: Build LCEL chain
#     chain = (
#         PromptTemplate.from_template(
#             prompt_str
#         )
#         | llm
#     )

#     # Step 5: Run chain with Langfuse callback
#     result = chain.invoke({"text_summary": text_summary})
    
#     # Step 6: Extract the AI-generated text from result
#     persona_text = result.content if hasattr(result, 'content') else str(result)

#     # Step 7: Render the result template
#     return templates.TemplateResponse("result.html", {
#         "request": request,
#         "student_text": text_summary,
#         "persona_result": persona_text,
#         "timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p")
#     })