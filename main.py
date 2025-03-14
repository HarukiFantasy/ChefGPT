from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import jwt
import os
from supabase import create_client
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeVectorStore
from pinecone import Pinecone

# ==============================
# 기본 환경설정
# ==============================

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Pinecone 및 OpenAI 임베딩 초기화
pc = Pinecone(api_key=PINECONE_API_KEY)
index_name = "recipes"
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
vector_store = PineconeVectorStore.from_existing_index(index_name, embeddings)

# FastAPI 앱 초기화
app = FastAPI(
    title="ChefGPT. The best provider of Indian Recipes in the world",
    description="Give ChefGPT the name of an ingredient and it will give you multiple recipes to use that ingredient on in return.",
    servers=[
        {"url": "https://chefgpt-bdfc.onrender.com"}
    ]
)

# JWT 인증 스키마
bearer_scheme = HTTPBearer()

# ==============================
# 데이터 모델
# ==============================

class Document(BaseModel):
    page_content: str

class UserInfo(BaseModel):
    id: str
    email: str
    name: str
    github_id: str

class RecipeSaveRequest(BaseModel):
    recipe_id: str
    recipe_name: str
    recipe_detail: str

class FavoriteRecipe(BaseModel):
    id: str
    recipe_id: str
    recipe_name: str
    recipe_detail: str
    created_at: str

# ==============================
# 유틸 함수 (JWT 기반 유저 인증)
# ==============================

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)):
    token = credentials.credentials
    payload = jwt.decode(token, options={"verify_signature": False})  # 개발용: 서명 검증 off (운영에서는 반드시 검증)
    return payload["sub"]  # Supabase의 user_id (UUID)

# ==============================
# 엔드포인트
# ==============================

# 기본 루트
@app.get("/", response_class=JSONResponse)
def root():
    return {"message": "Welcome to the Cooking recipes API!"}


# ✅ 레시피 검색 API
@app.get("/recipes", response_model=list[Document])
async def get_receipt(ingredient: str):
    try:
        docs = vector_store.similarity_search(ingredient, k=5)
        return [{"page_content": doc.page_content} for doc in docs]
    except Exception as e:
        print("🔥 Error during recipe search:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ✅ 유저 저장 API
@app.post("/save-user")
def save_user(user_info: UserInfo):
    user_id = user_info.id
    email = user_info.email
    name = user_info.name
    github_id = user_info.github_id

    existing_user = supabase.table("users").select("*").eq("id", user_id).execute()

    if len(existing_user.data) == 0:
        supabase.table("users").insert({
            "id": user_id,
            "email": email,
            "name": name,
            "github_id": github_id
        }).execute()
        return {"message": "User saved"}
    else:
        return {"message": "User already exists"}


# ✅ 레시피 저장 API (유저가 좋아요 한 레시피 저장)
@app.post("/recipes/save")
def save_recipe(request: RecipeSaveRequest, user_id: str = Depends(get_current_user)):
    supabase.table("favorite_recipes").insert({
        "user_id": user_id,
        "recipe_id": request.recipe_id,
        "recipe_name": request.recipe_name,
        "recipe_detail": request.recipe_detail
    }).execute()
    return {"message": "Recipe saved"}


# ✅ 유저가 저장한 레시피 조회 API
@app.get("/recipes/favorites", response_model=list[FavoriteRecipe])
def get_favorite_recipes(user_id: str = Depends(get_current_user)):
    result = supabase.table("favorite_recipes").select("*").eq("user_id", user_id).execute()
    return result.data
