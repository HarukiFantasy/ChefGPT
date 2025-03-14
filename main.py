from fastapi import FastAPI, Depends, HTTPException, Security, Request, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, RedirectResponse
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
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
OpenAI_redirectURI = "https://chat.openai.com/aip/g-4e89111e0545651f98621d5c78b25e5682a4bbbb/oauth/callback" 

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

@app.get("/auth")
def github_login(state: str):
    github_auth_url = (
        f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={OpenAI_redirectURI}&scope=read:user&state={state}"
    )
    return RedirectResponse(github_auth_url)

@app.post("/token", include_in_schema=False)
async def handle_oauth_token(code: str = Form(...)):
    token_url = "https://github.com/login/oauth/access_token"
    headers = {"Accept": "application/json"}
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": OpenAI_redirectURI
    }
    response = requests.post(token_url, headers=headers, data=payload)
    token_data = response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="GitHub access token not provided.")

    user_response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    user_data = user_response.json()
    github_id = user_data.get("id")
    email = user_data.get("email") or "no-email@example.com"
    name = user_data.get("login") or "No Name"

    existing_user = supabase.table("users").select("*").eq("github_id", github_id).execute()
    if not existing_user.data:
        supabase.table("users").insert({
            "github_id": github_id,
            "email": email,
            "name": name
        }).execute()

    return {
        "access_token": access_token,
        "github_id": github_id,
        "email": email,
        "name": name
    }

@app.get("/recipes", response_model=list[Document])
async def get_receipt(ingredient: str):
    try:
        docs = vector_store.similarity_search(ingredient, k=5)
        return [{"page_content": doc.page_content} for doc in docs]
    except Exception as e:
        print("🔥 Error during recipe search:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

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