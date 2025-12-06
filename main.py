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
from models import StudentInfo, PersonaAnalysis
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
    <div class="results-container show results-wide" id="resultsContainer">
        <div id="successContainer" style="display: block;">
            
            <!-- Stepper Progress -->
            <div class="stepper-container">
                <div class="stepper">
                    <div class="step completed" id="step-received">
                        <div class="step-circle">1</div>
                        <div class="step-label">Received</div>
                    </div>
                    <div class="step active" id="step-thinking">
                        <div class="step-circle">2</div>
                        <div class="step-label">Thinking</div>
                    </div>
                    <div class="step" id="step-generating">
                        <div class="step-circle">3</div>
                        <div class="step-label">Generating</div>
                    </div>
                    <div class="step" id="step-complete">
                        <div class="step-circle">4</div>
                        <div class="step-label">Complete</div>
                    </div>
                </div>
            </div>

            <!-- Student Summary Box (Visible during Thinking) -->
            <div id="studentSummaryBox" class="student-summary-box" style="display:none">
                <h4><span class="icon">📄</span> Student Profile Summary</h4>
                <div id="studentSummaryContent"></div>
            </div>
            
            <!-- Dashboard Grid Result -->
            <div id="dashboardContainer"></div>
            
            <!-- Timestamp & Controls -->
            <div class="result-timestamp" id="resultTimestamp" style="display: none;"></div>
            
            <button class="btn-restart" onclick="window.location.reload()" id="restartBtn" style="display: none;">Generate Another Persona</button>
            
            <!-- Error Container -->
            <div id="errorContainer"></div>
        </div>
    </div>

    <!-- SSE Connection Manager (Hidden) -->
    <div id="sse-connection" hx-ext="sse" sse-connect="{stream_url}">
        <!-- We use a custom script to handle the complex logic of sorting content into reasoning vs dashboard -->
        <div sse-swap="token" hx-target="#dashboardContainer" hx-swap="beforeend"></div>
        
        <!-- CRITICAL FIX: We must swap the scripts into the DOM for them to execute -->
        <div sse-swap="stage" hx-target="body" hx-swap="beforeend"></div> 
        
        <!-- Close stream when done -->
        <div sse-swap="done" hx-target="#sse-connection" hx-swap="outerHTML"></div>
        <div sse-swap="error" hx-target="#errorContainer" hx-swap="innerHTML"></div>
    </div>

    <script>
        // Custom event listener for SSE stage updates to drive the stepper
        document.body.addEventListener('htmx:sseMessage', function(e) {{
            if (e.detail.type === 'stage') {{
                // Parse the data manually since HTMX sse-swap handles the DOM swap but we need logic
                // The data comes as HTML string <div...>...</div>. We can regex it or just assume sequence.
                // Simpler: We update stepper based on message content or just timing. 
                // Actually, best way is to have the server send a script to update UI.
                // For now, let's rely on the server sending <script> tags in the events.
            }}
        }});
    </script>
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
            # 1. RECEIVED -> THINKING
            yield """event: stage
data: <script>document.getElementById('step-received').classList.add('completed'); document.getElementById('step-thinking').classList.add('active');</script>

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
            
            # Start Generation
            prompt_str = create_persona_prompt(text_summary)
            
            # --- PHASE 1: THINKING (Show Summary) ---
            # Since native reasoning tokens are hidden, we display the input summary
            # to give context while the user waits.
            
            # Use json.dumps to safely escape the string for JS injection
            summary_html = text_summary.replace('\n', '<br>')
            safe_summary_json = json.dumps(summary_html)
            
            yield f"""event: stage
data: <script>
    console.log('Attempting to show student summary...');
    var box = document.getElementById('studentSummaryBox');
    var content = document.getElementById('studentSummaryContent');
    if (box && content) {{
        box.style.display = 'block';
        content.innerHTML = '<strong>Summary being analyzed:</strong><br>' + {safe_summary_json} + '<br><br><em>Generating persona...</em>';
        console.log('Summary shown.');
    }} else {{
        console.error('Could not find summary box elements');
    }}
</script>

"""
            # Force flush to ensure UI updates before blocking operation
            await asyncio.sleep(0.2)

            # --- PHASE 2: STRUCTURED DATA (JSON) ---
            # We use standard structured output. 
            structured_llm = llm.with_structured_output(PersonaAnalysis)
            
            structured_chain = (
                PromptTemplate.from_template("{prompt_str}")
                | structured_llm
            )
            
            # This will block while the model thinks/generates
            analysis_result = await structured_chain.ainvoke({
                "prompt_str": prompt_str
            })
            
            # Update Stepper: Thinking -> Generating -> Complete
            # We skip the "Generating" visual step practically since it arrives instantly after blocking
            # AND we DELETE the summary box now.
            yield """event: stage
data: <script>
document.getElementById('step-thinking').classList.remove('active'); 
document.getElementById('step-thinking').classList.add('completed'); 
document.getElementById('step-generating').classList.add('active');
var summaryBox = document.getElementById('studentSummaryBox');
if(summaryBox) summaryBox.remove();
</script>

"""
            
            # --- PHASE 3: RENDER HTML ---
            # We use Jinja2 to render the dashboard template with the data
            dashboard_html = templates.get_template("_dashboard.html").render(analysis=analysis_result)
            
            # Minify slightly to send over wire
            dashboard_html = dashboard_html.replace('\n', ' ')
            
            # Send the final HTML to the dashboard container
            yield f"event: token\ndata: {dashboard_html}\n\n"
            
            # 4. COMPLETE
            elapsed = 0 
            timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
                         
            yield f"""event: done
data: <div id="sse-connection-closed"></div><script>document.getElementById('step-generating').classList.remove('active'); document.getElementById('step-generating').classList.add('completed'); document.getElementById('step-complete').classList.add('completed'); document.getElementById('resultTimestamp').innerHTML = 'Generated on {timestamp}'; document.getElementById('resultTimestamp').style.display='block'; document.getElementById('restartBtn').style.display='block';</script>

"""
            
            # 4. COMPLETE
            elapsed = 0 # We could track this if needed
            timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
                         
            yield f"""event: done
data: <div id="sse-connection-closed"></div><script>document.getElementById('step-generating').classList.remove('active'); document.getElementById('step-generating').classList.add('completed'); document.getElementById('step-complete').classList.add('completed'); document.getElementById('resultTimestamp').innerHTML = 'Generated on {timestamp}'; document.getElementById('resultTimestamp').style.display='block'; document.getElementById('restartBtn').style.display='block';</script>

"""
                    
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