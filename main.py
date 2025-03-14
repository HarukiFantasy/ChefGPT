from dotenv import load_dotenv
import os
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec 
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from typing import List
from pydantic import BaseModel

# 환경변수 로드
load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = "recipes"
# OpenAI Embedding (langchain)
embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))
# Vector Store (langchain + Pinecone)
vector_store = PineconeVectorStore.from_existing_index("recipes", embeddings)


# FastAPI 인스턴스
RenderURL = "https://chefgpt-bdfc.onrender.com"

app = FastAPI(
    title="ChefGPT. The best provider of Indian Recipes in the world",
    description="Give ChefGPT the name of an ingredient and it will give you multiple recipes to use that ingredient on in return.",
    servers=[
        {"url": "https://chefgpt-bdfc.onrender.com"}
    ]
)

# 데이터 타입
class Document(BaseModel):
    page_content: str

# 라우트
@app.get("/", response_class=JSONResponse)
def root():
    return {"message": "Welcome to the Cooking recipes API!"}

# 유사 검색 API
@app.get("/recipes", response_model=List[Document])
async def get_receipt(request: Request, ingredient: str):
    try:
        docs = vector_store.similarity_search(ingredient, k=5)
        return [{"page_content": doc.page_content} for doc in docs]
    except Exception as e:
        print("🔥 Error during recipe search:", str(e))  # 로그로 남기기
        return JSONResponse(content={"error": str(e)}, status_code=500)
