from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import os
from supabase import create_client
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeVectorStore
from pinecone import Pinecone

# ==============================
# 환경 설정
# ==============================

from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

pc = Pinecone(api_key=PINECONE_API_KEY)
index_name = "recipes"
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
vector_store = PineconeVectorStore.from_existing_index(index_name, embeddings)

app = FastAPI(
    title="ChefGPT. The best provider of Indian Recipes in the world",
    description="Give ChefGPT the name of an ingredient and it will give you multiple recipes to use that ingredient on in return.",
    servers=[
        {"url": "https://chefgpt-bdfc.onrender.com"}
    ]
)

bearer_scheme = HTTPBearer()

# ==============================
# 데이터 모델
# ==============================

class Document(BaseModel):
    page_content: str

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

class User(BaseModel):
    github_id: str
    email: str
    name: str

# ==============================
# API 엔드포인트
# ==============================

@app.get("/", response_class=JSONResponse)
def root():
    return {"message": "Welcome to the Cooking recipes API!"}

# ✅ GitHub 로그인 및 Supabase 유저 저장
@app.get("/auth", response_model=User)
def github_auth(authorization: HTTPAuthorizationCredentials = Security(bearer_scheme)):
    github_token = authorization.credentials
    user_info_resp = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {github_token}"}
    )
    if user_info_resp.status_code != 200:
        raise HTTPException(status_code=403, detail="Invalid GitHub token")
    user_info = user_info_resp.json()
    github_id = user_info["id"]
    email = user_info.get("email") or "no-email@example.com"
    name = user_info.get("name") or "No Name"

    existing_user = supabase.table("users").select("*").eq("github_id", github_id).execute()

    if not existing_user.data:
        supabase.table("users").insert({
            "github_id": github_id,
            "email": email,
            "name": name
        }).execute()

    return User(github_id=str(github_id), email=email, name=name)

# ✅ 레시피 검색
@app.get("/recipes", response_model=list[Document])
async def get_receipt(ingredient: str):
    try:
        docs = vector_store.similarity_search(ingredient, k=5)
        return [{"page_content": doc.page_content} for doc in docs]
    except Exception as e:
        print("🔥 Error during recipe search:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

# ✅ 레시피 저장
@app.post("/recipes/save")
def save_recipe(request: RecipeSaveRequest, authorization: HTTPAuthorizationCredentials = Security(bearer_scheme)):
    github_token = authorization.credentials
    user_info_resp = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {github_token}"}
    )
    if user_info_resp.status_code != 200:
        raise HTTPException(status_code=403, detail="Invalid GitHub token")
    github_id = user_info_resp.json()["id"]
    supabase.table("favorite_recipes").insert({
        "user_id": github_id,
        "recipe_id": request.recipe_id,
        "recipe_name": request.recipe_name,
        "recipe_detail": request.recipe_detail
    }).execute()
    return {"message": "Recipe saved successfully."}

# ✅ 저장한 레시피 조회
@app.get("/recipes/favorites", response_model=list[FavoriteRecipe])
def get_favorite_recipes(authorization: HTTPAuthorizationCredentials = Security(bearer_scheme)):
    github_token = authorization.credentials
    user_info_resp = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {github_token}"}
    )
    if user_info_resp.status_code != 200:
        raise HTTPException(status_code=403, detail="Invalid GitHub token")
    github_id = user_info_resp.json()["id"]
    result = supabase.table("favorite_recipes").select("*").eq("user_id", github_id).execute()
    return result.data