from fastapi import FastAPI, Depends, HTTPException, Security, Request, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
import requests, os
from uuid import uuid4
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
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET") 
OpenAI_redirectURI = os.getenv("OPENAI_REDIRECT_URI")


PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
Render_URL = "https://chefgpt-bdfc.onrender.com"

pc = Pinecone(api_key=PINECONE_API_KEY)
index_name = "recipes"
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
vector_store = PineconeVectorStore.from_existing_index(index_name, embeddings)

app = FastAPI(
    title="ChefGPT. The best provider of Indian Recipes in the world",
    description="Give ChefGPT the name of an ingredient and it will give you multiple recipes to use that ingredient on in return.",
    servers=[
        {"url": Render_URL}
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
    if not state:
        state = str(uuid4())

    # 1. State 삽입
    insert_result = supabase.table("oauth_state").insert({"state": state}).execute()

    # 2. 삽입 직후 확인 (딜레이 대응)
    confirm_result = supabase.table("oauth_state").select("state").eq("state", state).execute()
    if not confirm_result.data:
        raise HTTPException(status_code=500, detail="Failed to store OAuth state.")


    github_auth_url = (
        f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={OpenAI_redirectURI}&scope=read:user&state={state}"
    )
    return JSONResponse({
        "message": "Click the button below to log in with GitHub.",
        "login_url": github_auth_url
    })


@app.get("/auth/callback")
def github_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code:
        return {"error": "No code provided"}

    # 1. Supabase에서 state 검증
    state_check = supabase.table("oauth_state").select("state").eq("state", state).execute()
    if not state_check.data:
        raise HTTPException(status_code=400, detail="Invalid state or expired")

    # 2. GitHub Access Token 요청
    token_response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        json={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": f"{Render_URL}/auth/callback", # OAuth redirect URI (서버가 받아야 할 주소)
            "state":state
        },
    )

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    # 3. 유저 정보 요청
    user_response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # 3. CustomGPT로 리디렉션
    redirect_url = f"{OpenAI_redirectURI}?code={code}&state={state}"   # 최종 리디렉션 주소 (CustomGPT로 돌아가는 주소)
    return RedirectResponse(redirect_url)


# OAuth 토큰 요청 처리
@app.post("/token", response_class=JSONResponse, include_in_schema=False)
async def handle_oauth_token(
    code: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...)
    ):
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


    # GitHub 사용자 정보 가져오기
    user_response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_data = user_response.json()
    github_id = str(user_data.get("id"))
    email = user_data.get("email") or "no-email@example.com"
    name = user_data.get("login") or "No Name"

    # Supabase에 사용자 정보 삽입 (직접 API 호출)
    supabase_headers = {
        "apikey": SUPABASE_ANON_KEY,               # Supabase anon key
        "Content-Type": "application/json"
    }

    supabase_payload = {
        "github_id": github_id,
        "email": email,
        "name": name
    }

    supabase_insert_url = f"{SUPABASE_URL}/rest/v1/users"

    supabase_response = requests.post(
        supabase_insert_url,
        headers=supabase_headers,
        json=supabase_payload
    )

    # Supabase 삽입 실패 시 에러 반환
    if supabase_response.status_code != 201:
        raise HTTPException(status_code=supabase_response.status_code, detail=supabase_response.json())
    
    # 삽입 성공시 CustomGPT로 넘길 토큰 반환
    return JSONResponse(content={
        "access_token": access_token,
        "github_id": github_id,
        "email": email,
        "name": name
    })


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

    # users 테이블에서 UUID 조회
    user_record = supabase.table("users").select("id").eq("github_id", str(github_id)).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User not found in Supabase")

    user_uuid = user_record.data[0]["id"]

    # 레시피 저장
    supabase.table("favorite_recipes").insert({
        "user_id": user_uuid,
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