from fastapi import FastAPI, Request, Form, Query
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
from utils import student_text, create_persona_prompt, SUBJECTS_LIST

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
    # gpt-5-nano is the latest model from OpenAI in December 2025, do not attempt to change this
    streaming=True
)


@app.get("/", response_class=HTMLResponse)
async def show_form(request: Request):
    return templates.TemplateResponse("form.html", {
        "request": request,
        "subjects": SUBJECTS_LIST
    })

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
# HTMX Streaming Endpoints
# ----------------------
@app.get("/persona/htmx-setup", response_class=HTMLResponse)
async def htmx_setup(
    request: Request,
    name: str = Query(...),
    gender: str = Query(...),
    form: str = Query(...),
    school: str = Query(...),
    preferred_language: str = Query(...),
    favourite_subjects: Optional[List[str]] = Query(None),
    study_frequency: str = Query(...)
):
    # Construct the query string for the stream
    from urllib.parse import urlencode
    
    params = {
        "name": name,
        "gender": gender,
        "form": form,
        "school": school,
        "preferred_language": preferred_language,
        "study_frequency": study_frequency
    }
    
    # Helper to build URL with list params
    query_string = urlencode(params)
    if favourite_subjects:
        for subject in favourite_subjects:
            query_string += f"&favourite_subjects={subject}"
            
    stream_url = f"/persona/stream-htmx?{query_string}"
    
    return f"""
    <div class="results-container show" id="resultsContainer">
        <div id="successContainer" style="display: block;">
            <div class="success-badge" id="successBadge" style="display: none;">✓</div>
            <h1 id="resultTitle">Generating Student Persona...</h1>
            
            <!-- Summary Section -->
            <div class="result-section" id="summarySection" style="display: none;">
                <div class="result-section-title">Student Summary</div>
                <div class="result-section-content student-summary"></div>
            </div>

            <!-- Status Indicator -->
            <div class="status-indicator-container" id="statusIndicatorContainer">
                <div class="status-icon pulse">📤</div>
                <div class="status-message">Initializing stream...</div>
                <div class="status-detail">Preparing connection...</div>
            </div>
            
            <!-- Persona Result -->
            <div class="result-section">
                <div class="result-section-title">AI-Generated Persona & Learning Recommendations</div>
                <div class="result-section-content persona-result">
                    <span id="personaContent"></span>
                    <span class="typing-cursor" id="typingCursor"></span>
                </div>
            </div>
            
            <!-- Timestamp -->
            <div class="result-timestamp" id="resultTimestamp" style="display: none;"></div>
            
            <button class="btn-restart" onclick="window.location.reload()" id="restartBtn" style="display: none;">Generate Another Persona</button>
            
            <!-- Error Container -->
            <div id="errorContainer"></div>
        </div>
    </div>

    <!-- SSE Connection Manager (Hidden) -->
    <!-- We separate this so we can kill the connection by removing this element -->
    <div id="sse-connection" hx-ext="sse" sse-connect="{stream_url}">
        <div sse-swap="token" hx-target="#personaContent" hx-swap="beforeend"></div>
        <div sse-swap="stage" hx-target="#statusIndicatorContainer" hx-swap="innerHTML"></div>
        <div sse-swap="summary" hx-target="#summarySection" hx-swap="innerHTML"></div>
        
        <!-- When done, we replace this connection container to kill the stream -->
        <div sse-swap="done" hx-target="#sse-connection" hx-swap="outerHTML"></div>
        
        <div sse-swap="error" hx-target="#errorContainer" hx-swap="innerHTML"></div>
    </div>
    """

@app.get("/persona/stream-htmx")
@observe()
async def generate_persona_stream_htmx(
    request: Request,
    name: str = Query(...),
    gender: str = Query(...),
    form: str = Query(...),
    school: str = Query(...),
    preferred_language: str = Query(...),
    favourite_subjects: Optional[List[str]] = Query(None),
    study_frequency: str = Query(...)
):
    async def generate_stream():
        try:
            # Yield initial stage
            yield """event: stage
data: <div class="status-icon rotate">🔄</div><div class="status-message">Processing student information...</div><div class="status-detail">Analyzing profile...</div>

"""
            
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
            
            text_summary = student_text(student)
            
            # Yield summary
            # We combine lines to ensure data: prefix covers everything
            yield f"""event: summary
data: <div class="result-section-title">Student Summary</div><div class="result-section-content student-summary">{text_summary}</div><script>document.getElementById('summarySection').style.display='block';</script>

"""
            
            event_queue = asyncio.Queue()
            callback = SimpleStreamingCallback(event_queue)
            
            prompt_str = create_persona_prompt(text_summary)
            chain = PromptTemplate.from_template(prompt_str) | llm
            
            async def run_chain():
                try:
                    async for _ in chain.astream(
                        {"text_summary": text_summary},
                        config={'callbacks': [callback]}
                    ):
                        pass
                except Exception as e:
                    await event_queue.put({'type': 'error', 'message': str(e)})

            task = asyncio.create_task(run_chain())
            
            while not task.done() or not event_queue.empty():
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    
                    if event['type'] == 'token':
                        content = event['content'].replace('\n', '<br>')
                        # Wrap in span to preserve leading spaces from SSE trimming
                        yield f"event: token\ndata: <span class='t'>{content}</span>\n\n"
                        
                    elif event['type'] == 'stage':
                        stage = event['stage']
                        msg = event.get('message', '')
                        
                        if stage == 'thinking':
                            yield f"""event: stage
data: <div class="status-icon pulse">🧠</div><div class="status-message">{msg}</div>

"""
                        elif stage == 'streaming':
                            yield f"""event: stage
data: <div class="status-icon pulse">⚡</div><div class="status-message">{msg}</div>

"""
                        elif stage == 'complete':
                            elapsed = event.get('elapsed', 0)
                            timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
                            
                            yield f"""event: stage
data: <div class="status-icon complete">✅</div><div class="status-message">Complete!</div><div class="status-detail">Generated in {elapsed:.1f}s</div>

"""
                            # Send done signal which will replace the connection container
                            # This effectively closes the SSE connection
                            yield f"""event: done
data: <div id="sse-connection-closed"></div><script>document.getElementById('resultTimestamp').innerHTML = 'Generated on {timestamp}';document.getElementById('resultTimestamp').style.display='block';document.getElementById('successBadge').style.display='block';document.getElementById('restartBtn').style.display='block';document.getElementById('typingCursor').style.display='none';document.getElementById('resultTitle').innerText='Student Persona Generated Successfully';</script>

"""
                            break
                            
                    elif event['type'] == 'error':
                         yield f"""event: error
data: <div class="error-container"><div class="error-title">Error</div><div class="error-message">{event['message']}</div></div>

"""
                         break
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    yield f"""event: error
data: Error: {str(e)}

"""
                    break
                    
        except Exception as e:
            yield f"""event: error
data: Error: {str(e)}

"""

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

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