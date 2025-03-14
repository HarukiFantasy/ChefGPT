from dotenv import load_dotenv
import os
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from typing import List
from pydantic import BaseModel


load_dotenv()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = "recipes"
embeddings = OpenAIEmbeddings()
vectore_store = Pinecone(index_name=index_name, embedding=embeddings)
RenderURL = ""

app = FastAPI(
    title="ChefGPT. The best provider of Indian Recipes in the world",
    description="Give ChefGPT the name of an ingredient and it will give you multiple recipes to use that ingredient on in return.",
    servers=[
        {"url":RenderURL}
    ]
)

class Document(BaseModel):
    page_content: str

@app.get("/", response_class=JSONResponse)
def root():
    return {"message": "Welcome to the Cooking recipes API!"}

@app.get("/recipes", response_model=List[Document])
async def get_receipt(request: Request, ingredient: str):
    docs = vectore_store.similarity_search(ingredient)
    return docs