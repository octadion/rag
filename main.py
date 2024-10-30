from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import click, warnings, uvicorn
from server.api.v1.assistant.handler.delete_handler import router as delete_router
from server.api.v1.assistant.handler.get_handler import router as get_router
from server.api.v1.assistant.handler.post_handler import router as post_router
from server.api.v1.assistant.handler.upload_handler import router as upload_router
from server.api.v1.user.handler.post_handler import router as user_post_router
from server.api.v1.assistant.workflows.chat_handler import router as chat_router

app = FastAPI()

app.include_router(post_router, prefix="/api/v1/assistant", tags=["Assistant"])
app.include_router(get_router, prefix="/api/v1/assistant", tags=["Assistant"])
app.include_router(upload_router, prefix="/api/v1/assistant", tags=["Assistant"])
app.include_router(delete_router, prefix="/api/v1/assistant", tags=["Assistant"])
app.include_router(chat_router, prefix="/api/v1/assistant", tags=["Chat"])
app.include_router(user_post_router, prefix="/api/v1/user", tags=["User"])

@click.command()
@click.option('--host', default='0.0.0.0', help='Host address (default: 0.0.0.0)')
@click.option('--port', default=1111, help='Port number (default: 1111)')

def runserver(host, port):
    print(f'Starting server at http://{host}:{port}')
    warnings.warn(
        "This command will start the server in development mode, do not use it in production."
    )
    uvicorn.run("main:app", host=host, port=port, reload=True, log_level="debug", loop="asyncio")

if __name__ == "__main__":
    runserver()
