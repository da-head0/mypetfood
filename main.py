from fastapi import Depends, FastAPI, Request, Form, status, Body, HTTPException
from fastapi import security
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from db.get_db import db, food_col, rating_col, cat_col, searchbytitle, countcatnum, Rating, User
from function.recommendation import compare_taste
import uvicorn
from starlette.responses import RedirectResponse, Response
from starlette.requests import Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2PasswordRequestForm
from fastapi_login import LoginManager
from fastapi_login.exceptions import InvalidCredentialsException
import os
from datetime import timedelta
from pydantic import BaseModel



app = FastAPI()

security = HTTPBasic()
SECRET = '3066ba5df3bf0d588ab84f69304cf991277a0847947d954c'
manager = LoginManager(SECRET, token_url='/auth/token', use_cookie=True)

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

class FoodItem(BaseModel):
    title: str

class UserCreate(BaseModel):
    cat_name: str
    cat_age: str

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def userinfo(request: Request, catname : str = None, catage : str=None): #credentials: HTTPBasicCredentials = Depends(security)): 
    data = "어떤 고양이를 키우시나요?"
    catindex = countcatnum()
    existcat = cat_col.find_one({"cat_name":catname}) 
    #return {"고양이 이름": credentials.username, "고양이 나이": credentials.password}

    if (not existcat) and (catname):
        cat_col.insert_one({"cat_id":catindex, "cat_name":catname, "cat_age":catage})
        return templates.TemplateResponse("user.html", {"request": request, "data":data})
    
    if existcat and catname: # 고양이를 중복 입력할 경우
        cat_col.update({"cat_name":catname}, {"$set" : {"cat_id":catindex-1, "cat_age":catage}})
    
    return templates.TemplateResponse("user.html", {"request": request, "data":data})

@app.get("/main", response_class=HTMLResponse)
async def rating(request: Request,foodtitle: str = None, stars : int=None):
    data = "고양이가 좋아하는 사료, 싫어하는 사료를 체크해 보세요"
    datalist = []
    data = food_col.find()
    for d in data:
        datalist.append(d)
    if stars and foodtitle:
        foodtitle = foodtitle
        catindex = countcatnum() # 일단.. 가장 이전 유저로 한다. 바꿔야 함.
        existitem = rating_col.find_one({"cat_id":catindex, "title":foodtitle}) 
        if not existitem:
            rating_col.insert_one({"cat_id":catindex, "title":foodtitle, "rating":stars})
            #message = "선호 정보가 등록되었습니다"
            return templates.TemplateResponse("page.html", {"request": request, "data":datalist}) #, "message" : message})
        else:
            rating_col.update_one({"cat_id":catindex, "title":foodtitle}, {"$set" : {"rating":stars}})
    return templates.TemplateResponse("page.html", {"request": request, "data":datalist})

@app.get("/recommendation", response_class=HTMLResponse)
async def recommend_food(request: Request, cat_id: int=countcatnum()-1):
    tastecompared = compare_taste(cat_id) # 인덱스 숫자가 옴
    findlist = []
    catratedlist = []
    # 이미 고양이가 평가한 리스트 만들기
    catrated = rating_col.find({'cat_id':cat_id})
    for cat in catrated:
        catratedlist.append(cat['title']) # 평가한 리스트
    for d in tastecompared:
        findfood = food_col.find({'index':d}) # 개별 정보
        # 이미 고양이가 평가한것은 제외
        for f in findfood: # fast api에서는 이렇게 조건문으로 해주어야 한다... 빼면 오류남
            if f['title'] in catratedlist:
                pass
            else:
            # d가 이미 고른 타이틀이 아닌지 확인 필요
                findlist.append(f)
    return templates.TemplateResponse("recommend.html", {"cat": cat_col.find_one({"cat_id":cat_id}), "request": request, "data":findlist})

