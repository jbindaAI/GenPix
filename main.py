from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from openai import OpenAI
import openai
import requests
import uuid
import time
from pathlib import Path
import os


# Creating cache folder:
Path("gen_images/").mkdir(parents=True, exist_ok=True)


client = OpenAI()

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


def clean_expired_images():
    '''
    Function deletes expired images.
    Is activated as a background process when number of images in a cache exceeds 50.
    '''
    EXPIRATION_TIME = 24 # in hours
    for filename in os.listdir("gen_images"):
        current_time = time.time()
        expiry_period_secs = EXPIRATION_TIME * 3600
        filepath = os.path.join("gen_images", filename)
        file_creation_time = os.path.getctime(filepath)
        if current_time - file_creation_time > expiry_period_secs:
            os.remove(filepath)
            print(f"Deleted expired image: {filename}")
    return 1


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        name="home.html", request=request)


@app.post("/generate", response_class=HTMLResponse)
async def generate(request: Request,
                   background_tasks: BackgroundTasks,
                   prompt: str = Form(),
                   size: str = Form()
                   ):
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality="standard",
            n=1,
            )
        image_url = response.data[0].url
        image_filename = f"gen_img_{uuid.uuid4()}.png"
        image_response = requests.get(image_url)

        with open("gen_images/"+image_filename, "wb") as file:
            file.write(image_response.content)

        context = {
            "image_url": image_url,
            "image_filename": image_filename
            }

    except openai.OpenAIError as e:
        print(e)
        context = {}

    if len(os.listdir("gen_images/")) > 50:
        background_tasks.add_task(clean_expired_images)

    return templates.TemplateResponse(name="results.html", request=request, context=context)


@app.get("/download_image/{image_filename}")
def download_image(image_filename: str):
    return FileResponse(path="gen_images/"+image_filename, 
                        media_type='image/png',
                        filename=image_filename,
                        headers={"Content-Disposition": f"attachment; filename={image_filename}"}
                        )