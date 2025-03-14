from dotenv import load_dotenv
import os
from langchain_community.embeddings import OpenAIEmbeddings
import pinecone
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from typing import List
from pydantic import BaseModel

# 환경변수 로드
load_dotenv()

# Pinecone 초기화
pinecone.init(
    api_key=os.getenv("PINECONE_API_KEY"),
    environment="us-east-1"  # 직접 하드코딩 가능
)

RenderURL = "https://chefgpt-bdfc.onrender.com"

# Pinecone 인덱스
index = pinecone.Index("recipes")  # 하드코딩 or os.getenv("PINECONE_INDEX_NAME")

# OpenAI Embeddings
embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

# FastAPI 인스턴스
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
    query_vector = embeddings.embed_query(ingredient)  # 텍스트를 벡터로
    result = index.query(vector=query_vector, top_k=5, include_metadata=True)  # Pinecone 검색
    docs = [{"page_content": item["metadata"]["text"]} for item in result["matches"]]  # 결과 정리
    return docs
