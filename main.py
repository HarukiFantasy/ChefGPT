from dotenv import load_dotenv
import os
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone 
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from typing import List
from pydantic import BaseModel

# 환경변수 로드
load_dotenv()

# Pinecone 초기화
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("recipes")

# OpenAI Embeddings
embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

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
    # 1. 임베딩 변환
    query_vector = embeddings.embed_query(ingredient)
    # 2. Pinecone에서 유사 벡터 검색
    result = index.query(vector=query_vector, top_k=5, include_metadata=True)
    # 3. 결과 정제 (메타데이터에서 text 추출)
    docs = [{"page_content": match["metadata"]["text"]} for match in result["matches"]]
    return docs
