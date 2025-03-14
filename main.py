from dotenv import load_dotenv
import os, jwt
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec 
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import List
from pydantic import BaseModel
from supabase import create_client

# 환경변수 로드
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

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

@app.get("/auth/github")
def github_auth():
    github_url = f"{SUPABASE_URL}/auth/v1/authorize?provider=github"
    return {"auth_url": github_url}


class UserInfo(BaseModel):
    id: str
    email: str
    name: str
    github_id: str


@app.post("/save-user")
def save_user(user_info: UserInfo):
    # user_info는 Pydantic 모델이므로 .으로 접근
    user_id = user_info.id
    email = user_info.email
    name = user_info.name
    github_id = user_info.github_id

    # users 테이블에 존재 여부 확인
    existing_user = supabase.table("users").select("*").eq("id", user_id).execute()

    if len(existing_user.data) == 0:
        # 없으면 새로 저장
        supabase.table("users").insert({
            "id": user_id,
            "email": email,
            "name": name,
            "github_id": github_id
        }).execute()
        return {"message": "User saved"}
    else:
        return {"message": "User already exists"}
    

# 요청 모델
class RecipeSaveRequest(BaseModel):
    recipe_id: str
    recipe_name: str
    recipe_detail: str

# JWT 인증 및 유저 정보 추출
def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization.split(" ")[1]
    payload = jwt.decode(token, options={"verify_signature": False})  # (간소화 예시)
    return payload["sub"]  # 이게 바로 Supabase의 user_id (UUID)

# 레시피 저장 API
@app.post("/recipes/save")
def save_recipe(request: RecipeSaveRequest, user_id: str = Depends(get_current_user)):
    supabase.table("favorite_recipes").insert({
        "user_id": user_id,  # ✅ 로그인한 유저의 UUID
        "recipe_id": request.recipe_id,
        "recipe_name": request.recipe_name,
        "recipe_detail": request.recipe_detail
    }).execute()
    return {"message": "Recipe saved"}