@app.get("/catinfo", response_class=HTMLResponse)
async def recommend_food(request: Request, cat_id: int=1.0):
    catlist = []
    cats = cat_col.find()
    for cat in cats:
        reviewlist = []
        catreviewcount = rating_col.find({'cat_id':cat['cat_id']})
        for crw in catreviewcount:
            reviewlist.append(crw)
        catlist.append((cat, len(reviewlist)))
    return templates.TemplateResponse("catinfo.html", {"request": request, "cats":catlist})

@app.get("/search", response_class=HTMLResponse)
async def bytitle(request: Request, title: str =None, foodtitle: str = None, stars : int=None):
    data = searchbytitle(title)
    cat_id = countcatnum() - 1
    # 평가를 바꿀 경우
    existitem = rating_col.find_one({"cat_id":cat_id, "title":foodtitle}) 
    if (not existitem) and (foodtitle): # 처음 평가하는 경우
        rating_col.insert_one({"cat_id":cat_id, "title":foodtitle, "rating":stars}) # 데이터 추가
        return templates.TemplateResponse("rated.html", {"request": request, "data":data})
    else: # 다시 평가하는 경우
        rating_col.update_one({"cat_id":cat_id, "title":foodtitle}, {"$set" : {"rating":stars}})
    return templates.TemplateResponse("rated.html", {"request": request, "data":data})

@app.get("/itemlist", response_class=HTMLResponse)
async def bytitle(request: Request,foodtitle: str = None, stars : int=None):
    cat_id = countcatnum() - 1
    ratedlist = []
    catrated = rating_col.find({'cat_id':cat_id})
    for rated in catrated:
        ratedlist.append(rated)
    
    # 평가를 바꿀 경우
    if stars:
        rating_col.update_one({"cat_id":cat_id, "title":foodtitle}, {"$set" : {"rating":stars}})
    return templates.TemplateResponse("rated.html", {"request": request, "data":ratedlist})


@manager.user_loader
def load_cat(catname:str, catage:str):
    data = "어떤 고양이를 키우시나요?"
    catindex = countcatnum()
    existcat = cat_col.find_one({"cat_name":catname}) 
    #return {"고양이 이름": credentials.username, "고양이 나이": credentials.password}
    if not existcat:
        cat_col.insert_one({"cat_id":catindex, "cat_name":catname, "cat_age":catage})
        message = "고양이 정보가 추가되었습니다"
        return catname, catage 
        #templates.TemplateResponse("user.html", {"request": request, "data":data, "message" : message})
    
    else: # 고양이를 중복 입력할 경우
        cat_col.update({"cat_name":catname}, {"$set" : {"cat_id":catindex-1, "cat_age":catage}})
    #return templates.TemplateResponse("user.html", {"request": request, "data":data})


@app.get('/auth')
def auth(response: Response, user=Depends(manager)):
    token = manager.create_access_token(
        data=dict(sub=user.cat_name)
    )
    manager.set_cookie(response, token)
    return response

@app.post("/auth/register")
def register(user: UserCreate):
    existlist = []
    existcat = cat_col.find({'cat_name':user.cat_name})
    catindex = countcatnum()
    for cat in existcat:
        existlist.append(cat)
    if user.cat_name in existlist:
        raise HTTPException(status_code=400, detail="A user with this email already exists")
    else:
        cat_col.insert_one({"cat_id":catindex, "cat_name":user.cat_name, "cat_age":user.cat_age})
        return {"detail": "Successfull registered"}

# the python-multipart package is required to use the OAuth2PasswordRequestForm
@app.post('/auth/token')
def login(data: OAuth2PasswordRequestForm = Depends()):
    cat_name = data.catname
    cat_age = data.catage

    user = load_cat(cat_name, cat_age)  # we are using the same function to retrieve the user
    if not user:
        raise InvalidCredentialsException  # you can also use your own HTTPException
    elif cat_age != user['password']:
        raise InvalidCredentialsException
    
    access_token = manager.create_access_token(
        data=dict(sub=cat_name), expires=timedelta(hours=12)
    )
    return {'access_token': access_token, 'token_type': 'bearer'}

