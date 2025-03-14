from dotenv import load_dotenv
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from supabase import create_client
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeVectorStore
from pinecone import Pinecone

# ==============================
# 환경 설정
# ==============================

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

pc = Pinecone(api_key=PINECONE_API_KEY)
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
vector_store = PineconeVectorStore.from_existing_index("recipes", embeddings)

app = FastAPI(
    title="ChefGPT. The best provider of Indian Recipes in the world",
    description="Give ChefGPT the name of an ingredient and it will give you multiple recipes to use that ingredient on in return.",
    servers=[
        {"url": "https://chefgpt-bdfc.onrender.com"}
    ]
)

class Document(BaseModel):
    page_content: str

@app.get("/", response_class=JSONResponse)
def root():
    return {"message": "Welcome to the Cooking recipes API!"}

@app.get("/recipes", response_model=list[Document])
async def get_receipt(ingredient: str):
    try:
        docs = vector_store.similarity_search(ingredient, k=5)
        return [{"page_content": doc.page_content} for doc in docs]
    except Exception as e:
        print("🔥 Error during recipe search:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)
